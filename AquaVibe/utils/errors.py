# Authored By Dev © 2025
"""Centralized error capture and Telegram LOGGER_ID reporting."""
import asyncio
import os
import sys
import threading
import traceback
import hashlib
import html
import platform
import json
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime
from functools import wraps

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from AquaVibe.core.runtime import app
from config import (
    LOGGER_ID, DEBUG_IGNORE_LOG, REMOTE_ERROR_REPORTING,
    ERROR_SYSTEM_ENABLED, ERROR_DEDUP_WINDOW_SEC, ERROR_MAX_PER_WINDOW,
    ERROR_LOG_FILE, ERROR_INCLUDE_TRACEBACK, ERROR_REDACT_SECRETS,
)
from AquaVibe.log_config import LOGGER
from AquaVibe.utils.exceptions import is_ignored_error

DEBUG_LOG_FILE = "ignored_errors.log"
_LOCAL_LOGGER = LOGGER("AquaVibe.errors")
_ERROR_EVENTS = deque()
_ERROR_COUNTS = defaultdict(lambda: {"first": 0.0, "count": 0, "last": 0.0})
_ERROR_LOCK = threading.Lock()
_ERROR_LOG_PATH = Path(ERROR_LOG_FILE)

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(bot[_ -]?token\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_ -]?hash\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_ -]?key\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(mongo(?:db)?(?:\+srv)?://)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(string[_ -]?session\d*\s*[=:]\s*)[^\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password|passwd|secret|token|authorization)\s*[=:]\s*[^\s,}]+"), r"\1=[REDACTED]"),
]


def _sanitize(value, limit=None):
    text = _safe_text(value, limit or 20000)
    if ERROR_REDACT_SECRETS:
        for pattern, replacement in _SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
    return text[:limit] if limit else text


def _classify_severity(err):
    name = type(err).__name__.lower()
    text = str(err).lower()
    if any(x in name for x in ("memory", "systemexit", "keyboardinterrupt")):
        return "CRITICAL"
    if any(x in text for x in ("database", "mongo", "connection refused", "authentication failed")):
        return "HIGH"
    if any(x in name for x in ("timeout", "connection", "network")):
        return "MEDIUM"
    return "ERROR"


def _rate_state(fingerprint, force=False):
    now = time.monotonic()
    with _ERROR_LOCK:
        while _ERROR_EVENTS and now - _ERROR_EVENTS[0] > ERROR_DEDUP_WINDOW_SEC:
            _ERROR_EVENTS.popleft()
        state = _ERROR_COUNTS[fingerprint]
        if now - state["first"] > ERROR_DEDUP_WINDOW_SEC:
            state.update(first=now, count=0)
        state["count"] += 1
        state["last"] = now
        _ERROR_EVENTS.append(now)
        duplicate = state["count"] > 1
        suppressed = len(_ERROR_EVENTS) > ERROR_MAX_PER_WINDOW
        return duplicate, suppressed, state["count"]


async def _write_structured_event(event):
    try:
        _ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(_ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            await f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        _LOCAL_LOGGER.error("Could not write structured error event: %s", exc)


def _safe_text(value, limit=3500):
    try:
        text = str(value)
    except Exception:
        text = repr(value)
    return text[:limit]


async def send_large_error(text: str, caption: str, filename: str):
    """Send oversized error details directly to the configured Telegram logger.

    Tracebacks can contain URLs, identifiers, and request data, so do not upload
    them to a third-party paste service.
    """
    if not REMOTE_ERROR_REPORTING or not LOGGER_ID:
        return
    path = f"{filename}.txt"
    try:
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(_sanitize(text))
        await app.send_document(LOGGER_ID, path, caption="❌ Error Log (Local fallback)")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

def _html(value, limit=1200):
    return html.escape(_safe_text(value, limit), quote=False)


def _fingerprint(err, tb):
    raw = f"{type(err).__name__}|{str(err)}|{tb[-5000:]}"
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16].upper()


def _root_frame(tb):
    lines = [x.strip() for x in tb.splitlines() if x.strip().startswith("File ")]
    return lines[-1] if lines else "Unknown source location"


