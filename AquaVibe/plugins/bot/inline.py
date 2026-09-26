# Authored By Dev © 2025
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
)
from AquaVibe.core.runtime import AlternativeMedia

from AquaVibe.utils.inlinequery import answer
from config import BANNED_USERS
from AquaVibe.core.runtime import app
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton


@app.on_inline_query(~BANNED_USERS)
async def inline_query_handler(client, query):
    text = query.query.strip().lower()
    answers = []
    if text.strip() == "":
        try:
            await client.answer_inline_query(query.id, results=answer, cache_time=10)
        except Exception:
            return
    else:
        try:
            details, track_id = await AlternativeMedia.search(text)
            title = details.get("title", "Unknown").title()
            duration = details.get("duration_min", "Unknown")
            thumbnail = details.get("thumb") or "https://files.catbox.moe/veykzq.jpg"
            link = details.get("link") or "https://odysee.com/"
            description = f"{duration} minutes | Alternative Media"
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="Oᴘᴇɴ 🎵", url=link)]]
            )
            searched_text = f"""
❄ <b>ᴛɪᴛʟᴇ :</b> <a href={link}>{title}</a>

⏳ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> {duration} ᴍɪɴᴜᴛᴇs
🎵 <b>sᴏᴜʀᴄᴇ :</b> Alternative Media

<u><b>➻ ɪɴʟɪɴᴇ sᴇᴀʀᴄʜ ᴍᴏᴅᴇ ʙʏ {app.name}</b></u>"""
            answers.append(
                InlineQueryResultPhoto(
                    photo_url=thumbnail,
                    title=title,
                    thumb_url=thumbnail,
                    description=description,
                    caption=searched_text,
                    reply_markup=buttons,
                )
            )
        except Exception:
            answers = []
        try:
            return await client.answer_inline_query(query.id, results=answers)
        except Exception:
            return
