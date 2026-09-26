"""Interactive Telegram StringSession generator for Pyrogram/Pyrofork/Telethon.

Pyrogram and Pyrofork share the ``pyrogram`` import namespace; this deployment
uses Pyrofork, whose Pyrogram-compatible StringSession API powers both modes.
Telethon is a genuinely separate backend and is optional at runtime.
"""
import asyncio
from typing import Dict

from pyrogram import Client, filters
from pyrogram.errors import (
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton

try:
    from telethon import TelegramClient
    from telethon.errors import (
        PhoneCodeExpiredError as TelePhoneCodeExpired,
        PhoneCodeInvalidError as TelePhoneCodeInvalid,
        SessionPasswordNeededError as TeleSessionPasswordNeeded,
    )
    from telethon.sessions import StringSession as TeleStringSession
except Exception:
    TelegramClient = None
    TelePhoneCodeExpired = TelePhoneCodeInvalid = TeleSessionPasswordNeeded = None
    TeleStringSession = None

InlineKeyboardButton = StyledInlineKeyboardButton
_SESSIONS: Dict[int, dict] = {}
_TIMEOUT = 300

BACKENDS = {
    "pyrogram": "Pyrogram (Pyrofork-compatible)",
    "pyrofork": "Pyrofork",
    "telethon": "Telethon",
}


def _selector():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🐍 Pyrogram", callback_data="session_backend:pyrogram", aqua_style="primary")],
        [InlineKeyboardButton("⚡ Pyrofork", callback_data="session_backend:pyrofork", aqua_style="success")],
        [InlineKeyboardButton("🔷 Telethon", callback_data="session_backend:telethon", aqua_style="primary")],
        [InlineKeyboardButton("✖ Cancel", callback_data="session_gen_cancel", aqua_style="danger")],
    ])


def _cancel_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖ Cancel", callback_data="session_gen_cancel", aqua_style="danger")]])


async def _cleanup(user_id: int):
    state = _SESSIONS.pop(user_id, None)
    if not state:
        return
    client = state.get("client")
    if client:
        try:
            if state.get("backend") in {"pyrogram", "pyrofork"}:
                if client.is_connected:
                    await client.disconnect()
            else:
                await client.disconnect()
        except Exception:
            pass
    for msg in state.get("messages", []):
        try:
            await msg.delete()
        except Exception:
            pass


async def _expire(user_id: int):
    await asyncio.sleep(_TIMEOUT)
    if user_id in _SESSIONS:
        await _cleanup(user_id)
        try:
            await app.send_message(user_id, "⌛ Session generator expired. Start again with /string.")
        except Exception:
            pass


async def _begin(user_id: int, reply_target):
    await _cleanup(user_id)
    sent = await reply_target.reply_text(
        "🔐 <b>String Session Generator</b>\n\n"
        "Select the Python Telegram library you want to use:",
        reply_markup=_selector(),
    )
    _SESSIONS[user_id] = {"step": "backend", "messages": [sent]}
    asyncio.create_task(_expire(user_id))


@app.on_callback_query(filters.regex(r"^session_gen_start$"))
async def session_gen_start(client, callback: CallbackQuery):
    if callback.message.chat.type != "private":
        return await callback.answer("Open this in private chat.", show_alert=True)
    await callback.answer()
    await _begin(callback.from_user.id, callback.message)


@app.on_message(filters.command("string") & filters.private)
async def string_command(client, message: Message):
    await _begin(message.from_user.id, message)


