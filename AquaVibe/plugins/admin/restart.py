# Authored By Dev © 2025
import os
import shutil
import socket
import sys

import urllib3
from pyrogram import filters

from AquaVibe.core.runtime import app
from AquaVibe.misc import HAPP, ADMINS
from AquaVibe.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from AquaVibe.utils.decorators.language import language

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

async def is_heroku():
    return "heroku" in socket.getfqdn()

def cleanup_storage():
    folders_to_remove = ["downloads", "raw_files", "cache"]
    for folder in folders_to_remove:
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[CLEANUP] Failed to delete {folder}: {e}")

    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, d))
                except Exception:
                    pass


@app.on_message(filters.command(["logs"]) & ADMINS)
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except Exception:
        await message.reply_text(_["server_1"])


async def restart_(_, message):
    response = await message.reply_text("ʀᴇsᴛᴀʀᴛɪɴɢ...")
    ac_chats = await get_active_chats()
    for x in ac_chats:
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"{app.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
            )
            await remove_active_chat(x)
            await remove_active_video_chat(x)
        except Exception:
            pass

    cleanup_storage()

    await response.edit_text(
        "» ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss sᴛᴀʀᴛᴇᴅ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ғᴇᴡ sᴇᴄᴏɴᴅs ᴜɴᴛɪʟ ᴛʜᴇ ʙᴏᴛ sᴛᴀʀᴛs..."
    )

    os.execv(sys.executable, [sys.executable, "-m", "AquaVibe"])
