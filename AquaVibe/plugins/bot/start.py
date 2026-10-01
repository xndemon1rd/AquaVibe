# Authored By Dev © 2025
import asyncio
from pathlib import Path
import pyrogram
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity, CallbackQuery

import config
from AquaVibe.core.runtime import AlternativeMedia, app
from AquaVibe.plugins.admin.admins import admins_list
from AquaVibe.utils.database import (
    add_served_chat,
    add_served_user,
    get_user_gender,
    set_user_gender,
    blacklisted_chats,
    get_lang,
    get_served_chats,
    get_served_users,
    is_banned_user,
    is_on_off,
)
from AquaVibe.utils.decorators.language import LanguageStart
from AquaVibe.utils.premium_emoji import custom_emoji_entities, _utf16_len
from AquaVibe.utils.errors import report_exception
from AquaVibe.utils.inline.start import private_panel, start_panel
from AquaVibe.utils.inline.help import first_page
from config import BANNED_USERS, HELP_IMG_URL, START_IMG_URL
from strings import get_string
from AquaVibe.utils.welcome import welcome_caption

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
WELCOME_MALE_VIDEO = _ASSETS / "welcome_male.mp4"
WELCOME_FEMALE_IMG = _ASSETS / "welcome_female.jpg"
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
InlineKeyboardButton = ColoredInlineKeyboardButton


# Telegram file_ids of the welcome media, cached after the first successful send
# so /start never re-uploads the 5 MB video (or re-downloads the catbox GIF).
_MEDIA_FILE_IDS: dict = {}
from AquaVibe.core.mongo import mongodb as _mongodb
_MEDIA_DB = _mongodb.aqua_media_cache
_BG_TASKS: set = set()
_WELCOME_GIF_URL = "https://files.catbox.moe/ge1piy.gif"


def _spawn(coro) -> None:
    """Run ``coro`` in the background without delaying the reply."""
    async def _runner():
        try:
            await coro
        except Exception:
            pass

    task = asyncio.ensure_future(_runner())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)


async def _send_media(kind, key, source, chat_id, caption, entities, markup):
    """send_video/photo/animation using a cached file_id when we have one."""
    sender = getattr(app, f"send_{kind}")
    candidates = []
    if key not in _MEDIA_FILE_IDS:
        # Survive restarts: reuse the file_id saved in Mongo so the first /start
        # after a deploy doesn't re-upload the 5 MB video.
        try:
            doc = await asyncio.wait_for(_MEDIA_DB.find_one({"_id": key}), 2)
            if doc and doc.get("file_id"):
                _MEDIA_FILE_IDS[key] = doc["file_id"]
        except Exception:
            pass
    if key in _MEDIA_FILE_IDS:
        candidates.append(_MEDIA_FILE_IDS[key])
    candidates.append(source)
    last_exc = None
    for src in candidates:
        try:
            msg = await sender(
                chat_id=chat_id,
                caption=caption,
                caption_entities=entities,
                reply_markup=markup,
                **{kind: src},
            )
        except Exception as exc:  # stale file_id / upload problem -> try the source
            last_exc = exc
            if src is not source:
                _MEDIA_FILE_IDS.pop(key, None)
            continue
        file_id = getattr(getattr(msg, kind, None), "file_id", None)
        if file_id and _MEDIA_FILE_IDS.get(key) != file_id:
            _MEDIA_FILE_IDS[key] = file_id
            _spawn(_MEDIA_DB.update_one({"_id": key}, {"$set": {"file_id": file_id}}, upsert=True))
        return msg
    raise last_exc


async def _run_intro(intro: Message) -> None:
    """Emoji intro animation; runs in the background so /start isn't delayed."""
    try:
        for reaction in ("🐾", "❄️", "🕊️"):
            await asyncio.sleep(0.8)
            await intro.edit_text(reaction)
        await asyncio.sleep(0.35)
        await intro.delete()
    except Exception:
        pass


async def _notify_started(user) -> None:
    if await is_on_off(2) and config.LOGGER_ID:
        username = f"@{user.username}" if user.username else "(none)"
        await app.send_message(
            chat_id=config.LOGGER_ID,
            text=(
                f"{user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n"
                f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{user.id}</code>\n"
                f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
            ),
        )


