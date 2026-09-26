# Authored By Dev © 2025
import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError, ConnectionNotFound
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired, RPCError
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall, NoAudioSourceFound, NoVideoSourceFound
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality, GroupCallConfig
from pyrogram.raw.functions.phone import CreateGroupCall
import random

import config
from strings import get_string
from AquaVibe.core.runtime import LOGGER, app
from AquaVibe.misc import db
from AquaVibe.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from AquaVibe.utils.exceptions import AssistantErr
from AquaVibe.utils.formatters import check_duration, seconds_to_min, speed_converter
from AquaVibe.utils.inline.play import stream_markup
from AquaVibe.utils.stream.autoclear import auto_clean
from AquaVibe.utils.thumbnails import get_thumb
from AquaVibe.utils.errors import capture_internal_err

autoend = {}
counter = {}

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    # Fail early with a useful error instead of letting ntgcalls raise a
    # cryptic "media_path ... got NoneType" TypeError.
    if path is None or not isinstance(path, (str, os.PathLike)):
        raise AssistantErr("Invalid media source: download/stream URL is empty.")
    path = os.fspath(path)
    if not path.startswith(("http://", "https://")) and not os.path.exists(path):
        raise AssistantErr(f"Media source does not exist: {path}")
    # Keep MediaStream construction aligned with the current PyTgCalls API.
    # Do not force audio/video tracks to REQUIRED: that can make otherwise
    # playable provider files stall during WebRTC negotiation. PyTgCalls'
    # documented examples use an ignored video track for audio-only playback.
    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=ffmpeg_params,
        )
    return MediaStream(
        media_path=path,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.Flags.IGNORE,
        ffmpeg_parameters=ffmpeg_params,
    )

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

