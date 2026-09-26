# Authored By Dev © 2025
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from AquaVibe.core.runtime import app
from AquaVibe.core.call import StreamController
from AquaVibe.misc import db
from AquaVibe.utils.database import get_loop
from AquaVibe.utils.decorators import AdminRightsCheck
from AquaVibe.utils.inline import close_markup, stream_markup
from AquaVibe.utils.stream.autoclear import auto_clean
from config import BANNED_USERS


@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if not len(message.command) < 2:
        loop = await get_loop(chat_id)
        if loop != 0:
            return await message.reply_text(_["admin_8"])
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            check = db.get(chat_id)
            if check:
                count = len(check)
                if count > 2:
                    count = int(count - 1)
                    if 1 <= state <= count:
                        for x in range(state):
                            popped = None
                            try:
                                popped = check.pop(0)
                            except Exception:
                                return await message.reply_text(_["admin_12"])
                            if popped:
                                await auto_clean(popped)
                            if not check:
                                try:
                                    await message.reply_text(
                                        text=_["admin_6"].format(
                                            message.from_user.mention,
                                            message.chat.title,
                                        ),
                                        reply_markup=close_markup(_),
                                    )
                                    await StreamController.stop_stream(chat_id)
                                except Exception:
                                    return
                                break
                    else:
                        return await message.reply_text(_["admin_11"].format(count))
                else:
                    return await message.reply_text(_["admin_10"])
            else:
                return await message.reply_text(_["queue_2"])
        else:
            return await message.reply_text(_["admin_9"])
    else:
        check = db.get(chat_id)
        popped = None
        try:
            if check:
                popped = check.pop(0)
            if popped:
                await auto_clean(popped)
            if not check:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                try:
                    return await StreamController.stop_stream(chat_id)
                except Exception:
                    return
        except Exception:
            try:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                return await StreamController.stop_stream(chat_id)
            except Exception:
                return
    
    if not check:
        return
    
    queued = check[0]["file"]
    title = (check[0]["title"]).title()
    user = check[0]["by"]
    streamtype = check[0]["streamtype"]
    videoid = check[0]["vidid"]
    status = True if str(streamtype) == "video" else None
    db[chat_id][0]["played"] = 0
    exis = (check[0]).get("old_dur")
    if exis:
        db[chat_id][0]["dur"] = exis
        db[chat_id][0]["seconds"] = check[0]["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0
    else:
        if videoid == "telegram":
            image = None
        else:
            image = config.PLAYLIST_IMG_URL
        try:
            await StreamController.skip_stream(chat_id, queued, video=status, image=image)
        except Exception:
            return await message.reply_text(_["call_6"])
        if videoid == "telegram":
            button = stream_markup(_, chat_id)
            run = await message.reply_text(
                text=(
                    "✦ <b>蒼響 // NOW PLAYING</b> ✦\n\n"
                    f"🎵 <b>{title[:60]}</b>\n"
                    f"⏱ <code>{check[0]["dur"]}</code>  •  👤 {user}\n\n"
                    "◈ <b>VOICE STREAM ONLINE</b>"
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            button = stream_markup(_, chat_id)
            img = config.PLAYLIST_IMG_URL
            run = await message.reply_text(
                text=(
                    "✦ <b>蒼響 // NOW PLAYING</b> ✦\n\n"
                    f"🎵 <b>{title[:60]}</b>\n"
                    f"⏱ <code>{check[0]["dur"]}</code>  •  👤 {user}\n\n"
                    "◈ <b>VOICE STREAM ONLINE</b>"
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
