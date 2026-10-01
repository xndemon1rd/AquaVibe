"""Extra group-management features for AquaVibe.

Adds only features not already provided by AquaVibe's existing moderation
handlers: warnings, configurable anti-link/bad-word/flood protection,
join CAPTCHA, per-group rules/welcome text, reports, and content locks.
"""
import asyncio
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from AquaVibe.core.runtime import app
from AquaVibe.core.mongo import mongodb
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


settings_db = mongodb.group_management
warnings_db = mongodb.group_warnings
badwords_db = mongodb.group_badwords

_flood = defaultdict(deque)
_captcha_tasks = {}
_link_re = re.compile(r"(?:https?://|www\.|t\.me/|telegram\.me/|(?:^|\s)@\w{4,})", re.I)

_MUTE = _permissions(can_send_messages=False)
_UNMUTE = _permissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)


def _key(chat_id: int) -> dict:
    return {"chat_id": chat_id}


async def _cfg(chat_id: int) -> dict:
    doc = await settings_db.find_one(_key(chat_id))
    return doc or {"chat_id": chat_id, "warn_limit": 3, "flood_limit": 5,
                   "flood_window": 5, "antilink": False, "captcha": False,
                   "locks": {}}


async def _set(chat_id: int, **values):
    await settings_db.update_one(_key(chat_id), {"$set": values}, upsert=True)


