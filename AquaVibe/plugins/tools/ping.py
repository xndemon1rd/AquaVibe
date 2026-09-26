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
from AquaVibe.utils.premium_emoji import custom_emoji_entities
from config import BANNED_USERS


@app.on_message(filters.command("ping", prefixes=["/", "."]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = datetime.now()
    # Restore the original AquaVibe ping animation.
    AQUA_GIF = "https://files.catbox.moe/ge1piy.gif"
    response = await message.reply_animation(
        animation=AQUA_GIF,
        caption=_["ping_1"].format(app.mention),
        caption_entities=custom_emoji_entities(_["ping_1"].format(app.mention), blockquote=True),
    )
    pytgping = await StreamController.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = (datetime.now() - start).microseconds / 1000
    await response.edit_caption(
        caption=_["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, pytgping),
        caption_entities=custom_emoji_entities(_["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, pytgping), blockquote=True),
        reply_markup=supp_markup(_),
    )
