"""AquaVibe coloured inline buttons: blue, green and red.

Telegram (Bot API 9.4+) can paint inline buttons with three native styles:

    blue  -> "primary"
    green -> "success"
    red   -> "danger"

The pinned Pyrofork/MTProto layer cannot send those styles, so a keyboard is
delivered through the Bot API instead.  Nothing else in the bot has to change:
every module keeps doing ``InlineKeyboardButton(...)`` and the hooks installed
by :func:`install_color_hooks` (see ``AquaVibe/core/bot.py``) take care of the
colours.

How a colour is chosen
----------------------
1. Explicit:  ``InlineKeyboardButton("Stop", callback_data="x", color="red")``
   (``"blue"``, ``"green"``, ``"red"`` -- or ``"primary"/"success"/"danger"``).
2. Automatic: :func:`pick_color` looks at the button text / callback data.
   red   = close, stop, cancel, delete, remove, mute ...
   blue  = back, next, menu, help, info, queue, settings, links ...
   green = everything else (play, pause, skip, shuffle, loop, confirm ...)

Edit the word lists below to change the automatic rules.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
from collections import OrderedDict
from typing import Any, Optional

from pyrogram.types import InlineKeyboardButton as _InlineKeyboardButton

_log = logging.getLogger("AquaVibe.colors")


def _split_icon(text: str):
    """If ``text`` starts with a premium-mapped emoji, return (icon_id, rest)."""
    from AquaVibe.core.premium_emoji import BUTTON_ICON_EMOJI, DEFAULT_EMOJI

    stripped = text.lstrip()
    for emoji in sorted(BUTTON_ICON_EMOJI, key=len, reverse=True):
        if stripped.startswith(emoji):
            rest = stripped[len(emoji):]
            if rest.startswith("\ufe0f"):
                rest = rest[1:]
            rest = rest.lstrip()
            if rest:  # Telegram rejects empty button text
                return str(DEFAULT_EMOJI[emoji]), rest
    # No leading emoji: use a trailing one (e.g. "Next ➡️") as the icon.
    tail = text.rstrip()
    for emoji in sorted(BUTTON_ICON_EMOJI, key=len, reverse=True):
        for cand in (emoji, emoji + "\ufe0f"):
            if tail.endswith(cand):
                rest = tail[: -len(cand)].rstrip()
                if rest:
                    return str(DEFAULT_EMOJI[emoji]), rest
    return None, text

BLUE = "primary"
GREEN = "success"
RED = "danger"

_COLOR_NAMES = {
    "blue": BLUE, "primary": BLUE,
    "green": GREEN, "success": GREEN,
    "red": RED, "danger": RED,
}

# ── Automatic colour rules (edit freely) ──────────────────────────────────────
_RED_WORDS = frozenset({
    "close", "cancel", "delete", "remove", "stop", "ban", "kick", "mute",
    "clear", "reset", "disable", "logout", "disconnect", "purge", "reject",
    "decline", "leave", "end", "exit", "destroy", "wipe",
})
_RED_SYMBOLS = "✖✘❌🗑⛔🚫▢⏹■🔇"

_BLUE_WORDS = frozenset({
    "back", "next", "prev", "previous", "menu", "home", "help", "info", "about",
    "more", "open", "view", "page", "language", "lang", "settings", "setting",
    "queue", "lyrics", "volume", "support", "channel", "group", "owner",
    "profile", "add", "join", "source", "repo", "stats", "commands", "list",
    "search", "link", "updates", "update", "developer", "dev",
})
_BLUE_SYMBOLS = "⬅➡◀◁▷«»‹›⏪⏩🔙🔗ℹ⚙📋📝🧾🔊🌐"


def normalize_color(value: Any) -> Optional[str]:
    """Return "primary" / "success" / "danger" for a colour name, else None."""
    if value is None:
        return None
    return _COLOR_NAMES.get(str(value).strip().lower())


def pick_color(text: Any = "", callback_data: Any = None, is_link: bool = False) -> str:
    """Choose blue / green / red from a button's text and callback data."""
    if isinstance(callback_data, bytes):
        callback_data = callback_data.decode("utf-8", "replace")
    value = f"{text or ''} {callback_data or ''}".lower()
    words = re.findall(r"[a-z]+", value)

    # "forceclose", "autoclose" ... count as close.
    if any(w in _RED_WORDS or w.endswith("close") for w in words) or any(s in value for s in _RED_SYMBOLS):
        return RED
    if is_link or any(w in _BLUE_WORDS for w in words) or any(s in value for s in _BLUE_SYMBOLS):
        return BLUE
    return GREEN