class Call:
    def __init__(self):
        # Keep the Pyrogram clients as before, but do NOT construct PyTgCalls here.
        # PyTgCalls/ntgcalls can bind asyncio futures to the event loop active at
        # construction time. This object is imported before asyncio.run(init()),
        # so constructing it here can cause "Future attached to a different loop"
        # when playback starts. PyTgCalls instances are created in start(), inside
        # the same loop used by the bot.
        # IMPORTANT: these must be the exact Pyrogram clients started by
        # core.userbot.Userbot. Creating a second set of clients here leaves
        # PyTgCalls attached to sessions that were never started, so commands
        # appear to work but voice playback cannot actually connect.
        self.userbot1 = None
        self.userbot2 = None
        self.userbot3 = None
        self.userbot4 = None
        self.userbot5 = None

        self.one = None
        self.two = None
        self.three = None
        self.four = None
        self.five = None
        self.active_calls: set[int] = set()


    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("Invalid stream info for speedup.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            # Use argv execution instead of a shell. file_path comes from Telegram/media
            # state and must never become shell syntax.
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", file_path,
                "-filter:v", f"setpts={vs}*PTS",
                "-filter:a", f"atempo={speed}",
                "-y", out,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out,
                "speed": speed,
                "old_dur": db[chat_id][0].get("dur"),
                "old_second": db[chat_id][0].get("seconds"),
            })
        else:
            raise AssistantErr("Stream mismatch during speedup.")


    @capture_internal_err
    async def start_voice_chat(self, chat_id: int) -> None:
        """Create/start a group voice chat using the selected assistant user account."""
        assistant = await group_assistant(self, chat_id)
        mtproto = assistant.mtproto_client
        try:
            peer = await mtproto.resolve_peer(chat_id)
            await mtproto.invoke(
                CreateGroupCall(
                    peer=peer,
                    random_id=random.randint(1, 2_147_483_647),
                )
            )
            self.active_calls.discard(chat_id)
        except (ChatAdminRequired, RPCError) as exc:
            text = str(exc).upper()
            if isinstance(exc, ChatAdminRequired) or "CHAT_ADMIN_REQUIRED" in text:
                raise AssistantErr("ᴠᴄ ᴘᴇʀᴍɪssɪᴏɴ ɴᴏᴛ ɢɪᴠᴇɴ. ᴍᴀᴋᴇ ᴛʜᴇ ᴀssɪsᴛᴀɴᴛ ᴀᴅᴍɪɴ ᴡɪᴛʜ ᴍᴀɴᴀɢᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs ᴘᴇʀᴍɪssɪᴏɴ.")
            if "CHANNEL_PRIVATE" in text or "PEER_ID_INVALID" in text:
                raise AssistantErr("ᴛʜᴇ ᴀssɪsᴛᴀɴᴛ ɪs ɴᴏᴛ ᴀʙʟᴇ ᴛᴏ ᴀᴄᴄᴇss ᴛʜɪs ɢʀᴏᴜᴘ.")
            raise AssistantErr(f"ᴜɴᴀʙʟᴇ ᴛᴏ sᴛᴀʀᴛ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ.\nRᴇᴀsᴏɴ: {exc}")

    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except Exception:
                pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
        ffmpeg_params: str = None,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        stream = dynamic_media_stream(path=link, video=bool(video), ffmpeg_params=ffmpeg_params)

        try:
            # Use the canonical PyTgCalls play path. The current library
            # handles joining an existing voice chat and media negotiation
            # internally; passing a GroupCallConfig here can leave older/
            # mixed ntgcalls stacks in a joined-but-silent state.
            await assistant.play(chat_id, stream)
        except NoActiveGroupCall:
            # If the group has no active voice chat, create one through the
            # assistant account and retry the exact same media stream once.
            try:
                await self.start_voice_chat(chat_id)
                await assistant.play(chat_id, stream)
            except (ChatAdminRequired, NoActiveGroupCall):
                raise AssistantErr(_["call_8"])
        except ChatAdminRequired:
            raise AssistantErr(_["call_8"])
        except NoAudioSourceFound:
            raise AssistantErr(_["call_11"])
        except NoVideoSourceFound:
            raise AssistantErr(_["call_12"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(
                f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {e}"
            )
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)


    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                    await _clear_(chat_id)
                    if chat_id in self.active_calls:
                        try:
                            await client.leave_call(chat_id)
                        except NoActiveGroupCall:
                            pass
                        except Exception:
                            pass
                        finally:
                            self.active_calls.discard(chat_id)
                    return
        except Exception:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except Exception:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0

            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            video = True if str(streamtype) == "video" else False

            stream = dynamic_media_stream(path=queued, video=video)
            try:
                await client.play(chat_id, stream)
            except NoActiveGroupCall:
                # Recover from a stale in-memory active-chat flag by rejoining
                # the voice chat before retrying the queued track.
                try:
                    await self.join_call(
                        chat_id, original_chat_id, queued, video=video
                    )
                except Exception as exc:
                    LOGGER(__name__).error(
                        "Playback recovery failed in %s: %s: %s",
                        chat_id, type(exc).__name__, exc,
                    )
                    return await app.send_message(original_chat_id, text=_["call_6"])
            except Exception as exc:
                LOGGER(__name__).error(
                    "Playback failed in %s: %s: %s",
                    chat_id, type(exc).__name__, exc,
                )
                return await app.send_message(original_chat_id, text=_["call_6"])

            button = stream_markup(_, chat_id)
            run = await app.send_message(
                chat_id=original_chat_id,
                text=(
                    "✦ <b>蒼響 // NOW PLAYING</b> ✦\n\n"
                    f"🎵 <b>{title[:60]}</b>\n"
                    f"⏱ <code>{check[0]["dur"]}</code>  •  👤 {user}\n\n"
                    "◈ <b>VOICE STREAM ONLINE</b>\n"
                    "⚡ Audio is now being transmitted to the voice chat."
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg" if videoid == "telegram" else "stream"


    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        # Reuse the exact assistant clients that Userbot.start() already
        # authenticated. Never create duplicate/unstarted Pyrogram clients for
        # PyTgCalls: doing so makes voice playback silently fail or disconnect.
        from AquaVibe.core.runtime import userbot as runtime_userbot

        self.userbot1 = runtime_userbot.one if config.STRING1 else None
        self.userbot2 = runtime_userbot.two if config.STRING2 else None
        self.userbot3 = runtime_userbot.three if config.STRING3 else None
        self.userbot4 = runtime_userbot.four if config.STRING4 else None
        self.userbot5 = runtime_userbot.five if config.STRING5 else None

        clients = (
            (self.userbot1, "1"),
            (self.userbot2, "2"),
            (self.userbot3, "3"),
            (self.userbot4, "4"),
            (self.userbot5, "5"),
        )
        for client, label in clients:
            if client is None:
                continue
            if not getattr(client, "is_connected", False):
                LOGGER(__name__).warning(
                    "Assistant %s is not connected; skipping its PyTgCalls client.", label
                )
                continue
            if label == "1" and self.one is None:
                self.one = PyTgCalls(client)
            elif label == "2" and self.two is None:
                self.two = PyTgCalls(client)
            elif label == "3" and self.three is None:
                self.three = PyTgCalls(client)
            elif label == "4" and self.four is None:
                self.four = PyTgCalls(client)
            elif label == "5" and self.five is None:
                self.five = PyTgCalls(client)

        for assistant, label in ((self.one, "1"), (self.two, "2"), (self.three, "3"), (self.four, "4"), (self.five, "5")):
            if assistant is not None:
                try:
                    await assistant.start()
                    LOGGER(__name__).info("PyTgCalls assistant %s started.", label)
                except Exception as exc:
                    LOGGER(__name__).error(
                        "PyTgCalls assistant %s failed to start: %s: %s",
                        label, type(exc).__name__, exc,
                    )
                    # Never leave a non-running PyTgCalls wrapper available to
                    # the queue selector. A stale wrapper makes /play appear to
                    # work while voice playback fails later with confusing
                    # connection errors.
                    if label == "1": self.one = None
                    elif label == "2": self.two = None
                    elif label == "3": self.three = None
                    elif label == "4": self.four = None
                    elif label == "5": self.five = None

    @capture_internal_err
    async def ping(self) -> str:
        # PyTgCalls exposes ping as a numeric property in current releases.
        # Older builds exposed it as a callable. Support both forms and ignore
        # an assistant that is not started instead of crashing /ping.
        pings = []
        for assistant in (self.one, self.two, self.three, self.four, self.five):
            if assistant is None:
                continue
            try:
                value = assistant.ping
                if callable(value):
                    value = value()
                if hasattr(value, "__await__"):
                    value = await value
                value = float(value)
                pings.append(value)
            except Exception:
                continue
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
        )

        async def unified_update_handler(client, update: Update) -> None:
            if isinstance(update, StreamEnded):
                if update.stream_type == StreamEnded.Type.AUDIO:
                    assistant = await group_assistant(self, update.chat_id)
                    await self.play(assistant, update.chat_id)
            
            elif isinstance(update, ChatUpdate):
                status = update.status
                if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                    await self.stop_stream(update.chat_id)
                    return

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)


StreamController = Call()
