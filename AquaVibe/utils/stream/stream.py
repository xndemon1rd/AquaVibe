# Authored By Dev © 2025
import os
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup

import config
from AquaVibe.core.runtime import Carbon, AlternativeMedia, app
from AquaVibe.core.call import StreamController
from AquaVibe.misc import db
from AquaVibe.utils.database import add_active_video_chat, is_active_chat
from AquaVibe.utils.exceptions import AssistantErr
from AquaVibe.utils.inline import aq_markup, close_markup, stream_markup
from AquaVibe.utils.pastebin import AquaVibeBIN
from AquaVibe.utils.stream.queue import put_queue, put_queue_index
from AquaVibe.utils.formatters import seconds_to_min
from AquaVibe.utils.thumbnails import get_thumb
from AquaVibe.utils.errors import capture_internal_err


@capture_internal_err
async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
) -> None:
    if not result:
        return

    forceplay = bool(forceplay)
    is_video = bool(video)

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        position = 0

        for search in result:
            if count >= config.PLAYLIST_FETCH_LIMIT:
                break
            try:
                details, track_id = await AlternativeMedia.search(str(search))
            except Exception:
                continue

            title = details.get("title", "Unknown")
            duration_min = details.get("duration_min")
            duration_sec = details.get("duration_sec") or 0
            if not duration_min or (duration_sec and duration_sec > config.DURATION_LIMIT):
                continue

            try:
                file_path, direct = await AlternativeMedia.download(details.get("link", ""), title=title)
            except Exception:
                continue
            if not file_path:
                continue

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id, original_chat_id, file_path, title, duration_min,
                    user_name, details.get("vidid") or track_id, user_id, "audio"
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                await put_queue(
                    chat_id, original_chat_id, file_path, title, duration_min,
                    user_name, details.get("vidid") or track_id, user_id, "audio",
                    forceplay=forceplay,
                )
                await StreamController.join_call(
                    chat_id, original_chat_id, file_path, video=False
                )
                count += 1
                position = len(db.get(chat_id)) - 1

        if count == 0:
            return
        link = await AquaVibeBIN(msg)
        lines = msg.count("\n")
        car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
        try:
            carbon = await Carbon.generate(car, randint(100, 10000000))
            playlist_photo = carbon
        except Exception:
            playlist_photo = config.PLAYLIST_IMG_URL
        upl = close_markup(_)
        final_position = max(len(db.get(chat_id) or []) - 1, 0)
        return await app.send_photo(
            original_chat_id,
            photo=playlist_photo,
            caption=_['play_21'].format(final_position, link),
            reply_markup=upl,
        )

    elif streamtype == "alternative_media":
        title = str(result.get("title") or "Alternative Provider Track")
        duration_min = result.get("duration_min") or seconds_to_min(result.get("duration_sec") or 0)
        link = result.get("link") or ""
        if not link:
            raise AssistantErr("Alternative media provider returned no playable source URL.")
        try:
            file_path, direct = await AlternativeMedia.download(link, title=title, video=is_video)
        except Exception as exc:
            raise AssistantErr(f"Media source download failed: {exc}") from exc
        if not file_path:
            raise AssistantErr("Alternative media provider returned an empty media source.")

        media_kind = "video" if is_video else "audio"
        if await is_active_chat(chat_id):
            had_queue = bool(db.get(chat_id))
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min,
                user_name, result.get("vidid") or link, user_id, media_kind,
            )
            # If the active-chat flag survived a failed/ended stream, the old
            # code only queued the new song and waited for a StreamEnded event
            # that would never arrive. Start the first queued item immediately.
            if not had_queue:
                # First queue item is the current stream. Call.play() is the
                # StreamEnded/next-track transition and pops the current item
                # before reading the next one, so using it here would discard
                # the only queued song. Start the queued item directly instead.
                await StreamController.join_call(
                    chat_id, original_chat_id, file_path, video=is_video
                )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_['queue_4'].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min,
                user_name, result.get("vidid") or link, user_id, media_kind,
                forceplay=forceplay,
            )
            await StreamController.join_call(
                chat_id, original_chat_id, file_path, video=is_video
            )
            if is_video:
                await add_active_video_chat(chat_id)
            button = stream_markup(_, chat_id)
            run = await app.send_message(
                original_chat_id,
                text=(
                    "✦ <b>蒼響 // NOW PLAYING</b> ✦\n\n"
                    f"🎵 <b>{title[:60]}</b>\n"
                    f"⏱ <code>{duration_min}</code>  •  👤 {user_name}\n\n"
                    "◈ <b>VOICE STREAM ONLINE</b>\n"
                    "⚡ Audio is now being transmitted to the voice chat."
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            had_queue = bool(db.get(chat_id))
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
            )
            if not had_queue:
                # First queue item is the current stream. Call.play() is the
                # StreamEnded/next-track transition and pops the current item
                # before reading the next one, so using it here would discard
                # the only queued song. Start the queued item directly instead.
                await StreamController.join_call(
                    chat_id, original_chat_id, file_path, video=is_video
                )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            await StreamController.join_call(
                chat_id, original_chat_id, file_path, video=is_video
            )
            if is_video:
                await add_active_video_chat(chat_id)
            button = stream_markup(_, chat_id)
            run = await app.send_message(
                original_chat_id,
                text=(
                    "✦ <b>蒼響 // NOW PLAYING</b> ✦\n\n"
                    f"🎵 <b>{title[:60]}</b>\n"
                    f"⏱ <code>{duration_min}</code>  •  👤 {user_name}\n\n"
                    "◈ <b>VOICE STREAM ONLINE</b>\n"
                    "⚡ Audio is now being transmitted to the voice chat."
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            await StreamController.join_call(
                chat_id,
                original_chat_id,
                link,
                video=is_video,
            )
            button = stream_markup(_, chat_id)
            run = await app.send_message(
                original_chat_id,
                text=(
                    "✦ <b>蒼響 // STREAM ONLINE</b> ✦\n\n"
                    f"🔗 <b>Live source connected</b>  •  👤 {user_name}\n\n"
                    "◈ <b>VOICE PIPELINE ACTIVE</b>\n"
                    "⚡ Audio is being transmitted to the voice chat."
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
