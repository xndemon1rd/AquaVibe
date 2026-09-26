"""Community-management features inspired by common open-source Telegram bots.

Implemented from documented feature ideas, not copied source code:
- AFK with mention/reply notifications
- persistent group notes
- keyword filters with stored replies
- member tagging
- group info / member info helpers
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import Message

from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app
from AquaVibe.utils.admin_filters import admin_filter

notes_db = mongodb.group_notes
filters_db = mongodb.group_filters
afk_db = mongodb.user_afk


def _group(message: Message) -> bool:
    return bool(message.chat and message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP))


def _clean_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())[:80]


# ---------------- AFK ----------------
@app.on_message(filters.command("afk") & filters.group)
async def afk_cmd(_, message: Message):
    reason = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else "AFK"
    await afk_db.update_one(
        {"chat_id": message.chat.id, "user_id": message.from_user.id},
        {"$set": {"reason": reason[:200], "since": datetime.now(timezone.utc)}},
        upsert=True,
    )
    await message.reply_text(f"💤 {message.from_user.mention} is now AFK.\nReason: {html.escape(reason[:200])}")


@app.on_message(filters.all, group=-30)
async def afk_listener(_, message: Message):
    if not _group(message) or not message.from_user or message.from_user.is_bot:
        return

    # Clear AFK when the user speaks again.
    own = await afk_db.find_one({"chat_id": message.chat.id, "user_id": message.from_user.id})
    if own:
        await afk_db.delete_one({"chat_id": message.chat.id, "user_id": message.from_user.id})
        try:
            await message.reply_text(f"👋 Welcome back, {message.from_user.mention}! AFK removed.")
        except Exception:
            pass
        return

    target_ids = set()
    if message.reply_to_message and message.reply_to_message.from_user:
        target_ids.add(message.reply_to_message.from_user.id)
    if message.entities:
        for ent in message.entities:
            if getattr(ent, "type", None) == "text_mention" and ent.user:
                target_ids.add(ent.user.id)
            elif getattr(ent, "type", None) == "mention":
                text = message.text or ""
                try:
                    u = await app.get_users(text[ent.offset:ent.offset + ent.length])
                    target_ids.add(u.id)
                except Exception:
                    pass

    for uid in target_ids:
        doc = await afk_db.find_one({"chat_id": message.chat.id, "user_id": uid})
        if not doc:
            continue
        reason = html.escape(str(doc.get("reason") or "AFK"))
        await message.reply_text(f"💤 {message.reply_to_message.from_user.mention if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == uid else 'User'} is AFK.\nReason: {reason}")
        break


# ---------------- Notes ----------------
@app.on_message(filters.command("save") & filters.group & admin_filter)
async def save_note(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/save name` while replying to a message.")
    if not message.reply_to_message:
        return await message.reply_text("Reply to the message you want to save.")
    name = _clean_key(message.text.split(None, 1)[1])
    src = message.reply_to_message
    await notes_db.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"chat_id": message.chat.id, "name": name, "message_id": src.id}},
        upsert=True,
    )
    await message.reply_text(f"📝 Saved note `{name}`.")


@app.on_message(filters.command("get") & filters.group)
async def get_note(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/get name`")
    name = _clean_key(message.text.split(None, 1)[1])
    doc = await notes_db.find_one({"chat_id": message.chat.id, "name": name})
    if not doc:
        return await message.reply_text("❌ Note not found.")
    try:
        await app.copy_message(message.chat.id, message.chat.id, doc["message_id"])
    except Exception:
        await message.reply_text("❌ I couldn't retrieve that note anymore.")


@app.on_message(filters.command("notes") & filters.group)
async def list_notes(_, message: Message):
    names = [d.get("name") async for d in notes_db.find({"chat_id": message.chat.id}).limit(100)]
    await message.reply_text("📝 **Saved notes**\n\n" + ("\n".join(f"• `{n}`" for n in names) if names else "No notes saved."))


@app.on_message(filters.command("clear") & filters.group & admin_filter)
async def clear_note(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/clear name`")
    name = _clean_key(message.text.split(None, 1)[1])
    result = await notes_db.delete_one({"chat_id": message.chat.id, "name": name})
    await message.reply_text("✅ Note removed." if result.deleted_count else "❌ Note not found.")


# ---------------- Keyword filters ----------------
@app.on_message(filters.command("filter") & filters.group & admin_filter)
async def add_filter(_, message: Message):
    if len(message.command) < 2 or not message.reply_to_message:
        return await message.reply_text("Reply to a response message: `/filter keyword`")
    keyword = _clean_key(message.text.split(None, 1)[1])
    await filters_db.update_one(
        {"chat_id": message.chat.id, "keyword": keyword},
        {"$set": {"chat_id": message.chat.id, "keyword": keyword, "message_id": message.reply_to_message.id}},
        upsert=True,
    )
    await message.reply_text(f"🔎 Filter `{keyword}` saved.")


@app.on_message(filters.command("stop") & filters.group & admin_filter)
async def remove_filter(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/stop keyword`")
    keyword = _clean_key(message.text.split(None, 1)[1])
    result = await filters_db.delete_one({"chat_id": message.chat.id, "keyword": keyword})
    await message.reply_text("✅ Filter removed." if result.deleted_count else "❌ Filter not found.")


@app.on_message(filters.command("filters") & filters.group & admin_filter)
async def list_filters(_, message: Message):
    words = [d.get("keyword") async for d in filters_db.find({"chat_id": message.chat.id}).limit(100)]
    await message.reply_text("🔎 **Group filters**\n\n" + ("\n".join(f"• `{w}`" for w in words) if words else "No filters configured."))


@app.on_message(filters.all, group=-29)
async def keyword_filter_listener(_, message: Message):
    if not _group(message) or not message.from_user or message.from_user.is_bot:
        return
    text = (message.text or message.caption or "").casefold()
    if not text or text.startswith("/"):
        return
    docs = [d async for d in filters_db.find({"chat_id": message.chat.id}).limit(100)]
    for doc in docs:
        keyword = str(doc.get("keyword") or "").casefold()
        if keyword and keyword in text:
            try:
                await app.copy_message(message.chat.id, message.chat.id, int(doc["message_id"]))
            except Exception:
                pass
            break


# ---------------- Tagging ----------------
@app.on_message(filters.command("tagall") & filters.group & admin_filter)
async def tag_all(_, message: Message):
    custom = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else ""
    names = []
    try:
        async for member in app.get_chat_members(message.chat.id):
            user = member.user
            if not user or user.is_bot:
                continue
            if member.status in (ChatMemberStatus.RESTRICTED, ChatMemberStatus.BANNED):
                continue
            names.append(user.mention)
            if len(names) >= 150:
                break
    except Exception:
        return await message.reply_text("❌ I couldn't read the member list. Check my admin permissions.")
    if not names:
        return await message.reply_text("No members found to tag.")
    header = custom or "📢 Attention everyone!"
    # Telegram messages are limited to 4096 characters.
    chunk, chunks, size = [], [], len(header) + 2
    for name in names:
        add = len(name) + 1
        if chunk and size + add > 3800:
            chunks.append(" ".join(chunk))
            chunk, size = [], len(header) + 2
        chunk.append(name)
        size += add
    if chunk:
        chunks.append(" ".join(chunk))
    for i, body in enumerate(chunks):
        await message.reply_text((header + "\n" if i == 0 else "") + body)


# ---------------- Group / user info ----------------
@app.on_message(filters.command("groupinfo") & filters.group)
async def group_info(_, message: Message):
    chat = message.chat
    try:
        count = await app.get_chat_members_count(chat.id)
    except Exception:
        count = "?"
    text = (
        "🏠 <b>Group Info</b>\n\n"
        f"• <b>Name:</b> {html.escape(chat.title or '—')}\n"
        f"• <b>ID:</b> <code>{chat.id}</code>\n"
        f"• <b>Members:</b> <code>{count}</code>\n"
        f"• <b>Username:</b> <code>@{chat.username}</code>" if chat.username else
        "🏠 <b>Group Info</b>\n\n"
        f"• <b>Name:</b> {html.escape(chat.title or '—')}\n"
        f"• <b>ID:</b> <code>{chat.id}</code>\n"
        f"• <b>Members:</b> <code>{count}</code>"
    )
    await message.reply_text(text)


@app.on_message(filters.command("userinfo") & filters.group)
async def user_info(_, message: Message):
    user = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    if not user:
        return
    username = f"@{user.username}" if user.username else "—"
    await message.reply_text(
        "👤 <b>User Info</b>\n\n"
        f"• <b>Name:</b> {user.mention}\n"
        f"• <b>Username:</b> <code>{html.escape(username)}</code>\n"
        f"• <b>Bot:</b> <code>{user.is_bot}</code>\n"
        f"• <b>ID:</b> <code>{user.id}</code>"
    )
