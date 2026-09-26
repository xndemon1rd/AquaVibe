"""Multi-provider AI helpers for AquaVibe.

Text chat prefers Gemini, then Groq, with optional OpenAI as a final fallback.
Image generation remains OpenAI-backed.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import httpx

from AquaVibe.core.dir import DOWNLOAD_DIR
import config

SYSTEM_PROMPT = (
    "You are 蒼響 AI, a concise and helpful Telegram assistant. "
    "Do not claim actions you did not perform. Keep answers useful and clear."
)


def _clean(text: str) -> str:
    return (text or "").strip()[: config.AI_MAX_INPUT]


def _history(history: Optional[list[dict]]) -> list[dict]:
    return [m for m in (history or [])[-8:] if m.get("role") in {"user", "assistant", "model"} and m.get("content")]


def _openai_headers():
    return {"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"}


def _extract_openai(data: dict) -> str:
    text = data.get("output_text")
    if text:
        return str(text).strip()
    parts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


async def _gemini(prompt: str, history: list[dict]) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")
    contents = []
    for m in history:
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": str(m["content"])[:4000]}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 1800},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"}, json=payload)
        r.raise_for_status()
        data = r.json()
    candidates = data.get("candidates") or []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(str(x.get("text", "")) for x in parts if x.get("text"))
        if text.strip():
            return text.strip()
    raise RuntimeError("Gemini returned no text")


async def _groq(prompt: str, history: list[dict]) -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY missing")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history:
        role = "assistant" if m.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": str(m["content"])[:4000]})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": config.GROQ_MODEL, "messages": messages, "max_tokens": 1800}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}, json=payload)
        r.raise_for_status()
        data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("Groq returned no text")
    return text


async def _openai(prompt: str, history: list[dict]) -> str:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": prompt}]
    payload = {"model": config.AI_MODEL, "input": messages, "max_output_tokens": 1800}
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post("https://api.openai.com/v1/responses", headers=_openai_headers(), json=payload)
        r.raise_for_status()
        text = _extract_openai(r.json())
    if not text:
        raise RuntimeError("OpenAI returned no text")
    return text


async def ask(prompt: str, history: Optional[list[dict]] = None) -> str:
    prompt = _clean(prompt)
    if not prompt:
        return "Tell me what you want help with."
    history = _history(history)

    providers = []
    if config.GEMINI_API_KEY:
        providers.append(("Gemini", _gemini))
    if config.GROQ_API_KEY:
        providers.append(("Groq", _groq))
    if config.OPENAI_API_KEY:
        providers.append(("OpenAI", _openai))
    if not providers:
        return "AI assistant is not configured. Add GEMINI_API_KEY or GROQ_API_KEY in Railway Variables."

    errors = []
    for name, provider in providers:
        try:
            return await provider(prompt, history)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}")
            continue
    return "AI providers are temporarily unavailable. Please try again shortly."


async def generate_image(prompt: str) -> Optional[str]:
    if not config.OPENAI_API_KEY:
        return None
    prompt = (prompt or "").strip()[:4000]
    if not prompt:
        return None
    payload = {"model": config.AI_IMAGE_MODEL, "prompt": prompt, "size": "1024x1024", "quality": "auto"}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers=_openai_headers(),
                json=payload,
            )
            data = r.json() if r.content else {}
            if r.status_code >= 400:
                err = data.get("error") or {}
                message = err.get("message") if isinstance(err, dict) else str(err)
                raise RuntimeError(message or f"OpenAI HTTP {r.status_code}")
        item = (data.get("data") or [{}])[0]
        b64 = item.get("b64_json")
        if not b64:
            raise RuntimeError("OpenAI returned no image data")
        out = Path(DOWNLOAD_DIR) / f"aquavibe_ai_{os.getpid()}_{abs(hash(prompt))}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(b64))
        return str(out)
    except Exception as exc:
        # Preserve the actual provider error so /cimage can diagnose the failure.
        config.LAST_IMAGE_ERROR = f"{type(exc).__name__}: {exc}"
        return None