def _diagnosis(err, tb):
    """Return a conservative owner-facing diagnosis/fix for known errors."""
    text = f"{type(err).__name__}: {err}\n{tb}".lower()
    rules = [
        ("valueerror", "invalid literal for int()", "A duration or numeric field contains a non-numeric value (commonly '-' or an empty string).", "Validate/normalize the value before int() conversion; treat unavailable duration as 0.", "Check the source/search provider response and keep the formatter defensive."),
        ("attributeerror", "to_bytes", "A Telegram ID/entity field is a string where Pyrogram expects an integer.", "Convert Telegram custom-emoji/document IDs to int before constructing the entity.", "Inspect the entity builder and confirm every document/custom_emoji ID is an integer."),
        ("unexpected keyword argument", "", "A library API call is using an argument that the installed library no longer accepts.", "Use the installed library's supported parameter or the project's compatibility shim.", "Check the traceback line and installed package version before changing dependencies."),
        ("modulenotfounderror", "", "A required Python module is missing from the deployment environment.", "Add/pin the missing dependency in requirements.txt and rebuild.", "Verify the dependency is installed in the same Python environment used by Railway."),
        ("connectionerror", "", "A network/service connection failed.", "Retry with bounded backoff and verify the remote service, DNS, credentials, and timeout.", "Check whether the failure is transient or provider-side before changing code."),
        ("timeout", "", "An external operation exceeded its timeout.", "Use a suitable timeout/retry strategy and verify the external service is responsive.", "Check provider latency and avoid unbounded retries."),
    ]
    for typ, needle, cause, fix, owner in rules:
        if typ in text and (not needle or needle in text):
            return cause, fix, owner
    return ("The exception is not matched to a built-in diagnosis.",
            "Inspect the first application traceback frame and the exception message; make the smallest targeted fix and redeploy.",
            "Review the complete traceback, reproduce the failing command/action, then verify the fix in Railway logs.")


def format_traceback(err, tb, label: str, extras: dict = None, *, occurrence=1, severity=None, duplicate=False) -> str:
    tb = _sanitize(tb)
    exc_type = type(err).__name__
    fingerprint = _fingerprint(err, tb)
    severity = severity or _classify_severity(err)
    cause, fix, owner = _diagnosis(err, tb)
    parts = [
        f"🚨 <b>{_html(label, 200)}</b>",
        f"🆔 <b>Error ID:</b> <code>{fingerprint}</code>",
        f"📍 <b>Error Type:</b> <code>{_html(exc_type, 200)}</code>",
        f"🚦 <b>Severity:</b> <code>{severity}</code>",
        f"🔁 <b>Occurrences:</b> <code>{occurrence}</code>{" (duplicate)" if duplicate else ""}",
        f"💬 <b>Message:</b> <code>{_html(_sanitize(err, 1800), 1800)}</code>",
        f"📌 <b>Failure Location:</b> <code>{_html(_root_frame(tb), 1200)}</code>",
        f"🧠 <b>Likely Cause:</b> {_html(cause, 1800)}",
        f"🛠 <b>Recommended Fix:</b> {_html(fix, 1800)}",
        f"👑 <b>Owner Action:</b> {_html(owner, 1800)}",
        f"🐍 <b>Runtime:</b> <code>Python {platform.python_version()} | {platform.system()}</code>",
    ]
    if extras:
        parts.append("\n<b>📋 Context:</b>")
        for key, value in extras.items():
            parts.append(f"• <b>{_html(key, 80)}:</b> <code>{_html(_sanitize(value, 1000), 1000)}</code>")
    parts.append(f"\n<b>📜 Complete Traceback:</b>\n<pre>{_html(tb, 14000)}</pre>")
    return "\n".join(parts)


async def report_exception(err, tb=None, label="Unhandled Error", extras=None, *, force=False):
    """Capture, deduplicate, persist, diagnose, and report an exception safely."""
    try:
        if tb is None:
            tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        tb = _sanitize(tb)
        fingerprint = _fingerprint(err, tb)
        duplicate, rate_limited, occurrence = _rate_state(fingerprint, force=force)
        severity = _classify_severity(err)
        safe_extras = {str(k): _sanitize(v, 1200) for k, v in (extras or {}).items()}

        _LOCAL_LOGGER.error("%s [%s] %s (%s)", label, severity, _sanitize(err, 1000), fingerprint)

        if is_ignored_error(err) and DEBUG_IGNORE_LOG:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                async with aiofiles.open(DEBUG_LOG_FILE, "a", encoding="utf-8") as log:
                    await log.write(
                        f"\n--- Ignored Error | {label} @ {timestamp} ---\n"
                        f"Error ID: {fingerprint} | Severity: {severity} | Occurrence: {occurrence}\n"
                        f"Type: {type(err).__name__}\n"
                        f"Context: {json.dumps(safe_extras, ensure_ascii=False)}\n"
                        f"Traceback:\n{tb.strip()}\n------------------------------------------\n"
                    )
            except Exception as exc:
                _LOCAL_LOGGER.error("Could not write ignored error log: %s", exc)

        event = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "error_id": fingerprint,
            "severity": severity,
            "label": _sanitize(label, 200),
            "type": type(err).__name__,
            "message": _sanitize(err, 2000),
            "location": _sanitize(_root_frame(tb), 1200),
            "occurrence": occurrence,
            "duplicate": duplicate,
            "rate_limited": rate_limited,
            "context": safe_extras,
            "traceback": tb[-16000:] if ERROR_INCLUDE_TRACEBACK else "[traceback disabled by configuration]",
        }
        await _write_structured_event(event)

        if not ERROR_SYSTEM_ENABLED:
            return fingerprint
        try:
            connected = bool(getattr(app, "is_connected", False))
        except Exception:
            connected = False
        if not connected or not REMOTE_ERROR_REPORTING or not LOGGER_ID:
            return fingerprint
        # Suppress repeated identical alerts and protect the logger chat from storms.
        if (duplicate and not force) or rate_limited:
            return fingerprint

        caption = format_traceback(
            err, tb, label, safe_extras, occurrence=occurrence,
            severity=severity, duplicate=duplicate
        )
        filename = f"error_{fingerprint}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        if len(caption) > 4096:
            full = event["traceback"]
            await send_large_error(full, caption.split("\n\n", 1)[0], filename)
        else:
            await app.send_message(
                LOGGER_ID,
                f"<blockquote>{caption}</blockquote>",
                disable_web_page_preview=True,
            )
        return fingerprint
    except Exception as report_err:
        _LOCAL_LOGGER.error("LOGGER error-system failure: %s", report_err)
        return None