async def _is_admin(message: Message, user_id: int) -> bool:
    try:
        m = await app.get_chat_member(message.chat.id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def _bot_can(message: Message, permission: str) -> bool:
    try:
        me = await app.get_me()
        m = await app.get_chat_member(message.chat.id, me.id)
        if m.status == ChatMemberStatus.OWNER:
            return True
        return bool(getattr(m.privileges, permission, False))
    except Exception:
        return False


def _target(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None


# ---------------- Warnings ----------------
@app.on_message(filters.command("warn") & filters.group & admin_filter)
async def warn_cmd(_, message: Message):
    user = _target(message)
    if not user:
        return await message.reply_text("Reply to the user you want to warn.")
    if await _is_admin(message, user.id):
        return await message.reply_text("❌ Admins cannot be warned.")
    reason = message.text.split(None, 1)[1] if len(message.command) > 1 else "No reason"
    doc = await warnings_db.find_one({"chat_id": message.chat.id, "user_id": user.id})
    count = int((doc or {}).get("count", 0)) + 1
    cfg = await _cfg(message.chat.id)
    limit = int(cfg.get("warn_limit", 3))
    if count >= limit:
        if not await _bot_can(message, "can_restrict_members"):
            return await message.reply_text(f"⚠️ {user.mention} reached {count}/{limit} warnings, but I need restrict-members permission to auto-mute.")
        await app.restrict_chat_member(message.chat.id, user.id, _MUTE)
        await warnings_db.delete_one({"chat_id": message.chat.id, "user_id": user.id})
        return await message.reply_text(f"🔇 {user.mention} auto-muted after {count}/{limit} warnings.\nReason: {reason}")
    await warnings_db.update_one({"chat_id": message.chat.id, "user_id": user.id}, {"$set": {"count": count, "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    await message.reply_text(f"⚠️ {user.mention} warned: **{count}/{limit}**\nReason: {reason}")


@app.on_message(filters.command("warnings") & filters.group)
async def warnings_cmd(_, message: Message):
    user = _target(message) or message.from_user
    if not user:
        return
    doc = await warnings_db.find_one({"chat_id": message.chat.id, "user_id": user.id})
    cfg = await _cfg(message.chat.id)
    await message.reply_text(f"⚠️ {user.mention} has **{int((doc or {}).get('count', 0))}/{int(cfg.get('warn_limit', 3))}** warnings.")


@app.on_message(filters.command("unwarn") & filters.group & admin_filter)
async def unwarn_cmd(_, message: Message):
    user = _target(message)
    if not user:
        return await message.reply_text("Reply to a user to remove one warning.")
    doc = await warnings_db.find_one({"chat_id": message.chat.id, "user_id": user.id})
    count = max(0, int((doc or {}).get("count", 0)) - 1)
    if count:
        await warnings_db.update_one({"chat_id": message.chat.id, "user_id": user.id}, {"$set": {"count": count}})
    else:
        await warnings_db.delete_one({"chat_id": message.chat.id, "user_id": user.id})
    await message.reply_text(f"✅ Warning removed from {user.mention}. Current warnings: **{count}**")


@app.on_message(filters.command("clearwarnings") & filters.group & admin_filter)
async def clearwarnings_cmd(_, message: Message):
    user = _target(message)
    if not user:
        return await message.reply_text("Reply to a user to clear warnings.")
    await warnings_db.delete_one({"chat_id": message.chat.id, "user_id": user.id})
    await message.reply_text(f"✅ Cleared warnings for {user.mention}.")


@app.on_message(filters.command("setwarnlimit") & filters.group & admin_filter)
async def setwarnlimit_cmd(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit() or not 1 <= int(message.command[1]) <= 20:
        return await message.reply_text("Usage: `/setwarnlimit 3` (1–20)")
    n = int(message.command[1])
    await _set(message.chat.id, warn_limit=n)
    await message.reply_text(f"✅ Auto-mute warning limit set to **{n}**.")


# ---------------- Rules / welcome / report ----------------
@app.on_message(filters.command("setrules") & filters.group & admin_filter)
async def setrules_cmd(_, message: Message):
    text = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else (message.reply_to_message.text if message.reply_to_message else "")
    if not text:
        return await message.reply_text("Usage: `/setrules your group rules` or reply to a text message.")
    await _set(message.chat.id, rules=text)
    await message.reply_text("✅ Group rules updated.")


@app.on_message(filters.command("rules") & filters.group)
async def rules_cmd(_, message: Message):
    cfg = await _cfg(message.chat.id)
    await message.reply_text(cfg.get("rules", "No rules have been configured yet. Admins can use /setrules."))


@app.on_message(filters.command("setwelcome") & filters.group & admin_filter)
async def setwelcome_cmd(_, message: Message):
    text = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else (message.reply_to_message.text if message.reply_to_message else "")
    if not text:
        return await message.reply_text("Usage: `/setwelcome Hello {name}, welcome to {group}!`")
    await _set(message.chat.id, welcome=text)
    await message.reply_text("✅ Custom welcome saved. Variables: `{name}` and `{group}`.")


@app.on_message(filters.command("report") & filters.group)
async def report_cmd(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to the message you want to report.")
    reporters = []
    try:
        async for member in app.get_chat_members(message.chat.id, filter="administrators"):
            if member.user and not member.user.is_bot:
                reporters.append(member.user.mention)
    except Exception:
        reporters = []
    admin_text = " ".join(reporters[:15]) or "group admins"
    text = f"🚨 **Reported message**\nReported by: {message.from_user.mention}\nAdmins: {admin_text}"
    try:
        await message.reply_to_message.reply_text(text)
    except Exception:
        await message.reply_text(text)


# ---------------- Anti-link / bad words / flood ----------------
@app.on_message(filters.command("antilink") & filters.group & admin_filter)
async def antilink_cmd(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
        return await message.reply_text("Usage: `/antilink on` or `/antilink off`")
    enabled = message.command[1].lower() == "on"
    await _set(message.chat.id, antilink=enabled)
    await message.reply_text(f"🔗 Anti-link {'enabled' if enabled else 'disabled'}.")


@app.on_message(filters.command("addbadword") & filters.group & admin_filter)
async def addbadword_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/addbadword word`")
    word = message.text.split(None, 1)[1].strip().lower()
    await badwords_db.update_one({"chat_id": message.chat.id, "word": word}, {"$set": {"word": word}}, upsert=True)
    await message.reply_text(f"✅ Added `{word}` to the group bad-word filter.")


@app.on_message(filters.command("removebadword") & filters.group & admin_filter)
async def removebadword_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/removebadword word`")
    word = message.text.split(None, 1)[1].strip().lower()
    await badwords_db.delete_one({"chat_id": message.chat.id, "word": word})
    await message.reply_text(f"✅ Removed `{word}` from the filter.")


@app.on_message(filters.command("badwords") & filters.group & admin_filter)
async def badwords_cmd(_, message: Message):
    words = [d["word"] async for d in badwords_db.find({"chat_id": message.chat.id}).limit(100)]
    await message.reply_text("🚫 **Filtered words:**\n" + ("\n".join(f"• `{w}`" for w in words) if words else "None"))


@app.on_message(filters.command("setfloodlimit") & filters.group & admin_filter)
async def setfloodlimit_cmd(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit() or not 2 <= int(message.command[1]) <= 30:
        return await message.reply_text("Usage: `/setfloodlimit 5` (2–30 messages / 5 seconds)")
    n = int(message.command[1])
    await _set(message.chat.id, flood_limit=n)
    await message.reply_text(f"🌊 Flood limit set to **{n} messages / 5 seconds**.")


@app.on_message(filters.command("flood") & filters.group & admin_filter)
async def flood_cmd(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
        return await message.reply_text("Usage: `/flood on` or `/flood off`")
    enabled = message.command[1].lower() == "on"
    await _set(message.chat.id, flood=enabled)
    await message.reply_text(f"🌊 Anti-flood {'enabled' if enabled else 'disabled'}.")


@app.on_message(filters.all, group=-20)
async def protection_listener(_, message: Message):
    if not message.chat or message.chat.type.value not in ("group", "supergroup") or not message.from_user:
        return
    if message.from_user.is_bot or await _is_admin(message, message.from_user.id):
        return
    cfg = await _cfg(message.chat.id)
    text = (message.text or message.caption or "").strip()
    if cfg.get("antilink") and text and _link_re.search(text):
        if await _bot_can(message, "can_delete_messages"):
            try: await message.delete()
            except Exception: pass
        return
    if text:
        words = [d["word"] async for d in badwords_db.find({"chat_id": message.chat.id}).limit(200)]
        low = text.casefold()
        if any(w.casefold() in low for w in words):
            if await _bot_can(message, "can_delete_messages"):
                try: await message.delete()
                except Exception: pass
            return
    if cfg.get("flood"):
        now = asyncio.get_running_loop().time()
        q = _flood[(message.chat.id, message.from_user.id)]
        q.append(now)
        window = int(cfg.get("flood_window", 5))
        while q and now - q[0] > window: q.popleft()
        if len(q) >= int(cfg.get("flood_limit", 5)) and await _bot_can(message, "can_restrict_members"):
            try:
                await app.restrict_chat_member(message.chat.id, message.from_user.id, _MUTE, until_date=datetime.now(timezone.utc)+timedelta(seconds=30))
                q.clear()
            except Exception: pass


# ---------------- Content locks ----------------
_LOCK_ATTRS = {"links", "media", "stickers", "gifs", "photos", "videos", "audio", "documents"}

@app.on_message(filters.command("lock") & filters.group & admin_filter)
async def lock_cmd(_, message: Message):
    kind = message.command[1].lower() if len(message.command) > 1 else "all"
    if kind != "all" and kind not in _LOCK_ATTRS:
        return await message.reply_text("Usage: `/lock all|links|media|stickers|gifs|photos|videos|audio|documents`")
    cfg = await _cfg(message.chat.id)
    locks = dict(cfg.get("locks", {}))
    if kind == "all":
        for k in _LOCK_ATTRS: locks[k] = True
    else: locks[kind] = True
    await _set(message.chat.id, locks=locks)
    await message.reply_text(f"🔒 Locked **{kind}**.")


@app.on_message(filters.command("unlock") & filters.group & admin_filter)
async def unlock_cmd(_, message: Message):
    kind = message.command[1].lower() if len(message.command) > 1 else "all"
    if kind != "all" and kind not in _LOCK_ATTRS:
        return await message.reply_text("Usage: `/unlock all|links|media|stickers|gifs|photos|videos|audio|documents`")
    cfg = await _cfg(message.chat.id)
    locks = dict(cfg.get("locks", {}))
    if kind == "all":
        for k in _LOCK_ATTRS: locks[k] = False
    else: locks[kind] = False
    await _set(message.chat.id, locks=locks)
    await message.reply_text(f"🔓 Unlocked **{kind}**.")


@app.on_message(filters.all, group=-19)
async def lock_listener(_, message: Message):
    if not message.chat or message.chat.type.value not in ("group", "supergroup") or not message.from_user:
        return
    if message.from_user.is_bot or await _is_admin(message, message.from_user.id): return
    cfg = await _cfg(message.chat.id); locks = cfg.get("locks", {})
    kind = None
    if (message.photo or message.video or message.audio or message.document) and locks.get("media"): kind = "media"
    if message.photo and locks.get("photos"): kind = "photos"
    if message.video and locks.get("videos"): kind = "videos"
    if message.audio and locks.get("audio"): kind = "audio"
    if message.document and locks.get("documents"): kind = "documents"
    if (message.sticker) and locks.get("stickers"): kind = "stickers"
    if (message.animation) and locks.get("gifs"): kind = "gifs"
    text = message.text or message.caption or ""
    if locks.get("links") and text and _link_re.search(text): kind = "links"
    if kind and await _bot_can(message, "can_delete_messages"):
        try: await message.delete()
        except Exception: pass


# ---------------- Join CAPTCHA + custom welcome ----------------
@app.on_message(filters.command("captcha") & filters.group & admin_filter)
async def captcha_cmd(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
        return await message.reply_text("Usage: `/captcha on` or `/captcha off`")
    enabled = message.command[1].lower() == "on"
    await _set(message.chat.id, captcha=enabled)
    await message.reply_text(f"🧩 Join CAPTCHA {'enabled' if enabled else 'disabled'}.")


@app.on_message(filters.new_chat_members, group=-10)
async def join_guard(_, message: Message):
    cfg = await _cfg(message.chat.id)
    for user in message.new_chat_members:
        if user.is_bot and user.id != app.id: continue
        welcome = cfg.get("welcome")
        if welcome:
            try:
                await message.reply_text(welcome.replace("{name}", user.mention).replace("{group}", message.chat.title or "this group"))
            except Exception: pass
        if not cfg.get("captcha") or user.is_bot: continue
        if not await _bot_can(message, "can_restrict_members"): continue
        try:
            await app.restrict_chat_member(message.chat.id, user.id, _MUTE)
            cb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ I'm human", callback_data=f"aqua_captcha:{message.chat.id}:{user.id}")]])
            prompt = await message.reply_text(f"🧩 {user.mention}, tap the button within **120 seconds** to verify you're human.", reply_markup=cb)
            async def expire(chat_id=message.chat.id, uid=user.id, prompt_id=prompt.id):
                await asyncio.sleep(120)
                try:
                    await app.ban_chat_member(chat_id, uid)
                    await app.unban_chat_member(chat_id, uid)
                except Exception: pass
                _captcha_tasks.pop((chat_id, uid), None)
            task = asyncio.create_task(expire())
            _captcha_tasks[(message.chat.id, user.id)] = task
        except Exception:
            continue


@app.on_callback_query(filters.regex(r"^aqua_captcha:(-?\d+):(\d+)$"))
async def captcha_verify(_, query: CallbackQuery):
    _, chat_id, uid = query.data.split(":")
    chat_id, uid = int(chat_id), int(uid)
    if query.from_user.id != uid:
        return await query.answer("This verification belongs to another user.", show_alert=True)
    task = _captcha_tasks.pop((chat_id, uid), None)
    if task: task.cancel()
    try:
        await app.restrict_chat_member(chat_id, uid, _UNMUTE)
    except RPCError:
        return await query.answer("I couldn't restore your permissions. Ask an admin.", show_alert=True)
    await query.answer("Verified! Welcome to the group.")
    try: await query.message.edit_text(f"✅ {query.from_user.mention} verified successfully.")
    except Exception: pass
