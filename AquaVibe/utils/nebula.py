"""Free Nebula-compatible AI generation bridge.

Image generation uses the anonymous AI Horde backend that Nebula documents as
its free image backend. Video uses the public Wan 2.2 Hugging Face Space used by
NiftyVid, accessed through Gradio without an API key.

This deliberately keeps provider-specific code out of Telegram handlers.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from AquaVibe.core.dir import DOWNLOAD_DIR

HORDE_BASE = os.getenv("NEBULA_HORDE_BASE", "https://stablehorde.net/api/v2").rstrip("/")
HORDE_KEY = os.getenv("NEBULA_HORDE_KEY", "0000000000").strip() or "0000000000"
HORDE_MODEL = os.getenv("NEBULA_IMAGE_MODEL", "AlbedoBase XL").strip()
VIDEO_SPACE = os.getenv("NEBULA_VIDEO_SPACE", "cbensimon/wan2-2-fp8da-aoti-preview2").strip()
VIDEO_MAX_SECONDS = float(os.getenv("NEBULA_VIDEO_MAX_SECONDS", "4.5"))


def _safe_name(prefix: str, suffix: str) -> Path:
    return Path(DOWNLOAD_DIR) / f"{prefix}_{os.getpid()}_{int(time.time()*1000)}{suffix}"


async def _horde_image(prompt: str) -> str:
    headers = {"apikey": HORDE_KEY, "Client-Agent": "AquaVibe/1.0"}
    payload = {
        "prompt": prompt[:4000],
        "params": {
            "n": 1,
            "width": 1024,
            "height": 1024,
            "steps": 25,
            "cfg_scale": 7.0,
        },
        "models": [HORDE_MODEL] if HORDE_MODEL else [],
        "r2": True,
        "nsfw": False,
        "trusted_workers": False,
        "slow_workers": True,
    }
    timeout = httpx.Timeout(30, read=60)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{HORDE_BASE}/generate/async", headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"Nebula image HTTP {r.status_code}: {r.text[:300]}")
        job = r.json()
        job_id = job.get("id")
        if not job_id:
            raise RuntimeError("Nebula image backend returned no job id")
        deadline = time.monotonic() + float(os.getenv("NEBULA_IMAGE_TIMEOUT", "180"))
        while time.monotonic() < deadline:
            await asyncio.sleep(3)
            q = await client.get(f"{HORDE_BASE}/generate/status/{job_id}", headers=headers)
            if q.status_code >= 400:
                raise RuntimeError(f"Nebula image status HTTP {q.status_code}: {q.text[:300]}")
            data = q.json()
            if data.get("faulted"):
                raise RuntimeError("Nebula image job failed on the worker")
            if not data.get("done"):
                continue
            gens = data.get("generations") or []
            if not gens:
                raise RuntimeError("Nebula image job finished without an image")
            gen = gens[0]
            img_url = gen.get("img") or gen.get("url")
            if not img_url:
                raise RuntimeError("Nebula image result had no download URL")
            img = await client.get(img_url, follow_redirects=True, timeout=60)
            img.raise_for_status()
            out = _safe_name("aquavibe_nebula", ".png")
            out.write_bytes(img.content)
            return str(out)
    raise RuntimeError("Nebula image generation timed out")


def _extract_endpoint(api: Any):
    """Pick a Gradio endpoint that accepts an image and prompt."""
    if not isinstance(api, dict):
        return None, []
    named = api.get("named_endpoints") or {}
    candidates = []
    for name, spec in named.items():
        text = (str(name) + " " + json.dumps(spec)).lower()
        if "predict" in text or "generate" in text or "video" in text:
            candidates.append((name, spec))
    for name, spec in candidates:
        params = spec.get("parameters") if isinstance(spec, dict) else []
        names = [str(p.get("parameter_name") or p.get("label") or "").lower() for p in (params or [])]
        if any("image" in n for n in names) and any("prompt" in n or "text" in n for n in names):
            return name, params
    if candidates:
        name, spec = candidates[0]
        return name, spec.get("parameters") if isinstance(spec, dict) else []
    return None, []


def _gradio_arg(param: dict, image_path: str, prompt: str):
    name = str(param.get("parameter_name") or param.get("label") or "").lower()
    typ = str(param.get("type") or "").lower()
    if "image" in name or "image" in typ:
        return image_path
    if "prompt" in name or "text" in name or "description" in name:
        return prompt[:3000]
    if "duration" in name or "seconds" in name:
        return VIDEO_MAX_SECONDS
    if "steps" in name:
        return int(os.getenv("NEBULA_VIDEO_STEPS", "20"))
    if "seed" in name:
        return -1
    # Prefer documented/default value when available.
    if "parameter_has_default" in param and param.get("parameter_has_default"):
        return param.get("parameter_default")
    if "default" in param:
        return param.get("default")
    # Common optional controls.
    if "guidance" in name or "cfg" in name:
        return 1.0
    return None


async def _niftyvid_video(image_path: str, prompt: str) -> str:
    try:
        from gradio_client import Client
    except Exception as exc:
        raise RuntimeError("gradio_client is not installed") from exc

    # gradio_client is sync; run it off the event loop so other bot handlers remain responsive.
    def run_sync():
        client = Client(VIDEO_SPACE, verbose=False)
        api = client.view_api(return_format="dict")
        endpoint, params = _extract_endpoint(api)
        if not endpoint:
            raise RuntimeError("No usable Wan 2.2 video endpoint found in the public Space")
        args = [_gradio_arg(p, image_path, prompt) for p in params]
        result = client.predict(*args, api_name=endpoint)
        return result

    result = await asyncio.to_thread(run_sync)

    def find_file(obj):
        if isinstance(obj, str):
            if obj.startswith("http://") or obj.startswith("https://"):
                return obj
            if os.path.exists(obj) and os.path.isfile(obj):
                return obj
        if isinstance(obj, dict):
            for key in ("video", "url", "path", "name"):
                if key in obj:
                    found = find_file(obj[key])
                    if found:
                        return found
        if isinstance(obj, (list, tuple)):
            for item in obj:
                found = find_file(item)
                if found:
                    return found
        return None

    source = find_file(result)
    if not source:
        raise RuntimeError(f"Wan 2.2 returned an unsupported result: {str(result)[:500]}")
    if os.path.isfile(source):
        return source
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        r = await client.get(source)
        r.raise_for_status()
        out = _safe_name("aquavibe_nebula", ".mp4")
        out.write_bytes(r.content)
        return str(out)


async def generate_nebula_image(prompt: str) -> str:
    return await _horde_image(prompt)


async def generate_nebula_video(prompt: str) -> str:
    # The public Wan 2.2 endpoint is image-to-video. Generate a still first so
    # /cvideo remains text-driven from the user's point of view.
    image = await _horde_image(prompt)
    try:
        return await _niftyvid_video(image, prompt)
    finally:
        Path(image).unlink(missing_ok=True)
