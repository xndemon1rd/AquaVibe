# AquaVibe /id command
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from AquaVibe.core.runtime import app


@app.on_message(filters.command("id"))
async def get_id(client, message: Message):
    """Show the technical Telegram IDs for the current message/chat/reply."""
    out = [
        "ᴀqᴜᴀ ᴠɪʙᴇꜱ ∞",
        "",
        f"👤 User: `{message.from_user.id if message.from_user else 'N/A'}`",
        f"💬 Chat: `{message.chat.id if message.chat else 'N/A'}`",
    ]

    if message.reply_to_message:
        out.append(f"↩️ Replied Message: `{message.reply_to_message.id}`")

    await message.reply_text(
        "\n".join(out),
        disable_web_page_preview=True,
        parse_mode=ParseMode.MARKDOWN,
    )
