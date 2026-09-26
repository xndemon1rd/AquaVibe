"""Owner-managed banner system.

Owner usage:
  Reply to an image with /setbanner1 or /setbanner2.

User usage:
  /banner       -> send a configured banner (random slot)
  /banner 1     -> send banner slot 1
  /banner 2     -> send banner slot 2

Banners are stored as Telegram file IDs in the existing banner collection, so
no external image-hosting service is required.
"""
import random

from pyrogram import filters

from AquaVibe.core.runtime import app
from AquaVibe.utils.database import get_banner, set_banner
from config import OWNER_ID


def _file_id(message):
    """Return a reusable Telegram file_id for an image message."""
    if message.photo:
        return message.photo.file_id
    if message.document and (message.document.mime_type or "").lower().startswith("image/"):
        return message.document.file_id
    return None


async def _set_banner(message, slot: int):
    reply = message.reply_to_message
    if not reply:
        await message.reply_text(
            f"Reply to an image with /setbanner{slot}."
        )
        return

    file_id = _file_id(reply)
    if not file_id:
        await message.reply_text("The replied message must contain an image/photo.")
        return

    try:
        await set_banner(slot, file_id)
        await message.reply_text(f"Banner {slot} saved successfully.")
    except Exception:
        await message.reply_text("Couldn't save the banner. Please check the database connection.")


@app.on_message(filters.command("setbanner1", prefixes=["/", "."]) & filters.user(OWNER_ID))
async def set_banner_one(_, message):
    await _set_banner(message, 1)


@app.on_message(filters.command("setbanner2", prefixes=["/", "."]) & filters.user(OWNER_ID))
async def set_banner_two(_, message):
    await _set_banner(message, 2)


@app.on_message(filters.command("banner", prefixes=["/", "."]))
async def show_banner(_, message):
    args = message.command[1:] if message.command else []
    slot = None
    if args:
        try:
            slot = int(args[0])
        except ValueError:
            slot = None

    if slot not in (1, 2):
        slot = random.choice((1, 2))

    file_id = await get_banner(slot)
    if not file_id:
        other = 2 if slot == 1 else 1
        file_id = await get_banner(other)
        slot = other if file_id else slot

    if not file_id:
        await message.reply_text(
            "No banner has been configured yet. The owner can reply to an image with /setbanner1 or /setbanner2."
        )
        return

    try:
        await message.reply_photo(file_id, caption=f"Banner {slot}")
    except Exception:
        await message.reply_text("The configured banner could not be sent. The owner may need to replace it.")
