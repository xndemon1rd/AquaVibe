# Authored By Dev © 2025
from AquaVibe.utils.playback_card import now_playing_text
import asyncio
import html
import random
import config
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup
from config import (
    BANNED_USERS,
    lyrical,
    STREAM_IMG_URL,
    SUPPORT_CHAT,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
)
from strings import get_string
from AquaVibe.core.runtime import app, AlternativeMedia
from AquaVibe.core.call import StreamController
from AquaVibe.misc import db
from AquaVibe.utils.database import (
    get_active_chats,
    get_assistant,
    get_lang,
    is_active_chat,
    is_music_playing,
    music_off,
    music_on,
    set_loop,
)
from AquaVibe.utils.decorators import ActualAdminCB, languageCB
from AquaVibe.utils.formatters import seconds_to_min
from AquaVibe.utils.inline import close_markup, stream_markup, volume_menu_markup
from AquaVibe.utils.stream.autoclear import auto_clean
from AquaVibe.utils.stream.stream import stream as start_video_stream

MUSIC_HELP_TEXT = (
    "🧾 <b>AquaVibe Music Help</b>\n\n"
    "▶️ <code>/play [song/url]</code> — play audio in this chat's voice chat\n"
    "📹 <code>/vplay [song/url]</code> — play video in this chat's voice chat\n"
    "⏸ <code>/pause</code> · ▶️ <code>/resume</code> · ⏭ <code>/skip</code> · ⏹ <code>/stop</code>\n"
    "🔁 <code>/loop [n]</code> · 🔀 <code>/shuffle</code>\n"
    "📋 <code>/queue</code> — show what's playing and queued\n"
    "🔎 <code>/seek</code> / <code>/seekback</code> — jump forward/back\n"
    "🎚 <code>/speed</code> — change playback speed\n"
    "📝 <code>/lyrics [song]</code> — fetch lyrics\n\n"
    "Use the buttons on the Now Playing card for quick access to all of these."
)


def _lazy_lyrics_query():
    # Imported lazily to avoid any import-order issues with the plugin loader.
    from AquaVibe.plugins.misc.user_features import _lyrics_query
    return _lyrics_query


checker = {}


def parse_chat_info(chat_info: str):
    if "_" in chat_info:
        parts = chat_info.split("_")
        return int(parts[0]), parts[1]
    return int(chat_info), None


@app.on_callback_query(filters.regex("unban_assistant"))
async def unban_assistant(_, callback: CallbackQuery):
    chat_id = callback.message.chat.id
    userbot = await get_assistant(chat_id)
    try:
        await app.unban_chat_member(chat_id, userbot.id)
        await callback.answer(
            "ᴍʏ ᴀssɪsᴛᴀɴᴛ ɪᴅ ᴜɴʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ🥰🥳\n\n➻ ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ sᴏɴɢs🫠🔉\n\nTʜᴀɴᴋ ʏᴏᴜ💗",
            show_alert=True,
        )
    except Exception:
        await callback.answer(
            "Fᴀɪʟᴇᴅ ᴛᴏ ᴜɴʙᴀɴ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʙᴇᴄᴀᴜsᴇ ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ʙᴀɴ ᴘᴏᴡᴇʀ\n\n➻ Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ʙᴀɴ ᴘᴏᴡᴇʀ sᴏ ᴛʜᴀᴛ ɪ ᴄᴀɴ ᴜɴʙᴀɴ ᴍʏ ᴀssɪsᴛᴀɴᴛ ɪᴅ",
            show_alert=True,
        )


