from pyrogram import filters, enums
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import Message
from AquaVibe.core.runtime import app


async def _is_group_admin(client, message: Message):
    if message.chat.type not in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        return False
    if not message.from_user:
        return False
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER)


@app.on_message(filters.command(["link", "givelink"], prefixes=["/", "!", ".", "#", "?"]))
async def invite_link(client, message: Message):
    try:
        if not await _is_group_admin(client, message):
            return await message.reply_text("🚫 Only group admins can use this command.")
        try:
            link = await client.export_chat_invite_link(message.chat.id)
        except FloodWait as e:
            return await message.reply_text(f"⏳ Please wait {e.value} seconds and try again.")
        except ChatAdminRequired:
            return await message.reply_text("🚫 蒼響 needs permission to invite users in this group.")
        await message.reply_text(
            f"🔗 **Invite link for {message.chat.title or 'this group'}:**\n{link}",
            disable_web_page_preview=True,
        )
    except Exception:
        await message.reply_text("❌ I couldn't generate an invite link. Make sure 蒼響 is an admin with invite permissions.")
