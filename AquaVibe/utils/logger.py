# Authored By Dev © 2025
from pyrogram.enums import ParseMode

from AquaVibe.core.runtime import app
from AquaVibe.utils.database import is_on_off
from config import LOGGER_ID, REMOTE_PLAY_LOGGING


async def play_logs(message, streamtype, query: str = None):
    if REMOTE_PLAY_LOGGING and await is_on_off(2) and LOGGER_ID:
        if query is None:
            try:
                query = message.text.split(None, 1)[1]
            except Exception:
                query = "—"

        logger_text = f"""
<b>{app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{message.chat.id}</code>
<b>ᴄʜᴀᴛ ɴᴀᴍᴇ :</b> {message.chat.title}
<b>ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.chat.username}

<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>
<b>ɴᴀᴍᴇ :</b> {message.from_user.mention}
<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}

<b>ǫᴜᴇʀʏ :</b> {query}
<b>sᴛʀᴇᴀᴍᴛʏᴘᴇ :</b> {streamtype}"""
        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        return


async def report_play_error(message, error, operation="song playback"):
    """Log the real playback error and always show a useful player-facing error.

    The /play wrapper removes the command message early, so replying to that
    deleted message can itself fail and leave the user with no output. Send to
    the chat directly instead. Never claim that the bot is under maintenance
    unless that is actually the configured state.
    """
    import html
    import traceback

    chat_id = getattr(getattr(message, "chat", None), "id", "N/A")
    chat_title = getattr(getattr(message, "chat", None), "title", None) or "Private/Unknown"
    user = getattr(getattr(message, "from_user", None), "id", "N/A")
    user_name = getattr(getattr(message, "from_user", None), "first_name", "Unknown")
    error_type = type(error).__name__
    detail = str(error).strip() or "Unknown playback error"
    tb = traceback.format_exc()
    if tb.strip() == "NoneType: None":
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    logger_text = (
        "🚨 <b>Song Playback Error</b>\n\n"
        f"<b>Operation:</b> <code>{html.escape(str(operation))}</code>\n"
        f"<b>Chat ID:</b> <code>{html.escape(str(chat_id))}</code>\n"
        f"<b>Chat:</b> {html.escape(str(chat_title))}\n"
        f"<b>User ID:</b> <code>{html.escape(str(user))}</code>\n"
        f"<b>User:</b> {html.escape(str(user_name))}\n"
        f"<b>Error:</b> <code>{html.escape(error_type)}</code>\n"
        f"<b>Details:</b> <code>{html.escape(detail)[:1200]}</code>\n\n"
        f"<b>Traceback:</b>\n<pre>{html.escape(tb[-2500:])}</pre>"
    )
    if REMOTE_PLAY_LOGGING and LOGGER_ID:
        try:
            await app.send_message(LOGGER_ID, logger_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception:
            pass

    safe_detail = html.escape(detail[:700])
    player_text = (
        "❌ <b>Playback failed</b>\n\n"
        f"<b>Reason:</b> <code>{safe_detail}</code>\n\n"
        "Please try another song or use /play again."
    )
    try:
        await app.send_message(chat_id, player_text, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await message.reply_text(player_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass
