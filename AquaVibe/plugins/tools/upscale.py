import os
import aiohttp
import aiofiles
from PIL import Image

from config import DEEP_API, OPENAI_API_KEY
from AquaVibe.core.runtime import app
from config import EXTERNAL_UPLOADS_ENABLED
from pyrogram import filters
from pyrogram.types import Message
from AquaVibe.utils.ai import generate_image


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
        if DEEP_API:
            code, resp = await post_file(
                "https://api.deepai.org/api/torch-srgan", local_path,
                headers={"api-key": DEEP_API},
            )
            image_url = resp.get("output_url") if isinstance(resp, dict) else None
            if code == 200 and image_url:
                result_path = await download_from_url(local_path + ".result.jpg", image_url)

        if not result_path:
            # No DeepAI key or DeepAI unavailable: keep /upscale usable with a local 2x upscale.
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
    reply = message.reply_to_message
    query = reply.text if reply and reply.text else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not query:
        return await message.reply_text("💬 Reply to text or provide a prompt.\nExample: `/getdraw a neon city at night`")

    status = await message.reply_text("🎨 Generating image...")
    temp_path = f"cache/{message.from_user.id}_{message.chat.id}_{message.id}.png"
    try:
        final = None
        if DEEP_API:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
                form = aiohttp.FormData()
                form.add_field("text", query)
                async with session.post("https://api.deepai.org/api/text2img", data=form, headers={"api-key": DEEP_API}) as r:
                    resp = await r.json(content_type=None)
            image_url = resp.get("output_url") if isinstance(resp, dict) else None
            if image_url:
                final = await download_from_url(temp_path, image_url)

        if not final and OPENAI_API_KEY:
            final = await generate_image(query)

        if not final:
            return await status.edit("🚫 Image generation is not configured. Add `DEEP_API` or `OPENAI_API_KEY` in the host variables.")

        await status.delete()
        await message.reply_photo(final, caption=query)
    except Exception as exc:
        await status.edit(f"❌ Image generation failed: `{type(exc).__name__}`")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