# ── Button class ──────────────────────────────────────────────────────────────
class ColoredInlineKeyboardButton(_InlineKeyboardButton):
    """Drop-in ``InlineKeyboardButton`` that can carry a colour.

    Extra optional keyword arguments (all stripped before Pyrogram sees them):
        color / style / aqua_style  "blue" | "green" | "red" (or Telegram's names)
        icon_custom_emoji_id    Bot API custom-emoji icon for the button
    """

    def __init__(self, *args, **kwargs):
        color = kwargs.pop("color", None)
        style = kwargs.pop("style", None)
        aqua_style = kwargs.pop("aqua_style", None)  # legacy alias used by some plugins
        if style is None:
            style = aqua_style
        icon = kwargs.pop("icon_custom_emoji_id", None)
        super().__init__(*args, **kwargs)
        # Leading underscore: Pyrogram's Object.__str__ skips private attributes.
        self._aqua_color = normalize_color(color if color is not None else style)
        self._aqua_icon = str(icon) if icon else None


def _has_buttons(markup: Any) -> bool:
    rows = getattr(markup, "inline_keyboard", None)
    return bool(rows) and any(getattr(b, "text", None) for row in rows for b in row)


def _button_to_bot_api(button: Any) -> Optional[dict]:
    """Convert a Pyrogram button to Bot API JSON, or None if it can't be represented."""
    text = str(getattr(button, "text", "") or "")
    icon = getattr(button, "_aqua_icon", None)
    api_text = text
    if not icon:
        # Leading 🎶/👤/💎/... becomes a native premium icon.  The Pyrogram
        # button keeps the plain emoji, so it still shows if this push fails.
        icon, api_text = _split_icon(text)
    data: dict[str, Any] = {"text": api_text}

    callback = getattr(button, "callback_data", None)
    url = getattr(button, "url", None)
    switch = getattr(button, "switch_inline_query", None)
    switch_here = getattr(button, "switch_inline_query_current_chat", None)
    web_app = getattr(button, "web_app", None)
    login_url = getattr(button, "login_url", None)
    user_id = getattr(button, "user_id", None)
    copy_text = getattr(button, "copy_text", None)

    if callback is not None:
        if isinstance(callback, bytes):
            callback = callback.decode("utf-8", "replace")
        data["callback_data"] = str(callback)
    elif url is not None:
        data["url"] = str(url)
    elif switch is not None:
        data["switch_inline_query"] = str(switch)
    elif switch_here is not None:
        data["switch_inline_query_current_chat"] = str(switch_here)
    elif web_app is not None and getattr(web_app, "url", None):
        data["web_app"] = {"url": str(web_app.url)}
    elif login_url is not None and getattr(login_url, "url", None):
        login = {"url": str(login_url.url)}
        for attr in ("forward_text", "bot_username", "request_write_access"):
            if getattr(login_url, attr, None):
                login[attr] = getattr(login_url, attr)
        data["login_url"] = login
    elif user_id is not None:
        data["url"] = f"tg://user?id={int(user_id)}"
    elif copy_text is not None and getattr(copy_text, "text", None):
        data["copy_text"] = {"text": str(copy_text.text)}
    else:
        # Game / pay / unknown button types: refuse, so we never send a broken keyboard.
        return None

    color = getattr(button, "_aqua_color", None) or pick_color(
        text, callback, is_link=("url" in data or "login_url" in data or "web_app" in data)
    )
    data["style"] = color
    if icon:
        data["icon_custom_emoji_id"] = icon
    return data


