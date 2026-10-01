"""Lightweight runtime error recorder for production deployments."""
from __future__ import annotations

import asyncio

import json
import sys
import time
import traceback
import hashlib
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERROR_LOG = ROOT / "self_healing_errors.jsonl"

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(bot[_ -]?token\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_ -]?(?:key|hash)\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(mongo(?:db)?(?:\+srv)?://)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(string[_ -]?session\d*\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+"), r"\1[REDACTED]"),
]

def _sanitize(text: object, limit: int = 16000) -> str:
    value = str(text)[:limit]
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value
_INSTALLED = False
_ATTEMPTS = defaultdict(int)
_MAX_ATTEMPTS = 3



def _deterministic_repair(error: BaseException, traceback_text: str) -> str | None:
    """Return a deterministic repair action for known, non-AI failures.

    These are runtime safety nets, not arbitrary source rewriting. The current
    process is protected immediately; the AI healer is only used for unknown
    failures after this layer.
    """
    text = f"{type(error).__name__}: {error}\n{traceback_text}".lower()
    if "unexpected keyword argument 'quote'" in text or 'unexpected keyword argument "quote"' in text:
        try:
            from AquaVibe.core.bot import _install_reply_compatibility
            _install_reply_compatibility()
            return "Reinstalled Kurigram reply compatibility shim for legacy quote= usage"
        except Exception:
            return None
    return None

def _dispatch(error: BaseException, traceback_text: str, source: str) -> None:
    # Railway-lite: record errors only. Never spawn repair threads or rewrite
    # source code from inside the production bot process.
    fingerprint = hashlib.sha256(
        f"{type(error).__name__}|{str(error)}|{traceback_text[-4000:]}".encode("utf-8", "replace")
    ).hexdigest()[:20]
    if _ATTEMPTS[fingerprint] >= _MAX_ATTEMPTS:
        return
    _ATTEMPTS[fingerprint] += 1
    try:
        _deterministic_repair(error, traceback_text)
    except Exception:
        pass

def diagnose(error: BaseException, traceback_text: str) -> dict:
    text = f"{type(error).__name__}: {error}\n{traceback_text}".lower()
    if isinstance(error, ValueError) and "invalid literal for int()" in text:
        return {"cause": "A numeric field contained a non-numeric value.", "fix": "Validate/normalize the value before int() conversion; unavailable values should use a safe default.", "owner_action": "Check the provider response and the exact traceback input."}
    if isinstance(error, AttributeError) and "to_bytes" in text:
        return {"cause": "A Telegram ID/entity field was passed as str instead of int.", "fix": "Convert the Telegram custom-emoji/document ID to int before constructing the entity.", "owner_action": "Inspect the entity builder and verify ID types."}
    if isinstance(error, ModuleNotFoundError):
        return {"cause": "A required Python module is unavailable in the deployment image.", "fix": "Add/pin the missing package in requirements.txt and rebuild.", "owner_action": "Confirm the package is installed in Railway's runtime."}
    return {"cause": "No deterministic diagnosis matched this exception.", "fix": "Inspect the first application traceback frame and exception message, then apply a targeted fix.", "owner_action": "Reproduce the failing action and verify the fix after redeploy."}


def record(error: BaseException, traceback_text: str, source: str = "runtime") -> str:
    fingerprint = hashlib.sha256(
        f"{type(error).__name__}|{str(error)}|{traceback_text[-5000:]}".encode("utf-8", "replace")
    ).hexdigest()[:16].upper()
    diagnosis = diagnose(error, traceback_text)
    event = {
        "timestamp": int(time.time()),
        "source": source,
        "error_id": fingerprint,
        "type": type(error).__name__,
        "message": _sanitize(error, 2000),
        "diagnosis": diagnosis,
        "traceback": _sanitize(traceback_text, 16000),
    }
    try:
        with ERROR_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass
    _dispatch(error, traceback_text, source)
    return fingerprint


def install() -> None:
    """Install process/asyncio-level detectors once."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def loop_handler(current_loop, context):
        exc = context.get("exception") or RuntimeError(context.get("message", "Unhandled asyncio exception"))
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        record(exc, tb, "asyncio")
        if previous_handler:
            previous_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(loop_handler)

    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        record(exc_value, tb, "process")
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook
