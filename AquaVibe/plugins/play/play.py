# Authored By Dev © 2025
import asyncio
import random
import string

from pyrogram import filters
from pyrogram.errors import FloodWait, RandomIdDuplicate
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
from pytgcalls.exceptions import NoActiveGroupCall

import config
from config import AYU, BANNED_USERS, lyrical

PLAY_RESULT_GIF = "https://files.catbox.moe/ge1piy.gif"

from AquaVibe.core.runtime import Apple, Spotify, Telegram, AlternativeMedia, app

# TEMP ROUTING DIAGNOSTIC
@app.on_message(filters.command("playtest") & ~BANNED_USERS, group=999)
async def _playtest_handler(client, message, _):
    await message.reply_text("✅ PLAY ROUTING WORKS")

from AquaVibe.core.call import StreamController
from AquaVibe.utils import seconds_to_min, time_to_seconds
from AquaVibe.utils.channelplay import get_channeplayCB
from AquaVibe.utils.decorators.language import languageCB
from AquaVibe.utils.decorators.play import PlayWrapper
from AquaVibe.utils.errors import capture_err, capture_callback_err
from AquaVibe.utils.formatters import formats
from AquaVibe.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from AquaVibe.utils.logger import play_logs, report_play_error
from AquaVibe.utils.stream.stream import stream


@app.on_message(
    filters.command(
        [
            "play",
            "vplay",
        ]
    )
    & filters.private
    & ~BANNED_USERS
)
async def play_private_info(client, message: Message, _):
    """Give a deterministic DM response instead of silently ignoring /play."""
    try:
        return await message.reply_text(
            "🎵 Music playback works in a group voice chat.\n\n"
            "Add me to a group, start a voice chat, and use /play <song> there."
        )
    except Exception as exc:
        await report_play_error(message, exc, operation="Private /play response")


