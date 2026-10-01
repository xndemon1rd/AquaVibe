# Authored By Dev © 2025
import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from AquaVibe.core.runtime import app
from config import SUPPORT_CHAT
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
InlineKeyboardButton = ColoredInlineKeyboardButton

BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton("ꜱᴜᴘᴘᴏʀᴛ", url=SUPPORT_CHAT)]])

MEDIA = {
    "cutie": "https://graph.org/file/24375c6e54609c0e4621c.mp4",
    "gay": "https://graph.org/file/850290f1f974c5421ce54.mp4",
    "lesbian": "https://graph.org/file/ff258085cf31f5385db8a.mp4",
}

TEMPLATES = {
    "cutie": "🍑 {mention} ɪꜱ {percent}% ᴄᴜᴛᴇ ʙᴀʙʏ🥀",
    "gay": "🍷 {mention} ɪꜱ {percent}% ɢᴀʏ!",
    "lesbian": "💜 {mention} ɪꜱ {percent}% ʟᴇꜱʙɪᴀɴ!",
}


def get_user_mention(message: Message) -> str:
    user = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    if user is None:  # anonymous admin / channel post
        return "Someone"
    return f"[{user.first_name}](tg://user?id={user.id})"


def get_reply_id(message: Message) -> int | None:
    return message.reply_to_message.id if message.reply_to_message else None


async def handle_percentage_command(_, message: Message):
    command = message.command[0].lower()
    if command not in MEDIA or command not in TEMPLATES:
        return

    mention = get_user_mention(message)
    percent = random.randint(1, 100)
    text = TEMPLATES[command].format(mention=mention, percent=percent)
    media_url = MEDIA[command]
    reply_id = get_reply_id(message)

    # The hosted GIF/MP4 links can go stale; never let a dead link break the
    # command. Try the media first, then fall back to a plain text reply.
    try:
        await app.send_animation(
            message.chat.id,
            media_url,
            caption=text,
            reply_markup=BUTTON,
            reply_to_message_id=reply_id,
        )
    except Exception:
        await message.reply_text(text, reply_markup=BUTTON, quote=True)


for cmd in ["cutie", "gay", "lesbian"]:
    app.on_message(filters.command(cmd))(handle_percentage_command)
