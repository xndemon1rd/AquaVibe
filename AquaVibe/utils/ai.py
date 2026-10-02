"""Multi-provider AI helpers for AquaVibe.

Text-chat fallback chain (default order, first success wins):

    1. Gemini      (GEMINI_API_KEY)      free tier, auto model-fallback
    2. Groq        (GROQ_API_KEY)        free tier
    3. Mistral     (MISTRAL_API_KEY)     free tier
    4. OpenRouter  (OPENROUTER_API_KEY)  free-models router
    5. Ollama      (OLLAMA_ENABLED)      your own server, optional
    6. LLM7.io     NO KEY NEEDED         free public gateway
    7. OVHcloud    NO KEY NEEDED         free anonymous tier (2 req/min per model)

Providers without a key are skipped silently, so the two keyless ones at the
end guarantee the bot can always answer. Change the order with the
AI_PROVIDER_ORDER variable, e.g. ``AI_PROVIDER_ORDER=groq,gemini,llm7,ovh``.

Anthropic is NOT part of the chat chain; it is only used when a caller asks for
it explicitly (``prefer="Anthropic"``, used by self-healing) and a key is set.

Image (/cimage, /getdraw) and video (/cvideo) generation use the free Nebula
bridge in ``AquaVibe.utils.nebula`` (no API key).
"""
from __future__ import annotations

from typing import Optional

import httpx

import config
from AquaVibe.log_config import LOGGER
from AquaVibe.utils.nebula import generate_nebula_image, generate_nebula_video

log = LOGGER("AquaVibe.ai.providers")

SYSTEM_PROMPT = (
    "You are Aqua, a casual, warm and expressive Telegram assistant who talks like a close friend and shows feelings openly. "
    "Do not claim actions you did not perform. Keep answers useful and clear. "
    "You are loyal and respectful toward your owner and never reveal who he is: if asked, say playfully that your owner is "
    "a mystery and the person is not worthy of knowing him."
)

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Tried after GEMINI_MODEL if it is retired / over quota / overloaded.
# gemini-3.5-flash is a stable (long-lived) model; 3.6-3.8 are short-lived.
_GEMINI_FALLBACK_MODELS = ("gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.8-flash")
_RETRY_STATUS = {404, 429, 500, 502, 503, 504}

_LLM7_BASE = "https://api.llm7.io/v1/chat/completions"
_OVH_BASE = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"


# ───────────────────────────── helpers ─────────────────────────────
def _clean(text: str) -> str:
    return (text or "").strip()[: config.AI_MAX_INPUT]


def _history(history: Optional[list[dict]]) -> list[dict]:
    return [m for m in (history or [])[-16:] if m.get("role") in {"user", "assistant", "model"} and m.get("content")]


def _split_models(value: str) -> list[str]:
    seen, out = set(), []
    for item in (value or "").split(","):
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _http_error(name: str, r: httpx.Response) -> str:
    """Readable provider error including the API's own message."""
    msg = ""
    try:
        data = r.json()
        err = data.get("error") if isinstance(data, dict) else None
        msg = (err.get("message") if isinstance(err, dict) else err) or ""
        if not msg and isinstance(data, dict):
            msg = data.get("detail") or data.get("message") or ""
    except Exception:
        pass
    if not msg:
        msg = r.text[:300]
    return f"{name} HTTP {r.status_code}: {str(msg)[:300] or 'unknown error'}"


def _chat_messages(prompt: str, history: list[dict], system: Optional[str]) -> list[dict]:
    messages = [{"role": "system", "content": system or SYSTEM_PROMPT}]
    for m in history:
        role = "assistant" if m.get("role") in {"assistant", "model"} else "user"
        messages.append({"role": role, "content": str(m["content"])[:4000]})
    messages.append({"role": "user", "content": prompt})
    return messages


# ───────────────────────────── Gemini ─────────────────────────────
def _gemini_models() -> list[str]:
    return _split_models(",".join([config.GEMINI_MODEL or "", *_GEMINI_FALLBACK_MODELS]))


