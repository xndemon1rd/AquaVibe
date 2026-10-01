"""Advanced group-security/automation features for AquaVibe.

These are original implementations of feature ideas commonly found in large
Telegram management bots. They intentionally do not duplicate AquaVibe's
existing warn/antilink/flood/lock/captcha handlers.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.types import (
    ChatPermissions,
    ChatJoinRequest,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app
from AquaVibe.utils.admin_filters import admin_filter

def _permissions(**values):
    """Build ChatPermissions across Pyrogram/Pyrofork variants."""
    import inspect
    try:
        params = inspect.signature(ChatPermissions).parameters
        allowed = set(params)
        if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            values = {k: v for k, v in values.items() if k in allowed}
    except (TypeError, ValueError):
        pass
    return ChatPermissions(**values)


security_db = mongodb.aqua_advanced_security
raid_windows: dict[int, deque[float]] = defaultdict(deque)

_READONLY = _permissions(can_send_messages=False)
_NORMAL = _permissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)


def _key(chat_id: int) -> dict:
    return {"chat_id": int(chat_id)}


async def _cfg(chat_id: int) -> dict:
    doc = await security_db.find_one(_key(chat_id))
    return doc or {"chat_id": chat_id, "raidmode": False, "raid_limit": 8, "raid_window": 20,
                   "welcome_enabled": True, "goodbye_enabled": False, "goodbye": "👋 {name} left {group}.",
                   "protect": False}


async def _set(chat_id: int, **values):
    await security_db.update_one(_key(chat_id), {"$set": values}, upsert=True)


async def _bot_can(chat_id: int, permission: str) -> bool:
    try:
        me = await app.get_me()
        member = await app.get_chat_member(chat_id, me.id)
        if member.status == ChatMemberStatus.OWNER:
            return True
        return bool(getattr(member.privileges, permission, False))
    except Exception:
        return False


@app.on_message(filters.command("protect") & filters.group)
async def protect_cmd(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
        # Social /protect @user is available to members; /protect on|off remains admin-only.
        try:
            from AquaVibe.plugins.social.social_features import _protect_action
            return await _protect_action(message)
        except Exception:
            return await message.reply_text("Usage: `/protect on`, `/protect off`, or reply to a user with `/protect`.")
    try:
        member = await app.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply_text("🔒 Admin only for group protection. For a social shield, reply to a user with `/protect`.")
    except Exception:
        return await message.reply_text("🔒 I could not verify your admin status.")
    enabled = message.command[1].lower() == "on"
    await _set(message.chat.id, protect=enabled, antilink=enabled, flood=enabled)
    await message.reply_text(
        f"🛡️ Advanced protection {'enabled' if enabled else 'disabled'}.\n"
        "Anti-link and anti-flood are synchronized with this switch; fine-tune them with /antilink and /flood."
    )


@app.on_message(filters.command("raidmode") & filters.group & admin_filter)
async def raidmode_cmd(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
        return await message.reply_text("Usage: `/raidmode on|off [limit] [seconds]`")
    enabled = message.command[1].lower() == "on"
    limit = int(message.command[2]) if len(message.command) > 2 and message.command[2].isdigit() else 8
    window = int(message.command[3]) if len(message.command) > 3 and message.command[3].isdigit() else 20
    limit = max(2, min(limit, 100))
    window = max(5, min(window, 300))
    await _set(message.chat.id, raidmode=enabled, raid_limit=limit, raid_window=window)
    state = "enabled" if enabled else "disabled"
    await message.reply_text(f"🚨 Raid mode {state}. Trigger: {limit} joins / {window}s.")


@app.on_message(filters.command("raidstatus") & filters.group)
async def raidstatus_cmd(_, message: Message):
    cfg = await _cfg(message.chat.id)
    await message.reply_text(
        "🚨 <b>Raid Protection</b>\n\n"
        f"• Mode: <b>{'ON' if cfg.get('raidmode') else 'OFF'}</b>\n"
        f"• Trigger: <code>{cfg.get('raid_limit', 8)}</code> joins / <code>{cfg.get('raid_window', 20)}</code>s\n"
        f"• Advanced protect: <b>{'ON' if cfg.get('protect') else 'OFF'}</b>"
    )


@app.on_chat_join_request()
async def join_request_guard(_, request: ChatJoinRequest):
    """Auto-handle join requests during an active raid window.

    We only decline requests when raid mode is explicitly enabled. Otherwise
    Telegram's normal join-request workflow remains untouched.
    """
    try:
        cfg = await _cfg(request.chat.id)
        if not cfg.get("raidmode"):
            return
        # During raid mode, pending join requests are declined rather than
        # silently approved. This keeps the group protected until an admin
        # turns the mode off.
        await app.decline_chat_join_request(request.chat.id, request.from_user.id)
    except Exception:
        return


@app.on_chat_join_request()
async def join_request_notify(_, request: ChatJoinRequest):
    """Post every pending join request in the group with Accept/Reject
    buttons, so an admin can decide it from the chat.
    Skipped when raid mode already auto-declined it.
    """
    try:
        cfg = await _cfg(request.chat.id)
        if cfg.get("raidmode"):
            return
        user = request.from_user
        if not user:
            return
        name = user.first_name or "Someone"
        mention = f'<a href="tg://user?id={user.id}">{name}</a>'
        bio = getattr(request, "bio", None)
        text = (
            "📥 <b>New join request</b>\n\n"
            f"{mention} (<code>{user.id}</code>) wants to join this group."
            + (f"\n\n<i>{bio}</i>" if bio else "")
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Accept", callback_data=f"jreq_ok:{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"jreq_no:{user.id}"),
        ]])
        await app.send_message(request.chat.id, text, reply_markup=keyboard)
    except Exception:
        return


@app.on_callback_query(filters.regex(r"^jreq_(ok|no):(-?\d+)$"))
async def join_request_decision_cb(_, callback: CallbackQuery):
    action, target_id = callback.matches[0].group(1), int(callback.matches[0].group(2))
    chat_id = callback.message.chat.id

    try:
        member = await app.get_chat_member(chat_id, callback.from_user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await callback.answer("Only group admins can decide join requests.", show_alert=True)
    except Exception:
        return await callback.answer("Could not verify your admin status.", show_alert=True)

    try:
        if action == "ok":
            await app.approve_chat_join_request(chat_id, target_id)
            outcome = "✅ Approved"
        else:
            await app.decline_chat_join_request(chat_id, target_id)
            outcome = "❌ Rejected"
    except RPCError:
        return await callback.answer("This request may already be resolved.", show_alert=True)

    await callback.answer(outcome)
    try:
        by = callback.from_user.first_name or "an admin"
        await callback.message.edit_text(
            f"{outcome} join request from <code>{target_id}</code> — by {by}."
        )
    except Exception:
        pass


@app.on_message(filters.new_chat_members, group=-8)
async def raid_join_guard(_, message: Message):
    cfg = await _cfg(message.chat.id)
    if not cfg.get("raidmode"):
        return
    if not await _bot_can(message.chat.id, "can_restrict_members"):
        return
    now = asyncio.get_running_loop().time()
    q = raid_windows[message.chat.id]
    for _member in message.new_chat_members:
        q.append(now)
    window = int(cfg.get("raid_window", 20))
    while q and now - q[0] > window:
        q.popleft()
    if len(q) < int(cfg.get("raid_limit", 8)):
        return
    # Once the threshold is crossed, temporarily mute the new arrivals. We do
    # not mass-ban existing members or attempt destructive actions.
    until = datetime.now(timezone.utc) + timedelta(minutes=5)
    for member in message.new_chat_members:
        try:
            await app.restrict_chat_member(message.chat.id, member.id, _READONLY, until_date=until)
        except Exception:
            pass
    q.clear()
    try:
        await message.reply_text("🚨 <b>Raid protection triggered.</b> New arrivals are temporarily muted. Admins can review the group and disable /raidmode when safe.")
    except Exception:
        pass


@app.on_message(filters.command("setgoodbye") & filters.group & admin_filter)
async def setgoodbye_cmd(_, message: Message):
    text = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else ""
    if not text:
        return await message.reply_text("Usage: `/setgoodbye Goodbye {name} from {group}!`")
    await _set(message.chat.id, goodbye=text[:1000], goodbye_enabled=True)
    await message.reply_text("✅ Goodbye message saved and enabled. Variables: `{name}` and `{group}`.")


@app.on_message(filters.command("goodbye") & filters.group & admin_filter)
async def goodbye_cmd(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
        return await message.reply_text("Usage: `/goodbye on|off`")
    enabled = message.command[1].lower() == "on"
    await _set(message.chat.id, goodbye_enabled=enabled)
    await message.reply_text(f"👋 Goodbye messages {'enabled' if enabled else 'disabled'}.")


@app.on_message(filters.left_chat_member, group=-7)
async def goodbye_listener(_, message: Message):
    cfg = await _cfg(message.chat.id)
    if not cfg.get("goodbye_enabled") or not message.left_chat_member:
        return
    user = message.left_chat_member
    if user.is_bot:
        return
    text = str(cfg.get("goodbye") or "👋 {name} left {group}.")
    text = text.replace("{name}", user.mention).replace("{group}", message.chat.title or "this group")
    try:
        await message.reply_text(text)
    except Exception:
        pass


@app.on_message(filters.command("cleanup") & filters.group & admin_filter)
async def cleanup_cmd(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("Usage: `/cleanup <1-100>` — removes recent bot messages.")
    limit = max(1, min(int(message.command[1]), 100))
    deleted = 0
    try:
        me = await app.get_me()
        ids = []
        async for msg in app.get_chat_history(message.chat.id, limit=limit):
            if msg.from_user and msg.from_user.id == me.id:
                ids.append(msg.id)
        if ids:
            await app.delete_messages(message.chat.id, ids)
            deleted = len(ids)
    except Exception:
        pass
    await message.reply_text(f"🧹 Cleaned <b>{deleted}</b> recent bot messages.")


@app.on_message(filters.command("purgefrom") & filters.group & admin_filter)
async def purgefrom_cmd(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to the first message you want removed, then use `/purgefrom`.")
    deleted = 0
    try:
        start = message.reply_to_message.id
        end = message.id
        ids = list(range(start, end + 1))
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            await app.delete_messages(message.chat.id, chunk)
            deleted += len(chunk)
    except Exception:
        pass
    # The command itself may already be deleted; no follow-up is required.
