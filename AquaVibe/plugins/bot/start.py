# Authored By Dev © 2025
import asyncio
from pathlib import Path
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity

import config
from AquaVibe.core.runtime import AlternativeMedia, app
from AquaVibe.plugins.admin.admins import admins_list
from AquaVibe.utils import bot_sys_stats
from AquaVibe.utils.database import (
    add_served_chat,
    add_served_user,
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
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton


async def delete_sticker_after_delay(message: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    user_id = message.from_user.id
    try:
        await add_served_user(user_id)
    except Exception:
        pass

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]

        if name.startswith("help"):
            keyboard = first_page(_)
            return await message.reply_photo(
                photo=HELP_IMG_URL,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )

        if name.startswith("sud"):
            await admins_list(client=client, message=message, _=_)
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
                      InlineKeyboardButton(text="📢 Support Channel", url="https://t.me/zxknox"), InlineKeyboardButton(text="👥 Support Group", url="https://t.me/zpaveldurov")]]
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

    out = private_panel(_, message.from_user.id)

    # Nobara-style private /start reaction intro: show a short emoji sequence
    # before the main card.  The sticker itself is configurable because Telegram
    # bot file_ids are bot-specific and cannot safely be copied from another bot.
    try:
        intro = await message.reply_text("`Hie " + (message.from_user.first_name or "there") + " <3`")
        for reaction in ("🐾", "❄️", "🕊️"):
            await asyncio.sleep(0.8)
            await intro.edit_text(reaction)
        await asyncio.sleep(0.35)
        await intro.delete()
    except Exception:
        pass

    start_sticker_id = getattr(config, "START_STICKER_FILE_ID", "")
    if start_sticker_id:
        try:
            await message.reply_sticker(start_sticker_id)
            await asyncio.sleep(0.2)
        except Exception:
            pass

    try:
        served_chats, served_users, stats = await asyncio.gather(
            get_served_chats(), get_served_users(), bot_sys_stats(),
            return_exceptions=True,
        )
        if isinstance(served_chats, Exception):
            served_chats = []
        if isinstance(served_users, Exception):
            served_users = []
        if isinstance(stats, Exception):
            stats = (0, 0, 0, 0)
        UP, CPU, RAM, DISK = stats
    except Exception:
        served_chats, served_users = [], []
        UP, CPU, RAM, DISK = 0, 0, 0, 0

    # Private /start card: premium welcome caption + animated GIF + buttons.
    start_caption = (
        f"🦋 𝖧𝖤𝖸, {message.from_user.first_name or 'there'}\n\n"
        "⚡ 𝖶𝖤𝖫𝖢𝖮𝖬𝖤 𝖳𝖮 蒼響\n"
        "◈ 𝖲𝗒𝗌𝗍𝖾𝗆 𝖮𝗇𝗅𝗂𝗇𝖾\n"
        "◈ 𝖥𝖺𝗌𝗍 • 𝖲𝗆𝖺𝗋𝗍 • 𝖲𝗆𝗈𝗈𝗍𝗁\n"
        "🚀 𝖱𝖾𝖺𝖽𝗒 𝖳𝗈 𝖱𝗎𝗇"
    )
    try:
        await message.reply_animation(
            animation="https://files.catbox.moe/ge1piy.gif",
            caption=start_caption,
            reply_markup=InlineKeyboardMarkup(out),
        )
    except Exception as exc:
        await report_exception(
            exc,
            label="Start Animation Error",
            extras={"Handler": "/start", "Chat ID": message.chat.id},
        )

    if await is_on_off(2) and config.LOGGER_ID:
        username = f"@{message.from_user.username}" if message.from_user.username else "(none)"
        await app.send_message(
            chat_id=config.LOGGER_ID,
            text=(
                f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n"
                f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n"
                f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username}"
            ),
        )


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

        except Exception as ex:
            await report_exception(
                ex,
                label="Welcome Handler Error",
                extras={"Chat ID": message.chat.id, "Chat": message.chat.title or "N/A"},
            )