async def handle_trace(err, tb, label, filename=None, extras=None):
    # Every captured exception is sent to LOGGER_ID, including errors that are
    # classified as ignorable.  DEBUG_IGNORE_LOG only controls the local file.
    await report_exception(err, tb, label, extras)


# ========== Decorators ==============

def capture_err(func):
    """Handle command errors and report the complete traceback to LOGGER_ID."""
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            await report_exception(
                err, tb, "Chat Write Forbidden",
                {"User": message.from_user.mention if message.from_user else "N/A",
                 "Chat ID": message.chat.id,
                 "Command": message.text or message.caption},
            )
            try:
                await app.leave_chat(message.chat.id)
            except Exception as leave_err:
                await report_exception(leave_err, label="Leave Chat Error", extras={"Chat ID": message.chat.id})
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            try:
                from AquaVibe.utils.error_detector import record
                record(err, tb, "command")
            except Exception as detector_err:
                _LOCAL_LOGGER.error("Error detector failed: %s", detector_err)
            extras = {
                "User": message.from_user.mention if message.from_user else "N/A",
                "Command": message.text or message.caption,
                "Chat ID": message.chat.id,
            }
            await handle_trace(err, tb, "Command Error", None, extras)
            raise
    wrapper._trabel_error_capture = True
    return wrapper


def capture_callback_err(func):
    """Handle callback-query errors and report the complete traceback."""
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            try:
                from AquaVibe.utils.error_detector import record
                record(err, tb, "callback")
            except Exception as detector_err:
                _LOCAL_LOGGER.error("Error detector failed: %s", detector_err)
            msg = callback_query.message
            extras = {
                "User": callback_query.from_user.mention if callback_query.from_user else "N/A",
                "Chat ID": msg.chat.id if msg else "N/A",
            }
            await handle_trace(err, tb, "Callback Error", None, extras)
            raise
    wrapper._trabel_error_capture = True
    return wrapper


def capture_internal_err(func):
    """Handle background/internal async errors and report them to LOGGER_ID."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            try:
                from AquaVibe.utils.error_detector import record
                record(err, tb, "internal")
            except Exception as detector_err:
                _LOCAL_LOGGER.error("Error detector failed: %s", detector_err)
            await handle_trace(err, tb, "Internal Error", None, {"Function": func.__name__})
            raise
    wrapper._trabel_error_capture = True
    return wrapper


# ========== Global uncaught error hooks ==============
def install_global_error_logging():
    """Install process/thread/asyncio hooks for errors outside decorators."""
    def sys_hook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _LOCAL_LOGGER.error("UNCAUGHT PROCESS ERROR\n%s", tb)
        try:
            from AquaVibe.utils.error_detector import record
            record(exc_value, tb, "process")
        except Exception:
            pass
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(report_exception(exc_value, tb, "Uncaught Process Error"))
        except Exception:
            pass

    def thread_hook(args):
        tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        _LOCAL_LOGGER.error("UNCAUGHT THREAD ERROR [%s]\n%s", args.thread.name, tb)
        try:
            from AquaVibe.utils.error_detector import record
            record(args.exc_value, tb, "thread")
        except Exception:
            pass
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(report_exception(args.exc_value, tb, "Uncaught Thread Error", {"Thread": args.thread.name}))
        except Exception:
            pass

    def asyncio_hook(loop, context):
        err = context.get("exception") or RuntimeError(context.get("message", "Unknown asyncio error"))
        tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        extras = {"Task": str(context.get("future") or context.get("task") or "N/A")[:500]}
        _LOCAL_LOGGER.error("UNHANDLED ASYNCIO ERROR\n%s", tb)
        try:
            loop.create_task(report_exception(err, tb, "Unhandled Asyncio Error", extras))
        except Exception:
            pass

    sys.excepthook = sys_hook
    try:
        threading.excepthook = thread_hook
    except Exception:
        pass
    try:
        asyncio.get_event_loop().set_exception_handler(asyncio_hook)
    except Exception:
        pass
