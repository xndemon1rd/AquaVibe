# Authored By Dev © 2025
import os
import aiohttp
import aiofiles
from pyrogram import filters
from AquaVibe.core.runtime import app
from config import REMOVE_BG_API_KEY, EXTERNAL_UPLOADS_ENABLED

def generate_unique_filename(base_name: str) -> str:
    if os.path.exists(base_name):
        count = 1
        name, ext = os.path.splitext(base_name)
        while True:
            new_name = f"{name}_{count}{ext}"
            if not os.path.exists(new_name):
                return new_name
            count += 1
    return base_name

async def remove_background(image_path: str) -> tuple:
    if not REMOVE_BG_API_KEY:
        return False, {"title": "Not configured", "errors": [{"detail": "REMOVE_BG_API_KEY is not configured."}]}
    headers = {"X-API-Key": REMOVE_BG_API_KEY}
    async with aiohttp.ClientSession() as session:
        try:
            with open(image_path, "rb") as img:
                data = {"image_file": img.read()}
            async with session.post(
                "https://api.remove.bg/v1.0/removebg", headers=headers, data=data
            ) as response:

                if "image" not in response.headers.get("content-type", ""):
                    return False, await response.json()

                output_filename = generate_unique_filename("no_bg.png")
                async with aiofiles.open(output_filename, "wb") as out_file:
                    await out_file.write(await response.read())
                return True, output_filename

        except Exception as e:
            return False, {"title": "Unknown Error", "errors": [{"detail": str(e)}]}

@app.on_message(filters.command("rmbg"))
async def remove_bg_command(client, message):
    if not EXTERNAL_UPLOADS_ENABLED:
        return await message.reply_text("🔒 External image uploads are disabled by default.")
    status = await message.reply("🖌️ Processing your image...")
    replied = message.reply_to_message

    if not replied or not (replied.photo or (replied.document and (replied.document.mime_type or "").startswith("image/"))):
        await status.delete()
        return await message.reply_text("📎 Reply to a photo or image document with /rmbg.")

    try:
        downloaded_photo = await client.download_media(replied)
        if not downloaded_photo:
            return await status.edit("❌ I couldn't download that image.")
        success, result = await remove_background(downloaded_photo)
        os.remove(downloaded_photo)

        if not success:
            error = result["errors"][0]
            return await status.edit(f"⚠️ ERROR: {result['title']}\n{error.get('detail', '')}")

        await message.reply_photo(photo=result, caption="✅ Here's your image without background.")
        await message.reply_document(document=result)
        os.remove(result)
        await status.delete()

    except Exception as e:
        await status.edit(f"❌ Failed to process the image.\nError: {e}")
