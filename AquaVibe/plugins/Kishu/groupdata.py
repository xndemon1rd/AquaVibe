import time
from pyrogram import filters, enums
from pyrogram.types import Message
from AquaVibe.core.runtime import app


@app.on_message(~filters.private & filters.command("groupdata"), group=2)
async def groupdata_handler(client, message: Message):
    if not message.from_user:
        return
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
            return await message.reply_text("🚫 Only group admins can use /groupdata.")
    except Exception:
        return await message.reply_text("❌ I couldn't verify your admin status.")

    started = time.perf_counter()
    status = await message.reply_text("🔍 Gathering group data...")
    try:
        chat = await client.get_chat(message.chat.id)
        total = getattr(chat, "members_count", None) or 0
        stats = {"admins": 0, "bots": 0, "deleted": 0, "premium": 0, "restricted": 0}

        try:
            async for m in client.get_chat_members(message.chat.id):
                user = m.user
                if not user:
                    continue
                if user.is_deleted:
                    stats["deleted"] += 1
                    continue
                if user.is_bot:
                    stats["bots"] += 1
                if getattr(user, "is_premium", False):
                    stats["premium"] += 1
                if m.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
                    stats["admins"] += 1
                if m.status == enums.ChatMemberStatus.RESTRICTED:
                    stats["restricted"] += 1
        except Exception:
            pass

        took = time.perf_counter() - started
        title = chat.title or "This Group"
        text = (
            f"<b>📊 Group Data</b>\n"
            f"<b>Group:</b> {title}\n"
            f"<b>Members:</b> <code>{total:,}</code>\n"
            f"<b>Admins:</b> <code>{stats['admins']:,}</code>\n"
            f"<b>Bots:</b> <code>{stats['bots']:,}</code>\n"
            f"<b>Deleted:</b> <code>{stats['deleted']:,}</code>\n"
            f"<b>Premium:</b> <code>{stats['premium']:,}</code>\n"
            f"<b>Restricted:</b> <code>{stats['restricted']:,}</code>\n"
            f"<b>Scan time:</b> <code>{took:.2f}s</code>"
        )
        await status.edit_text(text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    except Exception:
        await status.edit_text("❌ I couldn't collect this group's data. Make sure 蒼響 has permission to read members.")
