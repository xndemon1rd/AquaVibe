"""Additional group-management commands missing from AquaVibe's existing manager.

Inspired by command surfaces documented by Rose/MissRose, ProtectiveBot and
other Telegram group-management projects. Existing AquaVibe handlers are not
re-registered here; this module only adds commands that were absent.
"""
from datetime import datetime, timedelta, timezone
import re
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from pyrogram.errors import RPCError

from AquaVibe.core.runtime import app
from AquaVibe.core.mongo import mongodb
from AquaVibe.utils.admin_filters import admin_filter

cfg_db = mongodb.group_management
allow_db = mongodb.group_allowlist
fed_db = mongodb.group_federations
fedban_db = mongodb.group_fedbans

def _arg(message):
    return message.text.split(None, 1)[1].strip() if message.text and len(message.command) > 1 else ""

async def _cfg(chat_id):
    return await cfg_db.find_one({"chat_id": chat_id}) or {"chat_id": chat_id}

async def _set(chat_id, **values):
    await cfg_db.update_one({"chat_id": chat_id}, {"$set": values}, upsert=True)

async def _target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        raw = message.command[1].lstrip("@").strip()
        try:
            return await app.get_users(int(raw))
        except Exception:
            try:
                return await app.get_users(raw)
            except Exception:
                return None
    return None

