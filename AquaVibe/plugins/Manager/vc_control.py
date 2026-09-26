# Authored By Dev © 2025
from pyrogram import filters
from pyrogram.types import Message

from AquaVibe.core.runtime import app
from AquaVibe.core.call import StreamController
from AquaVibe.utils.admin_filters import admin_filter
from AquaVibe.plugins.Manager.assisuser import join_userbot
from config import BANNED_USERS


@app.on_message(filters.command("vstart") & filters.group & admin_filter & ~BANNED_USERS)
async def vstart(_, message: Message):
    try:
        join_status = await join_userbot(
            app, message.chat.id, getattr(message.chat, "username", None)
        )
        if join_status.startswith("**❌"):
            await message.reply_text(join_status)
            return
        await StreamController.start_voice_chat(message.chat.id)
        await message.reply_text("🎙️ **ᴠᴏɪᴄᴇ ᴄʜᴀᴛ sᴛᴀʀᴛᴇᴅ.**\n\n🎵 ᴛʏᴘᴇ /play ᴛᴏ sᴛᴀʀᴛ ᴍᴜsɪᴄ.")
    except Exception as exc:
        await message.reply_text(str(exc))