def markup_to_bot_api(markup: Any) -> Optional[dict]:
    """Full ``reply_markup`` object for the Bot API, or None if not possible."""
    if not _has_buttons(markup):
        return None
    rows = []
    for row in markup.inline_keyboard:
        converted = [_button_to_bot_api(b) for b in row]
        if any(b is None for b in converted):
            return None
        rows.append(converted)
    return {"inline_keyboard": rows}


# ── Bot API transport ─────────────────────────────────────────────────────────
_SESSION: Any = None
_SESSION_LOOP: Optional[asyncio.AbstractEventLoop] = None


async def _get_session():
    """One keep-alive HTTP session for the whole process.

    Tuned for latency: IPv4 only (a dead IPv6 route makes the first connect
    stall for 1-2 s), cached DNS, and a long keep-alive so the TLS connection
    to api.telegram.org stays open between button updates.
    """
    import socket
    import aiohttp

    global _SESSION, _SESSION_LOOP
    loop = asyncio.get_running_loop()
    if _SESSION is None or _SESSION.closed or _SESSION_LOOP is not loop:
        if _SESSION is not None and not _SESSION.closed:
            try:
                await _SESSION.close()
            except Exception:
                pass
        connector = aiohttp.TCPConnector(
            family=socket.AF_INET,
            ttl_dns_cache=300,
            keepalive_timeout=75,
            limit=32,
            enable_cleanup_closed=True,
        )
        _SESSION = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=6, connect=2.5),
        )
        _SESSION_LOOP = loop
    return _SESSION


_WARM_TASK: Optional["asyncio.Task"] = None


async def warm_up() -> None:
    """Open the Bot API connection at startup and keep it alive.

    Without this, the first coloured keyboard after start-up (and the first one
    after the connection went idle) pays DNS + TCP + TLS -- the 1-2 s delay.
    Call once after the client has started.
    """
    global _WARM_TASK

    async def _ping() -> None:
        try:
            import config

            token = getattr(config, "BOT_TOKEN", "")
            if not token:
                return
            session = await _get_session()
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as resp:
                await resp.read()
        except Exception as exc:  # never include the URL: it contains the bot token
            _log.debug("colour warm-up ping failed: %s", type(exc).__name__)

    async def _keepalive() -> None:
        while True:
            await _ping()
            await asyncio.sleep(45)  # shorter than the 75 s keep-alive timeout

    await _ping()
    if _WARM_TASK is None or _WARM_TASK.done():
        _WARM_TASK = asyncio.ensure_future(_keepalive())


async def _bot_api(method: str, payload: dict) -> bool:
    try:
        import config

        token = getattr(config, "BOT_TOKEN", "")
        if not token:
            return False
        session = await _get_session()
        url = f"https://api.telegram.org/bot{token}/{method}"
        for attempt in (1, 2):
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return True
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body = {}
                description = str(body.get("description", "")).lower()
                if "message is not modified" in description:
                    return True  # already coloured
                if resp.status == 429 and attempt == 1:
                    wait = (body.get("parameters") or {}).get("retry_after", 1)
                    await asyncio.sleep(min(float(wait), 2.0))
                    continue
                _log.debug("Bot API %s failed: %s %s", method, resp.status, description)
                return False
    except Exception as exc:  # never include the URL: it contains the bot token
        _log.debug("Bot API %s error: %s", method, type(exc).__name__)
    return False


# ── Ordering: a newer keyboard must never be overwritten by an older one ──────
class _Slot:
    __slots__ = ("version", "lock")

    def __init__(self) -> None:
        self.version = 0
        self.lock = asyncio.Lock()


_MAX_TRACKED = 1024
_SLOTS: "OrderedDict[tuple, _Slot]" = OrderedDict()