# --- Flood controls ---
@app.on_message(filters.command("setflood") & filters.group & admin_filter)
async def setflood(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("Usage: `/setflood 7` — set messages allowed in the flood window; use 0 to disable.")
    n = int(message.command[1])
    await _set(message.chat.id, flood_limit=max(0, min(n, 100)), flood=n > 0)
    await message.reply_text(f"🌊 Flood limit set to **{n}**.")

@app.on_message(filters.command("setfloodmode") & filters.group & admin_filter)
async def setfloodmode(_, message: Message):
    mode = message.command[1].lower() if len(message.command) > 1 else ""
    if mode not in {"ban", "kick", "mute", "tban", "tmute"}:
        return await message.reply_text("Usage: `/setfloodmode ban|kick|mute|tban|tmute`")
    await _set(message.chat.id, flood_action=mode)
    await message.reply_text(f"🌊 Flood action set to **{mode}**.")

# --- Lock/help surface ---
@app.on_message(filters.command("locktypes") & filters.group)
async def locktypes(_, message: Message):
    await message.reply_text(
        "🔒 **Available lock types**\n\n"
        "`links` `media` `stickers` `gifs` `photos` `videos` `audio` `documents`\n"
        "`bot` `command` `contact` `poll` `voice` `location` `games` `forward`\n\n"
        "Use `/lock <type>` and `/unlock <type>`."
    )

# --- Allowlist for anti-link/filters ---
@app.on_message(filters.command("allowlist") & filters.group & admin_filter)
async def allowlist(_, message: Message):
    if len(message.command) < 2:
        rows = [d.get("value", "") async for d in allow_db.find({"chat_id": message.chat.id}).limit(100)]
        return await message.reply_text("🟢 **Allowlist:**\n" + ("\n".join(f"• `{x}`" for x in rows) if rows else "Empty."))
    action = message.command[1].lower()
    value = " ".join(message.command[2:]).strip()
    if action in {"add", "del", "remove"}:
        if not value:
            return await message.reply_text("Usage: `/allowlist add example.com` or `/allowlist del example.com`")
        if action == "add":
            await allow_db.update_one({"chat_id": message.chat.id, "value": value.lower()}, {"$set": {"value": value.lower()}}, upsert=True)
            return await message.reply_text(f"✅ Added `{value}` to allowlist.")
        await allow_db.delete_one({"chat_id": message.chat.id, "value": value.lower()})
        return await message.reply_text(f"✅ Removed `{value}` from allowlist.")
    await message.reply_text("Usage: `/allowlist`, `/allowlist add <value>`, `/allowlist del <value>`")

# --- CAPTCHA/report modes ---
@app.on_message(filters.command("captchamode") & filters.group & admin_filter)
async def captchamode(_, message: Message):
    mode = message.command[1].lower() if len(message.command) > 1 else ""
    if mode not in {"button", "math", "text"}:
        return await message.reply_text("Usage: `/captchamode button|math|text`")
    await _set(message.chat.id, captcha_mode=mode)
    await message.reply_text(f"🧩 CAPTCHA mode set to **{mode}**.")

@app.on_message(filters.command("reports") & filters.group & admin_filter)
async def reports(_, message: Message):
    value = message.command[1].lower() if len(message.command) > 1 else ""
    if value not in {"on", "off", "yes", "no"}:
        return await message.reply_text("Usage: `/reports on` or `/reports off`")
    enabled = value in {"on", "yes"}
    await _set(message.chat.id, reports=enabled)
    await message.reply_text(f"🚨 Reports {'enabled' if enabled else 'disabled'}.")

# --- Join request approvals ---
@app.on_message(filters.command("approve") & filters.group & admin_filter)
async def approve(_, message: Message):
    target = await _target(message)
    if not target:
        return await message.reply_text("Reply to a join-request user or provide their ID/username.")
    try:
        await app.approve_chat_join_request(message.chat.id, target.id)
        await message.reply_text(f"✅ Approved {target.mention}.")
    except Exception as exc:
        await message.reply_text(f"❌ Could not approve: `{exc}`")

@app.on_message(filters.command("disapprove") & filters.group & admin_filter)
async def disapprove(_, message: Message):
    target = await _target(message)
    if not target:
        return await message.reply_text("Reply to a join-request user or provide their ID/username.")
    try:
        await app.decline_chat_join_request(message.chat.id, target.id)
        await message.reply_text(f"❌ Declined {target.mention}.")
    except Exception as exc:
        await message.reply_text(f"❌ Could not decline: `{exc}`")

# --- Connection mode (per-group settings lookup) ---
@app.on_message(filters.command("connect") & filters.group & admin_filter)
async def connect(_, message: Message):
    await _set(message.chat.id, connected=True)
    await message.reply_text("🔗 Connection mode enabled for this group.")

@app.on_message(filters.command("disconnect") & filters.group & admin_filter)
async def disconnect(_, message: Message):
    await _set(message.chat.id, connected=False)
    await message.reply_text("🔌 Connection mode disabled for this group.")

# --- Federation-style local ban lists ---
@app.on_message(filters.command("newfed") & filters.group & admin_filter)
async def newfed(_, message: Message):
    name = _arg(message)
    if not name:
        return await message.reply_text("Usage: `/newfed <name>`")
    fed_id = f"{message.chat.id}:{re.sub(r'[^a-zA-Z0-9_-]', '', name).lower()}"
    await fed_db.update_one({"fed_id": fed_id}, {"$set": {"name": name, "owner_id": message.from_user.id, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    await message.reply_text(f"🛡️ Federation created: **{name}**\nID: `{fed_id}`")

@app.on_message(filters.command("fedinfo") & filters.group)
async def fedinfo(_, message: Message):
    doc = await fed_db.find_one({"chat_id": message.chat.id})
    if not doc:
        doc = await fed_db.find_one({"owner_id": message.from_user.id}) if message.from_user else None
    await message.reply_text((f"🛡️ **Federation**\nName: `{doc.get('name')}`\nID: `{doc.get('fed_id')}`" if doc else "No federation configured."))

@app.on_message(filters.command("joinfed") & filters.group & admin_filter)
async def joinfed(_, message: Message):
    fed = _arg(message)
    if not fed:
        return await message.reply_text("Usage: `/joinfed <federation_id>`")
    doc = await fed_db.find_one({"fed_id": fed})
    if not doc:
        return await message.reply_text("❌ Federation not found in this bot's local registry.")
    await _set(message.chat.id, federation_id=fed)
    await message.reply_text(f"🛡️ Joined federation `{fed}`.")

@app.on_message(filters.command("leavefed") & filters.group & admin_filter)
async def leavefed(_, message: Message):
    await _set(message.chat.id, federation_id=None)
    await message.reply_text("🛡️ Left the federation.")

@app.on_message(filters.command("fedban") & filters.group & admin_filter)
async def fedban(_, message: Message):
    target = await _target(message)
    if not target:
        return await message.reply_text("Reply to or specify the user to federate-ban.")
    cfg = await _cfg(message.chat.id); fed = cfg.get("federation_id")
    if not fed:
        return await message.reply_text("This group has not joined a federation.")
    await fedban_db.update_one({"fed_id": fed, "user_id": target.id}, {"$set": {"user_id": target.id, "fed_id": fed}}, upsert=True)
    await message.reply_text(f"🌐 Globally banned {target.mention} in federation `{fed}`.")

@app.on_message(filters.command("fedunban") & filters.group & admin_filter)
async def fedunban(_, message: Message):
    target = await _target(message)
    if not target:
        return await message.reply_text("Reply to or specify the user.")
    cfg = await _cfg(message.chat.id); fed = cfg.get("federation_id")
    if not fed:
        return await message.reply_text("This group has not joined a federation.")
    await fedban_db.delete_one({"fed_id": fed, "user_id": target.id})
    await message.reply_text(f"✅ Removed {target.mention} from federation bans.")

@app.on_message(filters.command("fedlist") & filters.group & admin_filter)
async def fedlist(_, message: Message):
    cfg = await _cfg(message.chat.id); fed = cfg.get("federation_id")
    if not fed:
        return await message.reply_text("This group has not joined a federation.")
    ids = [str(d["user_id"]) async for d in fedban_db.find({"fed_id": fed}).limit(200)]
    await message.reply_text("🌐 **Federation bans:**\n" + ("\n".join(f"• `{x}`" for x in ids) if ids else "Empty."))

@app.on_message(filters.command("fedsubs") & filters.group & admin_filter)
async def fedsubs(_, message: Message):
    fed = _arg(message) or (await _cfg(message.chat.id)).get("federation_id")
    if not fed:
        return await message.reply_text("Usage: `/fedsubs <federation_id>`")
    groups = [str(d["chat_id"]) async for d in cfg_db.find({"federation_id": fed}).limit(200)]
    await message.reply_text("🌐 **Federation groups:**\n" + ("\n".join(f"• `{x}`" for x in groups) if groups else "No groups."))

# --- Useful admin utility missing from the existing command surface ---
@app.on_message(filters.command("adminlist") & filters.group)
async def adminlist(_, message: Message):
    rows = []
    try:
        async for member in app.get_chat_members(message.chat.id, filter="administrators"):
            if member.user:
                role = "owner" if member.status == ChatMemberStatus.OWNER else "admin"
                rows.append(f"• {member.user.mention} — {role}")
    except Exception as exc:
        return await message.reply_text(f"❌ Could not fetch admins: `{exc}`")
    await message.reply_text("👑 **Administrators**\n" + ("\n".join(rows) if rows else "None."))

@app.on_message(filters.command("modsettings") & filters.group & admin_filter)
async def modsettings(_, message: Message):
    cfg = await _cfg(message.chat.id)
    await message.reply_text(
        "⚙️ **Moderation settings**\n"
        f"Flood: `{cfg.get('flood', False)}` / `{cfg.get('flood_limit', 5)}`\n"
        f"Flood action: `{cfg.get('flood_action', 'mute')}`\n"
        f"Anti-link: `{cfg.get('antilink', False)}`\n"
        f"CAPTCHA: `{cfg.get('captcha', False)}` / `{cfg.get('captcha_mode', 'button')}`\n"
        f"Reports: `{cfg.get('reports', True)}`\n"
        f"Federation: `{cfg.get('federation_id') or 'none'}`"
    )

# --- ProtectiveBot/TeleSeed-style group registry and broadcast commands ---
@app.on_message(filters.command("addgroup") & filters.group & admin_filter)
async def addgroup(_, message: Message):
    await _set(message.chat.id, registered=True, registered_at=datetime.now(timezone.utc))
    await message.reply_text("✅ This group is registered with AquaVibe management.")

@app.on_message(filters.command("removegroup") & filters.group & admin_filter)
async def removegroup(_, message: Message):
    await _set(message.chat.id, registered=False)
    await message.reply_text("✅ This group was removed from the management registry.")

@app.on_message(filters.command("groupstatus") & filters.group)
async def groupstatus(_, message: Message):
    cfg = await _cfg(message.chat.id)
    await message.reply_text(
        f"📋 **Group status**\nID: `{message.chat.id}`\n"
        f"Registered: `{cfg.get('registered', False)}`\n"
        f"Federation: `{cfg.get('federation_id') or 'none'}`"
    )

@app.on_message(filters.command("banlist") & filters.group & admin_filter)
async def banlist(_, message: Message):
    rows = []
    try:
        async for member in app.get_chat_members(message.chat.id, filter="banned"):
            if member.user:
                rows.append(f"• `{member.user.id}` — {member.user.mention}")
                if len(rows) >= 100:
                    break
    except Exception as exc:
        return await message.reply_text(f"❌ Could not fetch ban list: `{exc}`")
    await message.reply_text("🚫 **Banned users**\n" + ("\n".join(rows) if rows else "No banned users found."))

@app.on_message(filters.command("setfloodwindow") & filters.group & admin_filter)
async def setfloodwindow(_, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit() or not 1 <= int(message.command[1]) <= 60:
        return await message.reply_text("Usage: `/setfloodwindow 5` (1–60 seconds)")
    await _set(message.chat.id, flood_window=int(message.command[1]))
    await message.reply_text(f"🌊 Flood window set to **{message.command[1]} seconds**.")
