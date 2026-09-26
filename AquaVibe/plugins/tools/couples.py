# Aqua Vibe couple-of-the-day
import random
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError
from pyrogram import errors, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from AquaVibe.core.runtime import app
from AquaVibe.core.dir import COUPLE_DIR
from AquaVibe.mongo.couples_db import get_couple, save_couple

ASSETS = Path("AquaVibe/assets/AquaVibe")
FALLBACK = ASSETS / "couple.png"  # bundled fallback; upic.png is not shipped
OUT_DIR = Path(COUPLE_DIR)
BACKGROUNDS = sorted(ASSETS.glob("couple_bg_*.png"))

def today() -> str:
    return datetime.now().strftime("%d/%m/%Y")

def tomorrow() -> str:
    return (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")

def circular(path: str | Path) -> Image.Image:
    try:
        img = Image.open(path).convert("RGBA").resize((330, 330))
    except (FileNotFoundError, UnidentifiedImageError):
        img = Image.open(FALLBACK).convert("RGBA").resize((330, 330))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + img.size, fill=255)
    img.putalpha(mask)
    border = Image.new("RGBA", (346, 346), (0, 0, 0, 0))
    ImageDraw.Draw(border).ellipse((2, 2, 344, 344), fill=(255,255,255,235))
    border.paste(img, (8, 8), img)
    return border

async def safe_get_user(uid: int):
    try:
        return await app.get_users(uid)
    except Exception:
        return None

async def safe_photo(uid: int, name: str) -> Path:
    try:
        chat = await app.get_chat(uid)
        if chat.photo and chat.photo.big_file_id:
            path = await app.download_media(chat.photo.big_file_id, file_name=OUT_DIR / name)
            return Path(path) if path else FALLBACK
    except Exception:
        pass
    return FALLBACK

def make_background(chat_id: int, date: str) -> Image.Image:
    if not BACKGROUNDS:
        return Image.new("RGBA", (1254,1254), (25,15,35,255))
    rng = random.Random(f"{chat_id}:{date}")
    return Image.open(rng.choice(BACKGROUNDS)).convert("RGBA").copy()

async def generate_image(chat_id: int, uid1: int, uid2: int, date: str) -> str:
    base = make_background(chat_id, date)
    p1 = await safe_photo(uid1, f"pfp1_{chat_id}.png")
    p2 = await safe_photo(uid2, f"pfp2_{chat_id}.png")
    a1 = circular(p1); a2 = circular(p2)
    base.paste(a1, (120, 360), a1)
    base.paste(a2, (788, 360), a2)
    d = ImageDraw.Draw(base, "RGBA")
    d.text((627, 760), "💗", anchor="mm", fill=(255,220,245,245))
    out_path = OUT_DIR / f"couple_{chat_id}_{date.replace('/','-')}.png"
    base.save(out_path, quality=94)
    for pf in (p1, p2):
        try:
            if pf != FALLBACK and pf.exists() and pf.parent == OUT_DIR:
                pf.unlink()
        except Exception:
            pass
    return str(out_path)

@app.on_message(filters.command("couple"))
async def couples_handler(_, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.**")
    wait = await message.reply("💗")
    cid = message.chat.id; date = today()
    record = None
    try:
        record = await get_couple(cid, date)
    except Exception:
        record = None
    user1 = user2 = None
    if record:
        user1 = await safe_get_user(record.get("user1"))
        user2 = await safe_get_user(record.get("user2"))
        if not (user1 and user2) or not record.get("img") or not Path(record["img"]).exists():
            record = None
    if not record:
        members = []
        try:
            async for m in app.get_chat_members(cid):
                if m.user and not m.user.is_bot and not m.user.is_deleted:
                    members.append(m.user.id)
        except Exception:
            await wait.edit("**ɪ ɴᴇᴇᴅ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ʀᴇᴀᴅ ɢʀᴏᴜᴘ ᴍᴇᴍʙᴇʀs.**")
            return
        if len(members) < 2:
            await wait.edit("**ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴜsᴇʀs ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ.**")
            return
        uid1, uid2 = random.sample(members, 2)
        user1, user2 = await safe_get_user(uid1), await safe_get_user(uid2)
        if not user1 or not user2:
            await wait.edit("**ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴛᴡᴏ ᴠᴀʟɪᴅ ᴍᴇᴍʙᴇʀs.**")
            return
        img_path = await generate_image(cid, uid1, uid2, date)
        try:
            await save_couple(cid, date, {"user1": uid1, "user2": uid2}, img_path)
        except Exception:
            pass
    else:
        img_path = record["img"]
    caption = (
        "💌 **ᴄᴏᴜᴘʟᴇ ᴏꜰ ᴛʜᴇ ᴅᴀʏ!** 💗\n\n"
        f"💌 **ᴛᴏᴅᴀʏ'ꜱ ᴄᴏᴜᴘʟᴇ:**\n⤷ {user1.mention} 💞 {user2.mention}\n\n"
        f"📅 **ɴᴇxᴛ ꜱᴇʟᴇᴄᴛɪᴏɴ:** `{tomorrow()}`\n\n"
        "💗 **ᴛᴀɢ ʏᴏᴜʀ ᴄʀᴜꜱʜ — ʏᴏᴜ ᴍɪɢʜᴛ ʙᴇ ɴᴇxᴛ!** 😉"
    )
    try:
        await message.reply_photo(img_path, caption=caption)
    finally:
        try: await wait.delete()
        except Exception: pass