@app.on_callback_query(filters.regex("stream_admin") & ~BANNED_USERS)
@languageCB
async def manage_callback(client, callback: CallbackQuery, _):
    data = callback.data.strip().split(None, 1)[1]
    command, chat_info = data.split("|", 1)
    chat_id, counter = parse_chat_info(chat_info)
    if not await is_active_chat(chat_id):
        return await callback.answer(_["general_5"], show_alert=True)
    user_mention = callback.from_user.mention
    
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await callback.answer(_["admin_1"], show_alert=True)
        await callback.answer()
        await music_off(chat_id)
        await StreamController.pause_stream(chat_id)
        await callback.message.reply_text(_["admin_2"].format(user_mention), reply_markup=close_markup(_))

    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await callback.answer(_["admin_3"], show_alert=True)
        await callback.answer()
        await music_on(chat_id)
        await StreamController.resume_stream(chat_id)
        await callback.message.reply_text(_["admin_4"].format(user_mention), reply_markup=close_markup(_))

    elif command in ["Stop", "End"]:
        await callback.answer()
        await StreamController.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await callback.message.reply_text(_["vc_ended"].format(user_mention))
        await callback.message.delete()

    elif command == "Loop":
        await callback.answer()
        await set_loop(chat_id, 3)
        await callback.message.reply_text(_["admin_41"].format(user_mention, 3))

    elif command == "Shuffle":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["admin_42"], show_alert=True)
        try:
            popped = playlist.pop(0)
        except Exception:
            return await callback.answer(_["admin_43"], show_alert=True)
        if not playlist:
            playlist.insert(0, popped)
            return await callback.answer(_["admin_43"], show_alert=True)
        await callback.answer()
        random.shuffle(playlist)
        playlist.insert(0, popped)
        await callback.message.reply_text(_["admin_44"].format(user_mention))

    elif command in ["Skip", "Replay"]:
        await handle_skip_replay(callback, _, chat_id, command, user_mention)

    elif command == "Queue":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["queue_2"], show_alert=True)
        await callback.answer()
        lines = []
        for i, track in enumerate(playlist[:15], 1):
            title = html.escape(str(track.get("title", "Unknown")).title()[:45])
            dur = html.escape(str(track.get("dur", "—")))
            by = html.escape(str(track.get("by", "—")))
            tag = "▶️ <b>Now Playing</b>" if i == 1 else f"{i}."
            lines.append(f"{tag} {title} • {dur} • req by {by}")
        extra = f"\n…and {len(playlist) - 15} more" if len(playlist) > 15 else ""
        await callback.message.reply_text("📋 <b>Queue</b>\n\n" + "\n".join(lines) + extra)

    elif command == "VolumeMenu":
        await callback.answer()
        try:
            await callback.edit_message_reply_markup(InlineKeyboardMarkup(volume_menu_markup(_, chat_id)))
        except Exception:
            pass

    elif command == "VolumeBack":
        await callback.answer()
        try:
            await callback.edit_message_reply_markup(InlineKeyboardMarkup(stream_markup(_, chat_id)))
        except Exception:
            pass

    elif command == "SetVolume":
        volume = int(counter) if counter and str(counter).lstrip("-").isdigit() else 80
        try:
            ok = await StreamController.change_volume(chat_id, volume)
        except Exception:
            ok = False
        if not ok:
            await callback.answer(
                "⚠️ Volume control isn't supported by this PyTgCalls build.", show_alert=True
            )
        else:
            await callback.answer("🔇 Muted" if volume == 0 else f"🔊 Volume set to {volume}%")
        try:
            await callback.edit_message_reply_markup(InlineKeyboardMarkup(stream_markup(_, chat_id)))
        except Exception:
            pass

    elif command == "Vplay":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["queue_2"], show_alert=True)
        current = playlist[0]
        vidid = current.get("vidid")
        file_path = str(current.get("file", ""))
        if not vidid or vidid == "telegram" or any(m in file_path for m in ("vid_", "live_", "index_")):
            return await callback.answer("📹 Video playback isn't available for this track.", show_alert=True)
        if str(current.get("streamtype")) == "video":
            return await callback.answer("📹 Already playing in video mode.", show_alert=True)
        await callback.answer("📹 Switching to video…")
        try:
            details, _track_id = await AlternativeMedia.track(vidid)
        except Exception:
            return await callback.message.reply_text("❌ Couldn't fetch the video version of this track.")
        mystic = await callback.message.reply_text("📹 Starting video playback…")
        try:
            await start_video_stream(
                _,
                mystic,
                callback.from_user.id,
                details,
                chat_id,
                callback.from_user.first_name,
                callback.message.chat.id,
                video=True,
                streamtype="alternative_media",
                forceplay=True,
            )
        finally:
            try:
                await mystic.delete()
            except Exception:
                pass

    elif command == "Lyrics":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["queue_2"], show_alert=True)
        title = str(playlist[0].get("title", "")).strip()
        if not title:
            return await callback.answer("❌ No track title to search lyrics for.", show_alert=True)
        await callback.answer("🎤 Searching lyrics…")
        try:
            result = await _lazy_lyrics_query()(title)
        except Exception:
            result = None
        if not result:
            return await callback.message.reply_text("❌ Lyrics not found for this track.")
        ltitle, artist, lyrics = result
        header = (
            f"🎤 <b>{html.escape(ltitle)}</b>\n👤 {html.escape(artist)}\n\n"
            if artist
            else f"🎤 <b>{html.escape(ltitle)}</b>\n\n"
        )
        await callback.message.reply_text(header + html.escape(lyrics[:3500]))

    elif command == "PHelp":
        await callback.answer()
        await callback.message.reply_text(MUSIC_HELP_TEXT)

    else:
        await handle_seek(callback, _, chat_id, command, user_mention)


