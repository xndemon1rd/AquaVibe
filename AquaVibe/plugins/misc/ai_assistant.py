"""/ai text assistant and /cimage AI image generation."""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from html import escape

from pyrogram import filters
from pyrogram.types import Message

from AquaVibe.core.runtime import app
from AquaVibe.utils.ai import ask, generate_image
from config import BANNED_USERS
import config

_HISTORY = defaultdict(lambda: deque(maxlen=8))


def _prompt(message: Message) -> str:
    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1].strip()
    return ""


@app.on_message(filters.command("ai") & ~BANNED_USERS)
async def ai_command(_, message: Message):
    prompt = _prompt(message)
    if not prompt and message.reply_to_message:
        prompt = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not prompt:
        return await message.reply_text("🤖 <b>蒼響 AI</b>\n\nUse <code>/ai your question</code>.")
    status = await message.reply_text("🤖 Thinking…")
    history = list(_HISTORY[message.from_user.id])
    answer = await ask(prompt, history)
    _HISTORY[message.from_user.id].append({"role": "user", "content": prompt})
    _HISTORY[message.from_user.id].append({"role": "assistant", "content": answer[:4000]})
    await status.edit_text(f"🤖 <b>蒼響 AI</b>\n\n{escape(answer[:4000])}")


@app.on_message(filters.command("cimage") & ~BANNED_USERS)
async def cimage_command(_, message: Message):
    prompt = _prompt(message)
    if not prompt:
        return await message.reply_text("🎨 Use <code>/cimage your image prompt</code>.")
    status = await message.reply_text("🎨 Creating your image…")
    path = await generate_image(prompt)
    if not path or not Path(path).exists():
        detail = getattr(__import__("config"), "LAST_IMAGE_ERROR", "Unknown image-generation error")
        if "OPENAI_API_KEY missing" in detail:
            detail = "OPENAI_API_KEY is not available to the running process."
        return await status.edit_text(f"❌ <b>Image generation failed.</b>\n<code>{escape(str(detail)[:700])}</code>")
    try:
        await message.reply_photo(path, caption=f"🎨 <b>Created by 蒼響 AI</b>\n\n{prompt[:700]}")
        await status.delete()
    finally:
        Path(path).unlink(missing_ok=True)
