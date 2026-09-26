import os
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.types import Message
from AquaVibe.core.runtime import app


@app.on_message(filters.command("mmf"))
async def mmf(_, message: Message):
    reply_message = message.reply_to_message
    if not reply_message or not (reply_message.photo or reply_message.document or reply_message.animation):
        return await message.reply_text(
            "❌ Reply to a photo/image with `/mmf top text;bottom text`."
        )

    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Add text after /mmf. Example: `/mmf When it works;When it doesn't`"
        )

    text = message.text.split(None, 1)[1].strip()
    if not text:
        return await message.reply_text("❌ Please provide meme text.")

    status = await message.reply_text("🪄 Creating meme...")
    source = None
    output = None
    try:
        source = await app.download_media(reply_message)
        if not source or not os.path.isfile(source):
            raise ValueError("The replied media could not be downloaded.")
        output = await drawText(source, text)
        await app.send_document(message.chat.id, document=output)
        await status.delete()
    except Exception:
        await status.edit_text("❌ I couldn't create the meme from that media.")
    finally:
        for path in (source, output):
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


async def drawText(image_path, text):
    with Image.open(image_path) as original:
        img = original.convert("RGB")

    i_width, i_height = img.size
    font_path = "./AquaVibe/assets/default.ttf"
    m_font = ImageFont.truetype(font_path, max(20, int((70 / 640) * i_width)))

    parts = text.split(";", 1)
    upper_text = parts[0].strip()
    lower_text = parts[1].strip() if len(parts) == 2 else ""
    draw = ImageDraw.Draw(img)

    def draw_lines(value, y, bottom=False):
        if not value:
            return y
        current = y
        for line in textwrap.wrap(value, width=15) or [value]:
            bbox = m_font.getbbox(line)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = max(0, (i_width - w) / 2)
            yy = i_height - h - int((20 / 640) * i_width) if bottom else current
            for dx, dy in [(-2,0),(2,0),(0,-2),(0,2)]:
                draw.text((x+dx, yy+dy), line, font=m_font, fill=(0,0,0))
            draw.text((x, yy), line, font=m_font, fill=(255,255,255))
            current += h + 5
        return current

    draw_lines(upper_text, 10)
    draw_lines(lower_text, 10, bottom=True)

    output = "memify.webp"
    img.save(output, "WEBP", quality=90)
    return output
