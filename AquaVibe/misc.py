# Authored By Dev © 2025
import socket
import time
import heroku3

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus

from config import HEROKU_API_KEY, HEROKU_APP_NAME, OWNER_ID
from AquaVibe.core.mongo import mongodb
from .log_config import LOGGER

ADMINS = filters.user()
COMMANDERS = [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
HAPP = None
_boot_ = time.time()

def is_heroku():
    return "heroku" in socket.getfqdn()

XCB = [
    "/", "@", ".", "com", ":", "git", "heroku", "push",
    str(HEROKU_API_KEY), "https", str(HEROKU_APP_NAME),
    "HEAD", "master"
]

def dbb():
    global db
    db = {}
    LOGGER(__name__).info("ᴅᴀᴛᴀʙᴀsᴇ ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ💗")

async def admin():
    global ADMINS
    ADMINS.add(OWNER_ID)
    adminsdb = mongodb.admins
    data = await adminsdb.find_one({"admin": "admin"}) or {}
    admins = data.get("admins", [])

    if OWNER_ID not in admins:
        admins.append(OWNER_ID)
        await adminsdb.update_one(
            {"admin": "admin"}, {"$set": {"admins": admins}}, upsert=True
        )

    for user_id in admins:
        ADMINS.add(user_id)

    LOGGER(__name__).info("sᴜᴅᴏ ᴜsᴇʀs ᴅᴏɴᴇ..")

def heroku():
    global HAPP
    if is_heroku():
        if HEROKU_API_KEY and HEROKU_APP_NAME:
            try:
                Heroku = heroku3.from_key(HEROKU_API_KEY)
                HAPP = Heroku.app(HEROKU_APP_NAME)
                LOGGER(__name__).info("ʜᴇʀᴏᴋᴜ ᴀᴘᴘ ᴄᴏɴғɪɢᴜʀᴇᴅ..")
            except Exception:
                LOGGER(__name__).warning("ʏᴏᴜ sʜᴏᴜʟᴅ ʜᴀᴠᴇ ɴᴏᴛ ғɪʟʟᴇᴅ ʜᴇʀᴏᴋᴜ ᴀᴘᴘ ɴᴀᴍᴇ ᴏʀ ᴀᴘɪ ᴋᴇʏ ᴄᴏʀʀᴇᴄᴛʟʏ ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ɪᴛ...")