async def handle_skip_replay(callback: CallbackQuery, _, chat_id: int, command: str, user_mention: str):
    playlist = db.get(chat_id)

    if not playlist or len(playlist) == 0:
        return await callback.answer(_["queue_2"], show_alert=True)

    if command == "Skip":
        text_msg = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"
        try:
            popped = playlist.pop(0)
            if popped:
                await auto_clean(popped)
            if not playlist:
                await callback.edit_message_text(text_msg)
                await callback.message.reply_text(
                    _["admin_6"].format(user_mention, callback.message.chat.title),
                    reply_markup=close_markup(_)
                )
                return await StreamController.stop_stream(chat_id)
        except Exception:
            await callback.edit_message_text(text_msg)
            await callback.message.reply_text(
                _["admin_6"].format(user_mention, callback.message.chat.title),
                reply_markup=close_markup(_)
            )
            return await StreamController.stop_stream(chat_id)
    else:
        text_msg = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"

    await callback.answer()

    if len(playlist) == 0:
        return await callback.answer(_["queue_2"], show_alert=True)

    current_track = playlist[0]
    queued = current_track["file"]
    title = current_track["title"].title()
    user = current_track["by"]
    duration = current_track["dur"]
    streamtype = current_track["streamtype"]
    videoid = current_track["vidid"]
    status = True if str(streamtype) == "video" else None

    db[chat_id][0]["played"] = 0
    if current_track.get("old_dur"):
        db[chat_id][0]["dur"] = current_track["old_dur"]
        db[chat_id][0]["seconds"] = current_track["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0

    if any(marker in str(queued) for marker in ("vid_", "live_", "index_")):
        return await callback.message.reply_text(_["call_6"])

    image = None if videoid == "telegram" else config.PLAYLIST_IMG_URL
    try:
        await StreamController.skip_stream(chat_id, queued, video=status, image=image)
    except Exception:
        return await callback.message.reply_text(_["call_6"])

    buttons = stream_markup(_, chat_id)
    run = await callback.message.reply_photo(
        photo=config.PLAYBACK_CARD_IMG,
        caption=now_playing_text(
            title=title, artist="Artist Name", position="#1", requested_by=user,
            elapsed="01:24", duration=str(duration), volume="80%"
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    db[chat_id][0]["mystic"] = run
    db[chat_id][0]["markup"] = "tg" if videoid == "telegram" else "stream"
    await callback.edit_message_text(text_msg, reply_markup=close_markup(_))



async def handle_seek(callback: CallbackQuery, _, chat_id: int, command: str, user_mention: str):
    playing = db.get(chat_id)
    if not playing or len(playing) == 0:
        return await callback.answer(_["queue_2"], show_alert=True)
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return await callback.answer(_["admin_22"], show_alert=True)
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return await callback.answer(_["admin_22"], show_alert=True)
    duration_played = int(playing[0]["played"])
    duration_to_skip = 10 if int(command) in [1, 2] else 30
    duration = playing[0]["dur"]
    if int(command) in [1, 3]:
        if (duration_played - duration_to_skip) <= 10:
            bet = seconds_to_min(duration_played)
            return await callback.answer(
                f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
                f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs.",
                show_alert=True
            )
        to_seek = duration_played - duration_to_skip + 1
    else:
        if (duration_seconds - (duration_played + duration_to_skip)) <= 10:
            bet = seconds_to_min(duration_played)
            return await callback.answer(
                f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
                f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs.",
                show_alert=True
            )
        to_seek = duration_played + duration_to_skip + 1
    await callback.answer()
    mystic = await callback.message.reply_text(_["admin_24"])
    if "vid_" in file_path:
        return await mystic.edit_text(_["admin_22"])
    try:
        await StreamController.seek_stream(
            chat_id,
            file_path,
            seconds_to_min(to_seek),
            duration,
            playing[0]["streamtype"],
        )
    except Exception:
        return await mystic.edit_text(_["admin_26"])
    if int(command) in [1, 3]:
        db[chat_id][0]["played"] -= duration_to_skip
    else:
        db[chat_id][0]["played"] += duration_to_skip
    seek_message = _["admin_25"].format(seconds_to_min(to_seek))
    await mystic.edit_text(f"{seek_message}\n\nᴄʜᴀɴɢᴇs ᴅᴏɴᴇ ʙʏ : {user_mention} !")


@app.on_callback_query(filters.regex("close") & ~BANNED_USERS)
async def close_menu(_, query: CallbackQuery):
    try:
        await query.answer()
        await query.message.delete()
        msg = await query.message.reply_text(f"✅ ᴄʟᴏꜱᴇᴅ ʙʏ : {query.from_user.mention}")
        await asyncio.sleep(2)
        await msg.delete()
    except Exception:
        pass


@app.on_callback_query(filters.regex("stop_downloading") & ~BANNED_USERS)
@ActualAdminCB
async def stop_download(_, query: CallbackQuery, _lang):
    task = lyrical.get(query.message.id)
    if not task:
        return await query.answer(_lang["tg_4"], show_alert=True)
    if task.done() or task.cancelled():
        return await query.answer(_lang["tg_5"], show_alert=True)
    try:
        task.cancel()
        lyrical.pop(query.message.id, None)
        await query.answer(_lang["tg_6"], show_alert=True)
        return await query.edit_message_text(_lang["tg_7"].format(query.from_user.mention))
    except Exception:
        return await query.answer(_lang["tg_8"], show_alert=True)
