# Authored By Dev © 2025
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import BANNED_USERS, OWNER_ID
from AquaVibe.core.runtime import app
from AquaVibe.misc import ADMINS
from AquaVibe.utils.database import add_admin, remove_admin
from AquaVibe.utils.decorators.language import language
from AquaVibe.utils.extraction import extract_user
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton

# ─── Add Sudo ─────────────────────────────────────────────

@app.on_message(filters.command(["badmin"], prefixes=["/", "!", "."]) & filters.user(OWNER_ID))
@language
async def add_admin_user(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    if user.id in ADMINS:
        return await message.reply_text(_["admin_1"].format(user.mention))

    if await add_admin(user.id):
        if user.id not in ADMINS:
            ADMINS.add(user.id)
        return await message.reply_text(_["admin_2"].format(user.mention))

    await message.reply_text(_["admin_8"])

# ─── Remove Sudo ───────────────────────────────────────────

@app.on_message(filters.command(["dbadmin", "rmadmin"], prefixes=["/", "!", "."]) & filters.user(OWNER_ID))
@language
async def remove_admin_user(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    user = await extract_user(message)
    if user.id not in ADMINS:
        return await message.reply_text(_["admin_3"].format(user.mention))

    if await remove_admin(user.id):
        if user.id in ADMINS:
            ADMINS.remove(user.id)
        return await message.reply_text(_["admin_4"].format(user.mention))

    await message.reply_text(_["admin_8"])

# ─── Sudo List Entry ───────────────────────────────────────

@app.on_message(filters.command(["admins"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
async def admins_list(client, message: Message):
    keyboard = [[InlineKeyboardButton("๏ ᴠɪᴇᴡ sᴜᴅᴏʟɪsᴛ ๏", callback_data="admin_list_view")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        "**» ᴄʜᴇᴄᴋ sᴜᴅᴏ ʟɪsᴛ ʙʏ ɢɪᴠᴇɴ ʙᴇʟᴏᴡ.**\n\n**» ɴᴏᴛᴇ:** ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴄᴀɴ ᴠɪᴇᴡ.",
        reply_markup=reply_markup
    )

# ─── Callback: View Sudo List ──────────────────────────────

@app.on_callback_query(filters.regex("^admin_list_view$"))
async def view_admin_list_callback(client, callback_query: CallbackQuery):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ᴏɴʟʏ sᴜᴅᴏᴇʀs ᴀɴᴅ ᴏᴡɴᴇʀ ᴄᴀɴ ᴀᴄᴄᴇss ᴛʜɪs", show_alert=True)

    owner = await app.get_users(OWNER_ID)
    caption = f"**˹ʟɪsᴛ ᴏғ ʙᴏᴛ ᴍᴏᴅᴇʀᴀᴛᴏʀs˼**\n\n**🌹Oᴡɴᴇʀ** ➥ {owner.mention}\n\n"
    keyboard = [[InlineKeyboardButton("๏ ᴠɪᴇᴡ ᴏᴡɴᴇʀ ๏", url=f"tg://openmessage?user_id={OWNER_ID}")]]

    count = 0
    for user_id in ADMINS:
        if user_id == OWNER_ID:
            continue
        try:
            user = await app.get_users(user_id)
            count += 1
            caption += f"**🎁 Sᴜᴅᴏ {count} »** {user.mention}\n"
            keyboard.append([
                InlineKeyboardButton(f"๏ ᴠɪᴇᴡ sᴜᴅᴏ {count} ๏", url=f"tg://openmessage?user_id={user_id}")
            ])
        except Exception:
            continue

    if count == 0:
        caption += "_No additional admins yet._"

    keyboard.append([InlineKeyboardButton("๏ ʙᴀᴄᴋ ๏", callback_data="admin_list_back")])
    await callback_query.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))

# ─── Callback: Back to List Menu ────────────────────────────

@app.on_callback_query(filters.regex("^admin_list_back$"))
async def back_to_admin_list_menu(client, callback_query: CallbackQuery):
    keyboard = [[InlineKeyboardButton("๏ ᴠɪᴇᴡ sᴜᴅᴏʟɪsᴛ ๏", callback_data="admin_list_view")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await callback_query.message.edit_caption(
        caption="**» ᴄʜᴇᴄᴋ sᴜᴅᴏ ʟɪsᴛ ʙʏ ɢɪᴠᴇɴ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ.**\n\n**» ɴᴏᴛᴇ:**  ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴄᴀɴ ᴠɪᴇᴡ.",
        reply_markup=reply_markup
    )

# ─── Delete All Sudo ───────────────────────────────────────

@app.on_message(filters.command("delalladmin", prefixes=["/", "!", "%", ",", ".", "@", "#"]) & filters.user(OWNER_ID))
@language
async def remove_all_admin_users(client, message: Message, _):
    removed_count = 0
    for user_id in list(ADMINS):
        if user_id != OWNER_ID:
            if await remove_admin(user_id):
                if user_id in ADMINS:
                    ADMINS.remove(user_id)
                removed_count += 1
    await message.reply_text(f"Removed {removed_count} users from the admin list.")
