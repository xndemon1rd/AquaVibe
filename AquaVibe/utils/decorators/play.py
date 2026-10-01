# Saya Music
import asyncio
import re
import time

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteHashExpired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string
from AquaVibe.core.runtime import YouTube, app
from AquaVibe.misc import ADMINS as SUDOERS
from AquaVibe.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from AquaVibe.utils.inline import botplaylist_markup

# Cache for invite links per chat
links = {}

# (chat_id, assistant_id) -> monotonic time the assistant was last seen as a
# normal member. Saves one get_chat_member call on every cold /play.
_member_ok = {}
_MEMBER_OK_TTL = 300.0
_BG_TASKS: set = set()


def PlayWrapper(command):
    async def wrapper(client, message):
        # DB can be temporarily unavailable; playback should still answer/delete
        # the command instead of dying before the handler reaches the message delete.
        try:
            language = await get_lang(message.chat.id)
        except Exception:
            language = "en"
        _ = get_string(language)

        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="AnonymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_3"], reply_markup=upl)

        try:
            maintenance = await is_maintenance()  # True == maintenance mode is ON
        except Exception:
            maintenance = False  # DB blip: fail open, never block playback
        if maintenance:
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )

        # Deleting the command is cosmetic; do not make playback wait on it.
        async def _delete_cmd():
            try:
                await message.delete()
            except Exception:
                pass

        _t = asyncio.create_task(_delete_cmd())
        _BG_TASKS.add(_t)
        _t.add_done_callback(_BG_TASKS.discard)

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)

        if audio_telegram is None and video_telegram is None and url is None:
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                buttons = botplaylist_markup(_)
                return await message.reply_photo(
                    photo=PLAYLIST_IMG_URL,
                    caption=_["play_18"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
            except Exception:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None

        playmode, playty = await asyncio.gather(
            get_playmode(message.chat.id), get_playtype(message.chat.id)
        )
        if playty != "Everyone":
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                elif message.from_user.id not in admins:
                    return await message.reply_text(_["play_4"])

        if message.command[0][0] == "v":
            video = True
        else:
            if re.search(r"(?:^|\s)-v(?=\s|$)", message.text or ""):
                video = True
            else:
                video = True if message.command[0][1] == "v" else None

        if message.command[0][-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = None

        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            try:
                _ck = (chat_id, userbot.id)
                _hit = _member_ok.get(_ck)
                if _hit and time.monotonic() - _hit < _MEMBER_OK_TTL:
                    member = None  # recently verified: skip the Telegram round-trip
                else:
                    try:
                        member = await app.get_chat_member(chat_id, userbot.id)
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    if member.status not in (
                        ChatMemberStatus.BANNED,
                        ChatMemberStatus.RESTRICTED,
                    ):
                        _member_ok[_ck] = time.monotonic()

                if member is not None and member.status in (
                    ChatMemberStatus.BANNED,
                    ChatMemberStatus.RESTRICTED,
                ):
                    _member_ok.pop(_ck, None)
                    return await message.reply_text(
                        _["call_2"].format(
                            app.mention, userbot.id, userbot.name, userbot.username
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        text="๏ 𝗨ɴʙᴀɴ 𝗔ssɪsᴛᴀɴᴛ ๏",
                                        callback_data="unban_assistant",
                                    )
                                ]
                            ]
                        ),
                    )
            except UserNotParticipant:
                _member_ok.pop((chat_id, userbot.id), None)
                if chat_id in links:
                    invitelink = links[chat_id]
                else:
                    if message.chat.username:
                        invitelink = message.chat.username
                        try:
                            await userbot.resolve_peer(invitelink)
                        except Exception:
                            pass
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_1"])
                        except Exception as e:
                            return await message.reply_text(
                                _["call_3"].format(app.mention, type(e).__name__)
                            )

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )

                myu = await message.reply_text(_["call_4"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteHashExpired:
                    # Remove expired invite link from the cache.
                    if chat_id in links:
                        del links[chat_id]
                    # Generate a new invite link.
                    try:
                        invitelink = await app.export_chat_invite_link(chat_id)
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    if invitelink.startswith("https://t.me/+"):
                        invitelink = invitelink.replace(
                            "https://t.me/+", "https://t.me/joinchat/"
                        )
                    # Update the cache.
                    links[chat_id] = invitelink
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    await myu.edit(_["call_5"].format(app.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(
                        _["call_3"].format(app.mention, type(e).__name__)
                    )

                links[chat_id] = invitelink

                try:
                    await userbot.resolve_peer(chat_id)
                except Exception:
                    pass

        return await command(
            client, message, _, chat_id, video, channel, playmode, url, fplay
        )

    return wrapper
