import os
import aiohttp
import aiofiles
from PIL import Image

import config
from AquaVibe.core.runtime import app
from config import EXTERNAL_UPLOADS_ENABLED
from pyrogram import filters
from pyrogram.types import Message
from AquaVibe.utils.ai import generate_image
from AquaVibe.utils.database import get_ai_plan, consume_ai_generation


async def download_from_url(path: str, url: str) -> str | None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            async with aiofiles.open(path, mode="wb") as f:
                await f.write(await resp.read())
    return path


async def post_file(url: str, file_path: str, headers: dict):
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        with open(file_path, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("image", f, filename=os.path.basename(file_path), content_type="application/octet-stream")
            async with session.post(url, data=form, headers=headers) as resp:
                data = await resp.json(content_type=None)
                return resp.status, data


async def local_upscale(source: str, destination: str) -> str:
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
        image.save(destination, "JPEG", quality=95, optimize=True)
    return destination


@app.on_message(filters.command("upscale"))
async def upscale_image(_, message: Message):
    reply = message.reply_to_message
    if not reply or not reply.photo:
        return await message.reply_text("📎 Reply to an image.")

    status = await message.reply_text("🔄 Upscaling image...")
    local_path = None
    result_path = None
    try:
        local_path = await reply.download()
        # Local 2x Lanczos upscale (no external API).
        result_path = await local_upscale(local_path, local_path + ".2x.jpg")

        await status.delete()
        await message.reply_photo(result_path, caption="✨ Upscaled 2×")
    except Exception:
        try:
            await status.edit("❌ Upscaling failed. Please try another image.")
        except Exception:
            pass
    finally:
        for path in (local_path, result_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


@app.on_message(filters.command("getdraw"))
async def draw_image(_, message: Message):
    plan = await get_ai_plan(message.from_user.id)
    if plan == "none":
        return await message.reply_text("🔒 <b>AI Image Creation</b> requires VIP or VIP Pro.\nUse <code>/vip</code> to view plans.")
    allowed, remaining = await consume_ai_generation(message.from_user.id, "image", 3)
    if not allowed:
        return await message.reply_text("⏳ <b>Daily image limit reached.</b>\nYou can create up to <b>3 images per day</b>. Try again tomorrow.")
    reply = message.reply_to_message
    query = reply.text if reply and reply.text else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not query:
        return await message.reply_text("💬 Reply to text or provide a prompt.\nExample: `/getdraw a neon city at night`")

    status = await message.reply_text("🎨 Generating image...")
    final = None
    try:
        final = await generate_image(query)
        if not final or not os.path.exists(final):
            detail = getattr(config, "LAST_IMAGE_ERROR", "") or "Unknown image-generation error"
            return await status.edit(f"❌ Image generation failed.\n`{detail[:500]}`")

        await status.delete()
        await message.reply_photo(final, caption=query[:1000])
    except Exception as exc:
        await status.edit(f"❌ Image generation failed: `{type(exc).__name__}`")
    finally:
        if final and os.path.exists(final):
            try:
                os.remove(final)
            except Exception:
                pass