def _next_version(key: tuple):
    slot = _SLOTS.get(key)
    if slot is None:
        slot = _SLOTS[key] = _Slot()
        while len(_SLOTS) > _MAX_TRACKED:
            _SLOTS.popitem(last=False)  # forget the oldest message (bounded memory)
    else:
        _SLOTS.move_to_end(key)
    slot.version += 1
    return slot, slot.version


async def _push_markup(chat_id: Any, message_id: int, bot_markup: dict) -> bool:
    slot, version = _next_version((str(chat_id), int(message_id)))
    async with slot.lock:
        if slot.version != version:
            return False  # a newer keyboard is already queued
        return await _bot_api(
            "editMessageReplyMarkup",
            {"chat_id": chat_id, "message_id": int(message_id), "reply_markup": bot_markup},
        )


async def apply_colors(message: Any, markup: Any) -> bool:
    """Colour the keyboard of an already-sent Pyrogram ``message``."""
    bot_markup = markup_to_bot_api(markup)
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    message_id = getattr(message, "id", None)
    if bot_markup is None or chat_id is None or message_id is None:
        return False
    return await _push_markup(chat_id, message_id, bot_markup)


# ── Client hooks ──────────────────────────────────────────────────────────────
# Every Client method that can carry an inline keyboard.  send_photo & friends
# matter most: the Now Playing card is a photo message.
_SEND_METHODS = (
    "send_message", "send_photo", "send_video", "send_audio",
    "send_animation", "send_document", "send_voice",
    "edit_message_text", "edit_message_caption", "edit_message_media",
)
_KEYBOARD_ONLY = "edit_message_reply_markup"
_TASKS: set = set()  # keep references so background tasks are not garbage-collected


def _find_markup(args: tuple, kwargs: dict) -> Any:
    markup = kwargs.get("reply_markup")
    if markup is not None:
        return markup
    for value in args:
        if hasattr(value, "inline_keyboard"):
            return value
    return None


def _wrap_send(original):
    @functools.wraps(original)
    async def wrapper(self, *args, **kwargs):
        markup = _find_markup(args, kwargs)
        result = await original(self, *args, **kwargs)
        if markup is not None and _has_buttons(markup) and getattr(result, "chat", None) is not None:
            # Do not delay the message: colour it in the background.
            task = asyncio.ensure_future(apply_colors(result, markup))
            _TASKS.add(task)
            task.add_done_callback(_TASKS.discard)
        return result

    wrapper._aqua_colored = True
    return wrapper


def _wrap_keyboard_only(original):
    """Keyboard-only refreshes (e.g. the player timer) go straight through the
    Bot API in ONE call, so the buttons never flash grey between edits."""

    @functools.wraps(original)
    async def wrapper(self, *args, **kwargs):
        markup = _find_markup(args, kwargs)
        chat_id = kwargs.get("chat_id", args[0] if len(args) > 0 else None)
        message_id = kwargs.get("message_id", args[1] if len(args) > 1 else None)
        if markup is not None and chat_id is not None and message_id is not None:
            bot_markup = markup_to_bot_api(markup)
            if bot_markup is not None and await _push_markup(chat_id, message_id, bot_markup):
                return None
        return await original(self, *args, **kwargs)  # fallback: plain Pyrogram edit

    wrapper._aqua_colored = True
    return wrapper


def install_color_hooks(client_cls) -> None:
    """Patch ``pyrogram.Client`` once so every inline keyboard comes out coloured.

    Call this BEFORE any other wrapper that replaces these Client methods.
    """
    for name in _SEND_METHODS:
        original = getattr(client_cls, name, None)
        if original is not None and not getattr(original, "_aqua_colored", False):
            setattr(client_cls, name, _wrap_send(original))
    original = getattr(client_cls, _KEYBOARD_ONLY, None)
    if original is not None and not getattr(original, "_aqua_colored", False):
        setattr(client_cls, _KEYBOARD_ONLY, _wrap_keyboard_only(original))