@app.on_message(
    filters.command(
        [
            "play",
            "vplay",
        ]
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
@capture_err
async def play_command(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    try:
        mystic = await message.reply_text(
            _["play_2"].format(channel) if channel else random.choice(AYU)
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        mystic = await message.reply_text(
            _["play_2"].format(channel) if channel else random.choice(AYU)
        )
    except RandomIdDuplicate:
        mystic = await app.send_message(
            message.chat.id,
            _["play_2"].format(channel) if channel else random.choice(AYU),
        )

    plist_id, plist_type, spotify, slider = None, None, None, None
    internal_type, log_label = None, None
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )

    if audio_telegram:
        if audio_telegram.file_size > config.TG_AUDIO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_5"])

        duration_min = seconds_to_min(audio_telegram.duration)
        if audio_telegram.duration > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )

        file_path = await Telegram.get_filepath(audio=audio_telegram)
        downloaded = await Telegram.download(_, message, mystic, file_path)
        if downloaded:
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(audio_telegram, audio=True)
            dur = await Telegram.get_duration(audio_telegram, file_path)

            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                internal_type = "telegram"
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype=internal_type,
                    forceplay=bool(fplay),
                )
            except Exception as e:
                await report_play_error(message, e, operation=f"{internal_type or 'song'} playback")
                return

            caption_query = message.reply_to_message.caption or "—"
            await play_logs(message, streamtype="Telegram [Audio]", query=caption_query)
            return await mystic.delete()
        return

    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )

    if video_telegram:
        if message.reply_to_message.document:
            try:
                ext = (video_telegram.file_name or "").split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(
                        _["play_7"].format(" | ".join(formats))
                    )
            except Exception:
                return await mystic.edit_text(_["play_7"].format(" | ".join(formats)))

        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_8"])

        file_path = await Telegram.get_filepath(video=video_telegram)
        downloaded = await Telegram.download(_, message, mystic, file_path)
        if downloaded:
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(video_telegram)
            dur = await Telegram.get_duration(video_telegram, file_path)

            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                internal_type = "telegram"
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=True,
                    streamtype=internal_type,
                    forceplay=bool(fplay),
                )
            except Exception as e:
                await report_play_error(message, e, operation=f"{internal_type or 'song'} playback")
                return

            caption_query = message.reply_to_message.caption or "—"
            await play_logs(message, streamtype="Telegram [Video]", query=caption_query)
            return await mystic.delete()
        return

    if url:
        # HLS/M3U8 must stay a live stream. Do not send playlist URLs through
        # the file downloader; ntgcalls/FFmpeg can consume them directly.
        if AlternativeMedia.is_hls(url):
            try:
                await stream(
                    _, mystic, user_id, url, chat_id, user_name, message.chat.id,
                    video=bool(video), streamtype="index", forceplay=bool(fplay),
                )
            except Exception as e:
                await report_play_error(message, e, operation="HLS/M3U8 playback")
                return
            return await play_logs(message, streamtype="M3U8/HLS")

        if await AlternativeMedia.valid(url):
            try:
                details, track_id = await AlternativeMedia.track(url)
            except Exception as e:
                await report_play_error(message, e, operation="alternative provider source lookup")
                return

            img = details.get("thumb") or config.PLAYLIST_IMG_URL
            cap = _["play_10"].format(details["title"], details["duration_min"])
            internal_type = "alternative_media"
            log_label = "Alternative Provider Track"

        elif await Spotify.valid(url):
            spotify = True
            if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text(
                    "»  sᴘᴏᴛɪғʏ ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ."
                )

            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except Exception as e:
                    await report_play_error(message, e, operation="source lookup")
                    return

                try:
                    details, track_id = await AlternativeMedia.search(details["title"], video=bool(video))
                except Exception as e:
                    await report_play_error(message, e, operation="alternative provider source lookup")
                    return
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
                internal_type = "alternative_media"
                log_label = "Spotify Track"

            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception as e:
                    await report_play_error(message, e, operation="source lookup")
                    return

                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
                internal_type = "playlist"
                log_label = "Spotify playlist"

            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except Exception as e:
                    await report_play_error(message, e, operation="source lookup")
                    return

                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
                internal_type = "playlist"
                log_label = "Spotify album"

            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except Exception as e:
                    await report_play_error(message, e, operation="source lookup")
                    return

                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_11"].format(message.from_user.first_name)
                internal_type = "playlist"
                log_label = "Spotify artist"

            else:
                return await mystic.edit_text(_["play_15"])

        elif await Apple.valid(url):
            if "album" in url or "/song/" in url:
                try:
                    details, track_id = await Apple.track(url)
                except Exception as e:
                    await report_play_error(message, e, operation="source lookup")
                    return

                try:
                    details, track_id = await AlternativeMedia.search(details["title"], video=bool(video))
                except Exception as e:
                    await report_play_error(message, e, operation="alternative provider source lookup")
                    return
                img = details["thumb"]
                cap = _["play_10"].format(details["title"], details["duration_min"])
                internal_type = "alternative_media"
                log_label = "Apple Music"

            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Apple.playlist(url)
                except Exception as e:
                    await report_play_error(message, e, operation="source lookup")
                    return

                plist_type = "apple"
                img = url
                cap = _["play_12"].format(app.mention, message.from_user.mention)
                internal_type = "playlist"
                log_label = "Apple Music playlist"

            else:
                return await mystic.edit_text(_["play_3"])



        else:
            # Do not pre-play direct URLs in stream_call(): that helper is a
            # short startup probe which intentionally leaves the VC after a
            # few seconds. Calling it from /play made real direct streams
            # connect, play briefly, leave, and then race the queue. The normal
            # stream() path below now owns the entire VC lifecycle.
            await mystic.edit_text(_["str_2"])
            try:
                internal_type = "index"
                await stream(
                    _,
                    mystic,
                    user_id,
                    url,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=bool(video),
                    streamtype=internal_type,
                    forceplay=bool(fplay),
                )
            except Exception as e:
                await report_play_error(message, e, operation=f"{internal_type or 'song'} playback")
                return

            return await play_logs(message, streamtype="M3U8 or Index Link")

    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["play_18"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        slider = True
        query = message.text.split(None, 1)[1]
        if "-v" in query:
            query = query.replace("-v", "")

        try:
            details, track_id = await AlternativeMedia.search(query, video=bool(video))
        except Exception as e:
            await report_play_error(message, e, operation="alternative provider source lookup")
            return

        internal_type = "alternative_media"
        log_label = "Alternative Provider Track"

    if str(playmode) == "Direct":
        if not plist_type:
            if details.get("duration_min"):
                duration_sec = time_to_seconds(details["duration_min"])
                if duration_sec and duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
                    )
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                return await mystic.edit_text(
                    _["play_13"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )

        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=bool(video),
                streamtype=internal_type,
                spotify=spotify,
                forceplay=bool(fplay),
            )
        except Exception as e:
            await report_play_error(message, e, operation=f"{internal_type or 'song'} playback")
            return

        await mystic.delete()
        return await play_logs(message, streamtype=log_label)

    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                user_id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_animation(
                animation=PLAY_RESULT_GIF,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            plist_label_map = {
                "spplay": "Spotify playlist",
                "spalbum": "Spotify album",
                "spartist": "Spotify artist",
                "apple": "Apple Music playlist",
            }
            return await play_logs(
                message, streamtype=plist_label_map.get(plist_type, "Playlist")
            )

        else:
            if slider:
                buttons = slider_markup(
                    _,
                    track_id,
                    user_id,
                    query,
                    0,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                    "v" if video else "a",
                )
                await mystic.delete()
                await message.reply_animation(
                    animation=PLAY_RESULT_GIF,
                    caption=(
                        "<blockquote>"
                        "✦ <b>蒼響 // TRACK READY</b> ✦\n\n"
                        f"🎵 <b>{details["title"].title()}</b>\n"
                        f"⏱ <code>{details["duration_min"]}</code>\n\n"
                        "⚡ Select an action below to start playback."
                        "</blockquote>"
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="Searched on AlternativeMedia")

            else:
                buttons = track_markup(
                    _,
                    track_id,
                    user_id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_animation(
                    animation=PLAY_RESULT_GIF,
                    caption=(
                        "<blockquote>"
                        "✦ <b>蒼響 // TRACK READY</b> ✦\n\n"
                        f"🎵 <b>{details["title"]}</b>\n"
                        f"⏱ <code>{details["duration_min"]}</code>\n\n"
                        "⚡ Select an action below to start playback."
                        "</blockquote>"
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="URL Search Inline")


@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def play_music(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.split(None, 1)[1]
        vidid, user_id, mode, cplay, fplay = callback_data.split("|")

        if CallbackQuery.from_user.id != int(user_id):
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)

        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)

        user_name = CallbackQuery.from_user.first_name
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()

        try:
            mystic = await CallbackQuery.message.reply_text(
                _["play_2"].format(channel) if channel else random.choice(AYU)
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            mystic = await CallbackQuery.message.reply_text(
                _["play_2"].format(channel) if channel else random.choice(AYU)
            )
        except RandomIdDuplicate:
            mystic = await app.send_message(
                CallbackQuery.message.chat.id,
                _["play_2"].format(channel) if channel else random.choice(AYU),
            )

        details, track_id = await AlternativeMedia.track(vidid)

        if details.get("duration_min"):
            duration_sec = time_to_seconds(details["duration_min"])
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
                )
        else:
            buttons = livestream_markup(
                _,
                track_id,
                CallbackQuery.from_user.id,
                mode,
                "c" if cplay == "c" else "g",
                "f" if fplay else "d",
            )
            return await mystic.edit_text(
                _["play_13"], reply_markup=InlineKeyboardMarkup(buttons)
            )

        video = mode == "v"
        forceplay = fplay == "f"

        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            bool(video),
            streamtype="alternative_media",
            forceplay=bool(forceplay),
        )

        await mystic.delete()

    except Exception as e:
        await report_play_error(CallbackQuery.message, e, operation="song playback callback")
        return


@app.on_callback_query(filters.regex("AnonymousAdmin") & ~BANNED_USERS)
@capture_callback_err
async def anonymous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\n"
            "ᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n"
            "-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n"
            "-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex("AquaVibePlaylists") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def play_playlists_command(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.split(None, 1)[1]
        videoid, user_id, ptype, mode, cplay, fplay = callback_data.split("|")

        if CallbackQuery.from_user.id != int(user_id):
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)

        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
        user_name = CallbackQuery.from_user.first_name
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()

        try:
            mystic = await CallbackQuery.message.reply_text(
                _["play_2"].format(channel) if channel else random.choice(AYU)
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            mystic = await CallbackQuery.message.reply_text(
                _["play_2"].format(channel) if channel else random.choice(AYU)
            )
        except RandomIdDuplicate:
            mystic = await app.send_message(
                CallbackQuery.message.chat.id,
                _["play_2"].format(channel) if channel else random.choice(AYU),
            )

        videoid = lyrical.get(videoid)
        video = mode == "v"
        forceplay = fplay == "f"
        spotify = True

        if ptype == "spplay":
            result, _ = await Spotify.playlist(videoid)
            internal_type = "playlist"
            log_label = "Spotify playlist"
        elif ptype == "spalbum":
            result, _ = await Spotify.album(videoid)
            internal_type = "playlist"
            log_label = "Spotify album"
        elif ptype == "spartist":
            result, _ = await Spotify.artist(videoid)
            internal_type = "playlist"
            log_label = "Spotify artist"
        elif ptype == "apple":
            result, _ = await Apple.playlist(videoid, True)
            internal_type = "playlist"
            log_label = "Apple Music playlist"
        else:
            return

        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            bool(video),
            streamtype=internal_type,
            spotify=spotify,
            forceplay=bool(forceplay),
        )

        await play_logs(CallbackQuery.message, streamtype=log_label)
        await mystic.delete()

    except Exception as e:
        await report_play_error(CallbackQuery.message, e, operation="song playback callback")
        return


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
@capture_callback_err
async def slider_queries(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.split(None, 1)[1]
        parts = callback_data.split("|")
        if len(parts) == 7:
            what, rtype, query, user_id, cplay, fplay, mode = parts
        elif len(parts) == 6:
            # Backward compatibility for older slider buttons.
            what, rtype, query, user_id, cplay, fplay = parts
            mode = "a"
        else:
            return await CallbackQuery.answer("Invalid playback button.", show_alert=True)

        if CallbackQuery.from_user.id != int(user_id):
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)

        rtype = int(rtype)
        query_type = (rtype + 1) if what == "F" else (rtype - 1)

        if query_type > 9:
            query_type = 0
        if query_type < 0:
            query_type = 9

        video = mode == "v"
        details, vidid = await AlternativeMedia.search(query, video=video)
        title = details.get("title", "Unknown")
        duration_min = details.get("duration_min", "Unknown")
        buttons = slider_markup(_, vidid, user_id, query, 0, cplay, fplay, mode)
        await CallbackQuery.edit_message_text(
            text=(
                "<blockquote>"
                "✦ <b>蒼響 // TRACK READY</b> ✦\n\n"
                f"🎵 <b>{title.title()}</b>\n"
                f"⏱ <code>{duration_min}</code>\n\n"
                "⚡ Select an action below to start playback."
                "</blockquote>"
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        await CallbackQuery.answer(_["playcb_2"])

    except Exception:
        pass