async def delete_sticker_after_delay(message: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def _ask_gender(message: Message):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("♂ ᴍᴀʟᴇ", callback_data="AQUA_GENDER:male"),
            InlineKeyboardButton("♀ ғᴇᴍᴀʟᴇ", callback_data="AQUA_GENDER:female"),
        ]
    ])
    return await message.reply_text(
        "✦ <b>ᴡʜᴀᴛ ɪs ʏᴏᴜʀ ɢᴇɴᴅᴇʀ, ʙᴏss?</b> ✦\n\n"
        "ᴘɪᴄᴋ ᴏɴᴇ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ. ✨",
        reply_markup=keyboard,
    )


@app.on_callback_query(filters.regex(r"^AQUA_GENDER:(male|female)$"), group=5)
async def gender_verification_callback(client, query: CallbackQuery):
    user = query.from_user
    if not user:
        return await query.answer("User not found.", show_alert=True)
    gender = query.matches[0].group(1)
    try:
        already = await get_user_gender(user.id)
    except Exception:
        already = None
    if not already:  # first choice only: old buttons can't flip a saved gender
        await set_user_gender(user.id, gender)
    gender = already or gender
    await query.answer("Saved ✓")
    try:
        await query.message.delete()
    except Exception:
        pass
    try:
        _ = get_string(await get_lang(user.id))
    except Exception:
        _ = get_string("en")
    # Straight into the welcome card (male -> video, female -> custom image).
    await _send_private_welcome(user, _, gender)


