# Authored By Dev © 2025
from datetime import datetime

from pyrogram import filters
from pyrogram.types import Message
from config import *
from AquaVibe.core.runtime import app
from AquaVibe.core.call import StreamController
from AquaVibe.utils import bot_sys_stats
from AquaVibe.utils.decorators.language import language
from AquaVibe.utils.inline import supp_markup
from AquaVibe.utils.premium_emoji import custom_emoji_entities, text_link_entity
from config import BANNED_USERS

# Vanity credit shown on the ping card: a display name that links to a fixed
# Telegram user id. `app.mention` was used here before, but its markup was
# never rendered -- passing caption_entities explicitly makes Pyrogram skip
# parse_mode (and any markup baked into the string), so it showed as raw
# text. A real MessageEntity(TEXT_LINK) is required to make it clickable.
AQUA_MENTION_ID = 8641117257
AQUA_MENTION_NAME = "𝐀qᴜᴀ 𝐕ɪʙᴇ 𓆩♪𓆪"


@app.on_message(filters.command("ping", prefixes=["/", "."]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = datetime.now()
    # Restore the original AquaVibe ping animation.
    AQUA_GIF = "https://files.catbox.moe/ge1piy.gif"
    ping_1_text = _["ping_1"].format(AQUA_MENTION_NAME)
    response = await message.reply_animation(
        animation=AQUA_GIF,
        caption=ping_1_text,
        caption_entities=custom_emoji_entities(ping_1_text, blockquote=True)
        + [text_link_entity(AQUA_MENTION_NAME, f"tg://user?id={AQUA_MENTION_ID}")],
    )
    pytgping = await StreamController.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = (datetime.now() - start).microseconds / 1000
    ping_2_text = _["ping_2"].format(resp, AQUA_MENTION_NAME, UP, RAM, CPU, DISK, pytgping)
    await response.edit_caption(
        caption=ping_2_text,
        caption_entities=custom_emoji_entities(ping_2_text, blockquote=True)
        + [text_link_entity(AQUA_MENTION_NAME, f"tg://user?id={AQUA_MENTION_ID}")],
        reply_markup=supp_markup(_),
    )