@app.on_callback_query(filters.regex(r"^session_backend:(pyrogram|pyrofork|telethon)$"))
async def session_backend_select(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    state = _SESSIONS.get(user_id)
    if not state:
        return await callback.answer("Session generator expired. Use /string again.", show_alert=True)
    backend = callback.data.split(":", 1)[1]
    if backend == "telethon" and TelegramClient is None:
        return await callback.answer("Telethon is not installed on this bot.", show_alert=True)
    state.update({"backend": backend, "step": "phone"})
    await callback.answer(BACKENDS[backend])
    try:
        await callback.message.edit_text(
            f"🔐 <b>{BACKENDS[backend]} Session Generator</b>\n\n"
            "Send your phone number in international format, e.g. <code>+919876543210</code>.\n"
            "Use <code>/cancel</code> anytime.\n\n"
            "⚠️ Never share the generated session string with anyone.",
            reply_markup=_cancel_markup(),
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex(r"^session_gen_cancel$"))
async def session_gen_cancel(client, callback: CallbackQuery):
    await _cleanup(callback.from_user.id)
    await callback.answer("Cancelled.")
    try:
        await callback.message.edit_text("❌ String session generator cancelled.")
    except Exception:
        pass


@app.on_message(filters.command("cancel") & filters.private)
async def session_gen_cancel_command(client, message: Message):
    if message.from_user.id in _SESSIONS:
        await _cleanup(message.from_user.id)
        await message.reply_text("❌ String session generator cancelled.")
    else:
        await message.reply_text("No active session generator.")


@app.on_message(filters.private & filters.text & ~filters.command("string") & ~filters.command("cancel"))
async def session_generator_input(client, message: Message):
    user_id = message.from_user.id
    state = _SESSIONS.get(user_id)
    if not state or state.get("step") == "backend":
        return
    state.setdefault("messages", []).append(message)
    step = state.get("step")
    backend = state.get("backend")

    if step == "phone":
        phone = message.text.strip().replace(" ", "")
        if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 8:
            return await message.reply_text("❌ Invalid phone format. Send it like <code>+919876543210</code>.")
        try:
            api_id = int(config.API_ID)
            api_hash = str(config.API_HASH)
            if backend in {"pyrogram", "pyrofork"}:
                # Start a completely empty in-memory session. Passing an
                # encoded/empty StringSession here is version-sensitive and
                # was the reason /string could fail before the OTP step.
                # Pyrogram/Pyrofork export the final string with
                # export_session_string() after authorization.
                session_client = Client(
                    name=f"AquaString_{user_id}", api_id=api_id, api_hash=api_hash,
                    in_memory=True,
                )
                await session_client.connect()
                sent_code = await session_client.send_code(phone)
                state.update({"step": "code", "phone": phone, "phone_code_hash": sent_code.phone_code_hash, "client": session_client})
            else:
                session_client = TelegramClient(TeleStringSession(), api_id, api_hash)
                await session_client.connect()
                sent_code = await session_client.send_code_request(phone)
                state.update({"step": "code", "phone": phone, "phone_code_hash": sent_code.phone_code_hash, "client": session_client})
            await message.reply_text("📩 <b>OTP sent.</b>\n\nSend the Telegram login code here.")
        except PhoneNumberInvalid:
            await _cleanup(user_id)
            await message.reply_text("❌ Telegram rejected that phone number.")
        except Exception as e:
            await _cleanup(user_id)
            await message.reply_text(f"❌ Could not start login: <code>{type(e).__name__}</code>")
        return

    if step == "code":
        code = message.text.strip().replace(" ", "")
        if not code.isdigit():
            return await message.reply_text("❌ Send only the numeric Telegram login code.")
        try:
            if backend in {"pyrogram", "pyrofork"}:
                await state["client"].sign_in(phone_number=state["phone"], phone_code_hash=state["phone_code_hash"], phone_code=code)
            else:
                await state["client"].sign_in(phone=state["phone"], code=code, phone_code_hash=state["phone_code_hash"])
        except SessionPasswordNeeded if backend in {"pyrogram", "pyrofork"} else TeleSessionPasswordNeeded:
            state["step"] = "password"
            return await message.reply_text("🔒 <b>Two-step verification is enabled.</b>\nSend your Telegram 2FA password.")
        except PhoneCodeInvalid if backend in {"pyrogram", "pyrofork"} else TelePhoneCodeInvalid:
            return await message.reply_text("❌ Invalid OTP. Try again.")
        except PhoneCodeExpired if backend in {"pyrogram", "pyrofork"} else TelePhoneCodeExpired:
            await _cleanup(user_id)
            return await message.reply_text("⌛ OTP expired. Start again with /string.")
        except Exception as e:
            await _cleanup(user_id)
            return await message.reply_text(f"❌ Login failed: <code>{type(e).__name__}</code>")
        return await _finish(user_id)

    if step == "password":
        password = message.text
        try:
            if backend in {"pyrogram", "pyrofork"}:
                await state["client"].check_password(password)
            else:
                await state["client"].sign_in(password=password)
        except Exception as e:
            if type(e).__name__ in {"PasswordHashInvalid", "PasswordHashInvalidError", "PasswordHashInvalidError"}:
                return await message.reply_text("❌ Incorrect 2FA password. Try again.")
            await _cleanup(user_id)
            return await message.reply_text(f"❌ 2FA verification failed: <code>{type(e).__name__}</code>")
        return await _finish(user_id)


async def _finish(user_id: int):
    state = _SESSIONS.get(user_id)
    if not state or not state.get("client"):
        return
    backend = state.get("backend")
    try:
        if backend in {"pyrogram", "pyrofork"}:
            session_string = await state["client"].export_session_string()
        else:
            session_string = state["client"].session.save()
        await app.send_message(
            user_id,
            f"✅ <b>{BACKENDS[backend]} String Session Generated</b>\n\n"
            f"<code>{session_string}</code>\n\n"
            "⚠️ This string gives access to the Telegram account session. "
            "Do not share it, post it publicly, or commit it to GitHub."
        )
    except Exception as e:
        await app.send_message(user_id, f"❌ Could not export session: <code>{type(e).__name__}</code>")
    finally:
        await _cleanup(user_id)