async def _send_private_welcome(user, _, gender=None):
    """Private welcome card (intro reactions + image/GIF + buttons)."""
    chat_id = user.id
    out = private_panel(_, user.id)

    # Short "Hie <name>" intro.  Only the first send is awaited; the emoji
    # animation + cleanup run in the background so the card appears at once.
    try:
        intro = await app.send_message(chat_id, "`Hie " + (user.first_name or "there") + " <3`")
        _spawn(_run_intro(intro))
    except Exception:
        pass

    start_sticker_id = getattr(config, "START_STICKER_FILE_ID", "")
    if start_sticker_id:
        try:
            await app.send_sticker(chat_id, start_sticker_id)
        except Exception:
            pass

    # Private /start card: premium welcome caption + media + buttons.
    bot_display_name = (getattr(app.me, "first_name", None) if app.me else None) or config.BOT_NAME
    start_caption, start_entities = welcome_caption(user.first_name, user.id, bot_display_name)
    if gender is None:
        try:
            gender = await get_user_gender(user.id)
        except Exception:
            gender = None
    markup = InlineKeyboardMarkup(out)
    try:
        if gender == "male" and WELCOME_MALE_VIDEO.exists():
            await _send_media("video", "welcome_male", str(WELCOME_MALE_VIDEO),
                              chat_id, start_caption, start_entities, markup)
        elif gender == "female" and WELCOME_FEMALE_IMG.exists():
            await _send_media("photo", "welcome_female", str(WELCOME_FEMALE_IMG),
                              chat_id, start_caption, start_entities, markup)
        else:
            await _send_media("animation", "welcome_gif", _WELCOME_GIF_URL,
                              chat_id, start_caption, start_entities, markup)
    except Exception as exc:
        # Never leave the user with a dead /start: send the plain-text card FIRST,
        # then report the error in the background (reporting can be slow).
        try:
            await app.send_message(
                chat_id, start_caption, entities=start_entities, reply_markup=markup,
            )
        except Exception:
            pass
        _spawn(report_exception(
            exc,
            label="Start Welcome Error",
            extras={"Handler": "/start", "Chat ID": chat_id},
        ))

    _spawn(_notify_started(user))


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    user_id = message.from_user.id
    _spawn(add_served_user(user_id))  # DB write off the hot path

    # First-time private users must select a gender before the main menu.
    # Existing users who already have a saved selection continue normally.
    gender = None
    try:
        gender = await get_user_gender(user_id)
        if not gender:
            await _ask_gender(message)
            return
    except Exception:
        # Do not block /start if the optional profile field cannot be read.
        pass

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]

        if name.startswith("help"):
            from AquaVibe.plugins.bot.help import _category_markup, _help_text
            from AquaVibe.utils.premium_emoji import custom_emoji_entities
            text = _help_text()
            # Text-only catalog (no image) when arriving from a group's /help button.
            return await message.reply_text(
                text,
                entities=custom_emoji_entities(text, blockquote=False),
                reply_markup=_category_markup(message.from_user.id),
                disable_web_page_preview=True,
            )

        if name.startswith("sud"):
            await admins_list(client=client, message=message)
            if await is_on_off(2) and config.LOGGER_ID:
                username = f"@{message.from_user.username}" if message.from_user.username else "(none)"
                await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=(
                        f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n"
                        f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n"
                        f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
                    ),
                )
            return

        if name.startswith("inf"):
            m = await message.reply_text("🔎")
            try:
                vid_id = str(name).replace("info_", "", 1)
                details, _track_id = await AlternativeMedia.track(vid_id)
                title = details.get("title") or "Unknown"
                duration = details.get("duration_min") or "Unknown"
                thumbnail = details.get("thumb") or HELP_IMG_URL
                link = details.get("link") or "https://odysee.com/"
                searched_text = _["start_6"].format(title, duration, "Alternative Media", "", link, "Alternative Media", app.mention)
                key = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text=_["S_B_6"], url=link),
                      InlineKeyboardButton(text="📢 Support Channel", url="https://t.me/AstrixVeyra"), InlineKeyboardButton(text="👥 Support Group", url="https://t.me/zpaveldurov")]]
                )

                await m.delete()

                await app.send_photo(
                    chat_id=message.chat.id,
                    photo=thumbnail or HELP_IMG_URL,
                    caption=searched_text,
                    reply_markup=key,
                )

                if await is_on_off(2) and config.LOGGER_ID:
                    username = f"@{message.from_user.username}" if message.from_user.username else "(none)"
                    await app.send_message(
                        chat_id=config.LOGGER_ID,
                        text=(
                            f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.\n\n"
                            f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n"
                            f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
                        ),
                    )
            except Exception as e:
                await m.edit_text(f"Error: {e}")
            return

    await _send_private_welcome(message.from_user, _, gender)


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    try:
        display_name = message.from_user.first_name or "there"
        group_caption = (
            f"✨ Hello, {display_name}\n"
            f"🌐 Click the button below to explore my feature"
        )
        group_entities = custom_emoji_entities(group_caption, blockquote=True)
        name_offset = _utf16_len("✨ Hello, ")
        name_length = _utf16_len(display_name)
        group_entities.append(
            MessageEntity(
                type=MessageEntityType.TEXT_MENTION,
                offset=name_offset,
                length=name_length,
                user=message.from_user,
            )
        )
        await message.reply_text(
            group_caption,
            entities=group_entities,
            reply_markup=InlineKeyboardMarkup(out),
        )
    except Exception as exc:
        await report_exception(
            exc,
            label="Group Start Send Error",
            extras={"Chat ID": message.chat.id},
        )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except Exception:
                    pass

            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)

                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=adminlist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                welcome_caption = (
                    f"✨ 𝖧𝖾𝗅𝗅𝗈, {message.chat.title}\n"
                    f"🌐 𝖢𝗅𝗂𝖼𝗄 𝗍𝗁𝖾 𝖧𝖾𝗅𝗉 𝖻𝗎𝗍𝗍𝗈𝗇 𝖻𝖾𝗅𝗈𝗐 𝗍𝗈 𝖾𝗑𝗉𝗅𝗈𝗋𝖾 𝗆𝗒 𝖿𝖾𝖺𝗍𝗎𝗋𝖾𝗌!"
                )
                await message.reply_text(
                    welcome_caption,
                    entities=custom_emoji_entities(welcome_caption, blockquote=True),
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()

        except pyrogram.StopPropagation:
            raise
        except Exception as ex:
            await report_exception(
                ex,
                label="Welcome Handler Error",
                extras={"Chat ID": message.chat.id, "Chat": message.chat.title or "N/A"},
            )