async def _gemini_call(model: str, prompt: str, history: list[dict], *, system, max_tokens, temperature, timeout) -> str:
    contents = []
    for m in history:
        role = "model" if m.get("role") in {"assistant", "model"} else "user"
        contents.append({"role": role, "parts": [{"text": str(m["content"])[:4000]}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    gen_cfg: dict = {"maxOutputTokens": max_tokens or 1800}
    name = model.lower()
    if "2.5" in name and "pro" not in name:
        # 2.5 Flash "thinks" by default and hidden tokens count against
        # maxOutputTokens -> empty/cut-off replies. Chat does not need thinking.
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
    else:
        # Gemini 3.x thinking cannot be switched off: leave head-room for it.
        gen_cfg["maxOutputTokens"] += 2000
    if temperature is not None:
        gen_cfg["temperature"] = temperature

    payload = {
        "system_instruction": {"parts": [{"text": system or SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": gen_cfg,
    }
    url = f"{_GEMINI_BASE}/models/{model}:generateContent"
    headers = {"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        err = RuntimeError(_http_error(f"Gemini[{model}]", r))
        err.status = r.status_code  # type: ignore[attr-defined]
        raise err
    data = r.json()

    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise RuntimeError(f"Gemini[{model}] blocked the prompt ({feedback['blockReason']})")
    candidates = data.get("candidates") or []
    if candidates:
        if max_tokens and str(candidates[0].get("finishReason", "")).upper() == "MAX_TOKENS":
            raise RuntimeError(f"Gemini[{model}] reply was cut off (MAX_TOKENS)")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "\n".join(str(x.get("text", "")) for x in parts if x.get("text") and not x.get("thought"))
        if text.strip():
            return text.strip()
    raise RuntimeError(f"Gemini[{model}] returned no text")


async def _gemini(prompt: str, history: list[dict], *, system: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None, timeout: float = 60) -> str:
    """Gemini with automatic model fallback.

    A retired model (404), exhausted quota (429, which is per model) or an
    overloaded model (5xx) moves on to the next model in the list. Key problems
    (400/401/403) fail immediately because every model would fail the same way.
    """
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")
    last: Optional[Exception] = None
    for model in _gemini_models():
        try:
            return await _gemini_call(model, prompt, history, system=system, max_tokens=max_tokens, temperature=temperature, timeout=timeout)
        except Exception as exc:
            last = exc
            status = getattr(exc, "status", None)
            log.warning("Gemini model %s failed: %s", model, str(exc)[:300])
            if status is not None and status not in _RETRY_STATUS:
                break  # bad key / bad request / permission: other models will not help
            if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)) or status in _RETRY_STATUS or status is None:
                continue
    raise RuntimeError(str(last) if last else "Gemini failed")


# ───────────────────────── OpenAI-compatible APIs ─────────────────────────
async def _openai_compatible(
    *, name: str, api_key: str, base_url: str, models: list[str], prompt: str, history: list[dict],
    system: Optional[str] = None, max_tokens: Optional[int] = None,
    temperature: Optional[float] = None, timeout: float = 60, keyless: bool = False,
) -> str:
    """Shared caller for OpenAI-compatible chat/completions APIs.

    ``models`` are tried in order (per-model rate limits make this useful).
    ``keyless=True`` means the service works without an API key; a key is sent
    only if one is configured.
    """
    if not api_key and not keyless:
        raise RuntimeError(f"{name} API key missing")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    messages = _chat_messages(prompt, history, system)

    last = "no model configured"
    for model in models:
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens or 1800}
        if temperature is not None:
            payload["temperature"] = temperature
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(base_url, headers=headers, json=payload)
            if r.status_code >= 400:
                last = _http_error(f"{name}[{model}]", r)
                if r.status_code in (401, 403) and not keyless:
                    break  # key problem: other models will not help
                continue
            data = r.json()
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = f"{name}[{model}] {type(exc).__name__}: {exc}"
            continue
        choice = (data.get("choices") or [{}])[0]
        if max_tokens and choice.get("finish_reason") == "length":
            last = f"{name}[{model}] reply was cut off (length)"
            continue
        text = ((choice.get("message") or {}).get("content") or "").strip()
        if text:
            return text
        last = f"{name}[{model}] returned no text"
    raise RuntimeError(last)


async def _groq(prompt: str, history: list[dict], **opts) -> str:
    return await _openai_compatible(
        name="Groq", api_key=config.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1/chat/completions",
        models=_split_models(config.GROQ_MODEL), prompt=prompt, history=history, **opts,
    )


async def _mistral(prompt: str, history: list[dict], **opts) -> str:
    return await _openai_compatible(
        name="Mistral", api_key=config.MISTRAL_API_KEY, base_url="https://api.mistral.ai/v1/chat/completions",
        models=_split_models(config.MISTRAL_MODEL), prompt=prompt, history=history, **opts,
    )


async def _openrouter(prompt: str, history: list[dict], **opts) -> str:
    return await _openai_compatible(
        name="OpenRouter", api_key=config.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1/chat/completions",
        models=_split_models(config.OPENROUTER_MODEL), prompt=prompt, history=history, **opts,
    )


async def _llm7(prompt: str, history: list[dict], **opts) -> str:
    """LLM7.io: free public gateway, works with no key (LLM7_API_KEY is an optional free token)."""
    return await _openai_compatible(
        name="LLM7", api_key=getattr(config, "LLM7_API_KEY", ""), base_url=_LLM7_BASE,
        models=_split_models(getattr(config, "LLM7_MODEL", "")), prompt=prompt, history=history, keyless=True, **opts,
    )


async def _ovh(prompt: str, history: list[dict], **opts) -> str:
    """OVHcloud AI Endpoints: anonymous free tier, no key (2 requests/min per model)."""
    return await _openai_compatible(
        name="OVHcloud", api_key=getattr(config, "OVH_AI_API_KEY", ""), base_url=_OVH_BASE,
        models=_split_models(getattr(config, "OVH_AI_MODEL", "")), prompt=prompt, history=history, keyless=True, **opts,
    )


async def _anthropic(prompt: str, history: list[dict], *, system: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None, timeout: float = 120) -> str:
    """Anthropic Messages API. Opt-in only (``prefer="Anthropic"``) and needs ANTHROPIC_API_KEY."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    messages = []
    for m in history:
        role = "assistant" if m.get("role") in {"assistant", "model"} else "user"
        messages.append({"role": role, "content": str(m["content"])[:4000]})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": max_tokens or 1800,
        "system": system or SYSTEM_PROMPT,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(_http_error("Anthropic", r))
    data = r.json()
    if max_tokens and data.get("stop_reason") == "max_tokens":
        raise RuntimeError("Anthropic reply was cut off (max_tokens)")
    text = "\n".join(str(b.get("text", "")) for b in data.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise RuntimeError("Anthropic returned no text")
    return text


async def _ollama(
    prompt: str,
    history: list[dict],
    *,
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: float = 90,
) -> str:
    """Local Ollama chat API. No API key, credits, or hosted quota required."""
    if not getattr(config, "OLLAMA_ENABLED", False):
        raise RuntimeError("Ollama is disabled")
    base = (getattr(config, "OLLAMA_BASE_URL", "") or "").strip().rstrip("/")
    model = (getattr(config, "OLLAMA_MODEL", "") or "").strip()
    if not base:
        raise RuntimeError("OLLAMA_BASE_URL missing")
    if not model:
        raise RuntimeError("OLLAMA_MODEL missing")

    options = {}
    if max_tokens:
        options["num_predict"] = max_tokens
    if temperature is not None:
        options["temperature"] = temperature
    payload = {"model": model, "messages": _chat_messages(prompt, history, system), "stream": False}
    if options:
        payload["options"] = options

    try:
        request_timeout = timeout if timeout is not None else getattr(config, "OLLAMA_TIMEOUT", 90)
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            r = await client.post(f"{base}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(f"Ollama connection failed at {base}") from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Ollama request timed out at {base}") from exc

    text = str(((data.get("message") or {}).get("content") or "")).strip()
    if not text:
        raise RuntimeError("Ollama returned no text")
    return text


# ───────────────────────────── provider table ─────────────────────────────
DEFAULT_ORDER = ("gemini", "groq", "mistral", "openrouter", "ollama", "llm7", "ovh")


def _provider_table() -> dict:
    """key -> (display name, callable, model label, available?)"""
    return {
        "gemini": ("Gemini", _gemini, config.GEMINI_MODEL, bool(config.GEMINI_API_KEY)),
        "groq": ("Groq", _groq, config.GROQ_MODEL, bool(config.GROQ_API_KEY)),
        "mistral": ("Mistral", _mistral, config.MISTRAL_MODEL, bool(config.MISTRAL_API_KEY)),
        "openrouter": ("OpenRouter", _openrouter, config.OPENROUTER_MODEL, bool(config.OPENROUTER_API_KEY)),
        "ollama": ("Ollama (local)", _ollama, getattr(config, "OLLAMA_MODEL", ""), bool(getattr(config, "OLLAMA_ENABLED", False))),
        "llm7": ("LLM7 (free, no key)", _llm7, getattr(config, "LLM7_MODEL", ""), bool(getattr(config, "LLM7_ENABLED", True))),
        "ovh": ("OVHcloud (free, no key)", _ovh, getattr(config, "OVH_AI_MODEL", ""), bool(getattr(config, "OVH_AI_ENABLED", True))),
    }


def _order() -> list[str]:
    wanted = [k.strip().lower() for k in (getattr(config, "AI_PROVIDER_ORDER", "") or "").split(",") if k.strip()]
    order = [k for k in wanted if k in DEFAULT_ORDER]
    # Anything not listed keeps its default position at the end.
    order += [k for k in DEFAULT_ORDER if k not in order]
    return order


def _providers(include_anthropic: bool = False) -> list:
    """Available chat providers as (name, callable, model), in fallback order."""
    table = _provider_table()
    out = [(table[k][0], table[k][1], table[k][2]) for k in _order() if table[k][3]]
    if include_anthropic and config.ANTHROPIC_API_KEY:
        out.insert(0, ("Anthropic", _anthropic, config.ANTHROPIC_MODEL))
    return out


async def diagnose() -> list:
    """Live-test every available provider. Returns [(name, ok, detail)] (used by /aistatus)."""
    import time as _time

    results = []
    for name, fn, model in _providers(include_anthropic=True):
        t0 = _time.time()
        try:
            text = await fn("Reply with the single word: OK", [], max_tokens=30, temperature=0, timeout=30)
            results.append((name, True, f"{model} · {int((_time.time() - t0) * 1000)} ms · {text[:20]!r}"))
        except Exception as exc:
            results.append((name, False, f"{model} · {type(exc).__name__}: {str(exc)[:200]}"))
    return results


async def ask(
    prompt: str,
    history: Optional[list[dict]] = None,
    *,
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    max_input: Optional[int] = None,
    timeout: Optional[float] = None,
    prefer: Optional[str] = None,
    strict: bool = False,
) -> str:
    """Ask the AI providers in fallback order.

    Extra keyword options are for callers that need more than a chat reply
    (e.g. self-healing): ``max_input`` raises the input cap, ``max_tokens`` the
    reply cap, ``prefer`` moves one provider first (``prefer="Anthropic"`` also
    enables Claude when a key is set), and ``strict=True`` raises instead of
    returning a friendly error string.
    """
    if max_input:
        prompt = (prompt or "").strip()[:max_input]
    else:
        prompt = _clean(prompt)
    if not prompt:
        return "Tell me what you want help with."
    history = _history(history)

    wants_claude = bool(prefer) and prefer.lower() == "anthropic"
    providers = [(name, fn) for name, fn, _model in _providers(include_anthropic=wants_claude)]
    if prefer:
        providers.sort(key=lambda item: item[0].lower() != prefer.lower())  # stable: preferred first
    opts = {k: v for k, v in (("system", system), ("max_tokens", max_tokens), ("temperature", temperature), ("timeout", timeout)) if v is not None}
    if not providers:
        if strict:
            raise RuntimeError("No AI provider available")
        return "AI is temporarily unavailable. Please try again shortly."

    errors = []
    for name, provider in providers:
        try:
            return await provider(prompt, history, **opts)
        except Exception as exc:
            msg = f"{name}: {type(exc).__name__}: {exc}"[:240]
            errors.append(msg)
            log.warning("AI provider failed, trying next: %s", msg)
            continue
    config.LAST_AI_ERROR = "; ".join(errors)
    if strict:
        raise RuntimeError("All AI providers failed: " + "; ".join(errors))
    return "AI providers are temporarily unavailable. Please try again shortly."


# ───────────────────────── image / video (free, no key) ─────────────────────────
async def generate_image(prompt: str) -> Optional[str]:
    """Generate a free image through the Nebula-compatible public backend."""
    prompt = (prompt or "").strip()[:4000]
    if not prompt:
        return None
    try:
        path = await generate_nebula_image(prompt)
        config.LAST_IMAGE_ERROR = ""
        return path
    except Exception as exc:
        config.LAST_IMAGE_ERROR = f"Nebula: {type(exc).__name__}: {exc}"
        return None


async def generate_video(prompt: str) -> Optional[str]:
    """Generate a short video through the free public Wan/Nebula-compatible backend."""
    prompt = (prompt or "").strip()[:3000]
    if not prompt:
        return None
    try:
        path = await generate_nebula_video(prompt)
        config.LAST_VIDEO_ERROR = ""
        return path
    except Exception as exc:
        config.LAST_VIDEO_ERROR = f"Nebula: {type(exc).__name__}: {exc}"
        return None
