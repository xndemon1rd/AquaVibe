"""AquaVibe native Telegram colored-button compatibility layer.

Pyrofork 2.3.x predates Telegram Bot API 9.4 button styles. The bot still
uses Pyrofork for MTProto, so styled buttons are sent normally first and then
upgraded through the Bot API using editMessageReplyMarkup. This keeps all
existing callback handlers and Pyrogram code intact while enabling Telegram's
native primary/success/danger colors.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from pyrogram.types import InlineKeyboardButton as _InlineKeyboardButton

# Telegram button styles are applied through the Bot API because the pinned
# Pyrofork MTProto layer cannot serialize Bot API 9.4 style fields. Serialize
# style upgrades per message so rapid callback/edit operations cannot race and
# make the keyboard visibly flicker between styled and unstyled states.
_STYLE_LOCKS: dict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)


def _style_for(text: str, callback_data: Any = None) -> str:
    value = f"{text or ''} {callback_data or ''}".lower()
    danger = (
        "close", "cancel", "delete", "remove", "stop", "ban", "reject",
        "clear", "logout", "disconnect", "purge", "reset", "disable",
        "danger", "trash", "support", "owner", "✖", "❌", "🗑", "⛔"
    )
    primary = (
        "add me", "add", "play", "vplay", "back", "next", "menu",
        "info", "view", "open", "more", "home", "about", "channel",
        "group", "profile", "language", "page", "prev", "previous",
        "forward", "⏪", "⏩", "ℹ", "🔙", "🔗"
    )
    if any(token in value for token in danger):
        return "danger"
    if any(token in value for token in primary):
        return "primary"
    # Common positive/menu actions are green.  Keep SUPPORT/OWNER red via
    # the danger list above, and let all other ordinary action buttons be green.
    return "success"


class StyledInlineKeyboardButton(_InlineKeyboardButton):
    """Drop-in InlineKeyboardButton carrying an AquaVibe style marker."""

    def __init__(self, *args, **kwargs):
        self._aqua_style = kwargs.pop("aqua_style", None)
        self._aqua_icon_emoji_id = kwargs.pop("icon_custom_emoji_id", None)
        requested = kwargs.pop("style", None)
        super().__init__(*args, **kwargs)
        text = getattr(self, "text", args[0] if args else "")
        callback = getattr(self, "callback_data", None)
        self._aqua_style = self._aqua_style or requested or _style_for(text, callback)


def has_styled_buttons(reply_markup: Any) -> bool:
    if reply_markup is None:
        return False
    rows = getattr(reply_markup, "inline_keyboard", None)
    if rows is None:
        return False
    # Rebuilt keyboards returned by Telegram lose our private marker.  Treat
    # every inline keyboard as styleable and derive a safe color from its text
    # / callback when the explicit marker is unavailable.
    return any(getattr(button, "text", None) for row in rows for button in row)


def _button_to_bot_api(button: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"text": str(getattr(button, "text", ""))}
    style = getattr(button, "_aqua_style", None)
    if style not in {"primary", "success", "danger"}:
        style = _style_for(getattr(button, "text", ""), getattr(button, "callback_data", None))
    if style in {"primary", "success", "danger"}:
        data["style"] = style
    icon_id = getattr(button, "_aqua_icon_emoji_id", None)
    if icon_id:
        data["icon_custom_emoji_id"] = str(icon_id)

    callback = getattr(button, "callback_data", None)
    if callback is not None:
        if isinstance(callback, bytes):
            callback = callback.decode("utf-8", "replace")
        data["callback_data"] = str(callback)
        return data

    url = getattr(button, "url", None)
    if url is not None:
        data["url"] = str(url)
        return data

    switch = getattr(button, "switch_inline_query", None)
    if switch is not None:
        data["switch_inline_query"] = str(switch)
        return data

    switch_current = getattr(button, "switch_inline_query_current_chat", None)
    if switch_current is not None:
        data["switch_inline_query_current_chat"] = str(switch_current)
        return data

    web_app = getattr(button, "web_app", None)
    if web_app is not None:
        web_url = getattr(web_app, "url", None)
        if web_url:
            data["web_app"] = {"url": str(web_url)}
            return data

    login_url = getattr(button, "login_url", None)
    if login_url is not None:
        try:
            data["login_url"] = login_url.write_json() if hasattr(login_url, "write_json") else login_url.__dict__
            return data
        except Exception:
            pass

    user_id = getattr(button, "user_id", None)
    if user_id is not None:
        data["url"] = f"tg://user?id={int(user_id)}"
        return data

    # Unknown button types are left unstyled rather than risking a broken
    # keyboard. The regular Pyrogram-sent keyboard remains functional.
    data.pop("style", None)
    return data


def markup_to_bot_api(reply_markup: Any) -> dict[str, Any] | None:
    if not has_styled_buttons(reply_markup):
        return None
    rows = getattr(reply_markup, "inline_keyboard", None)
    return {"inline_keyboard": [[_button_to_bot_api(button) for button in row] for row in rows]}


async def apply_colored_markup(message: Any, bot_token: str, reply_markup: Any = None) -> bool:
    """Upgrade a just-sent/edited Pyrogram keyboard to native Bot API styles.

    Important: Pyrofork rebuilds the returned Message.reply_markup from Telegram,
    which drops our private ``_aqua_style`` attributes. Therefore callers pass
    the original markup object from their kwargs when available.
    """
    try:
        markup = reply_markup if reply_markup is not None else getattr(message, "reply_markup", None)
        payload_markup = markup_to_bot_api(markup)
        if not payload_markup:
            return False

        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None)
        message_id = getattr(message, "id", None)
        if chat_id is None or message_id is None or not bot_token:
            return False

        import aiohttp
        url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
        payload = {
            "chat_id": int(chat_id),
            "message_id": int(message_id),
            "reply_markup": json.dumps(payload_markup, ensure_ascii=False, separators=(",", ":")),
        }
        lock_key = (int(chat_id), int(message_id))
        lock = _STYLE_LOCKS[lock_key]
        async with lock:
            # Let a burst of callback/edit operations settle before applying
            # the native style. This avoids old and new markup updates racing
            # each other over the same message.
            await asyncio.sleep(0.12)
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    return response.status == 200
    except Exception:
        # Styling must never break an otherwise functional bot message.
        return False
