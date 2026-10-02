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
try:
    from pyrogram.errors import PasswordHashInvalid
except Exception:
    PasswordHashInvalid = type("PasswordHashInvalid", (Exception,), {})
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton

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

InlineKeyboardButton = ColoredInlineKeyboardButton
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


async def _start_in_dm(user_id: int, started_from: str) -> bool:
    """(Re)start the generator in the user's private chat.

    Anyone can kick this off from a group, a channel, or the bot's own DM —
    but the phone number, OTP, 2FA password, API ID/API Hash and the final
    session string are always exchanged in private, never in group/channel
    history. Returns False if the bot cannot DM the user yet (they haven't
    started the bot in private).
    """
    try:
        dm = await app.send_message(
            user_id,
            "🔐 <b>String Session Generator</b>\n\n"
            f"You started this from a {started_from}. For security, the phone "
            "number, OTP, 2FA password, API ID/API Hash and the generated "
            "session are all handled in this private chat only.",
        )
        await _begin(user_id, dm)
        return True
    except Exception:
        return False


@app.on_callback_query(filters.regex(r"^session_gen_start$"))
async def session_gen_start(client, callback: CallbackQuery):
    if callback.message.chat.type == "private":
        await callback.answer()
        await _begin(callback.from_user.id, callback.message)
        return

    started_from = "channel" if callback.message.chat.type == "channel" else "group"
    ok = await _start_in_dm(callback.from_user.id, started_from)
    if ok:
        await callback.answer(
            "✅ Check your DM — I've opened the String Session Generator there.",
            show_alert=True,
        )
    else:
        await callback.answer(
            "❌ I can't message you privately yet. Open my bot in DM, press Start, "
            "then tap this button again.",
            show_alert=True,
        )


@app.on_message(filters.command("string") & filters.private)
async def string_command(client, message: Message):
    await _begin(message.from_user.id, message)


@app.on_message(filters.command("string") & ~filters.private)
async def string_group_command(client, message: Message):
    """Allow /string from groups and channels without exposing OTP/session
    data there. The actual login flow always continues in the user's
    private bot chat — this just makes /string reachable from anywhere.
    """
    user_id = message.from_user.id if message.from_user else 0
    if not user_id:
        return await message.reply_text("❌ I need a user account to start the session generator.")
    started_from = "channel" if message.chat.type == "channel" else "group"
    ok = await _start_in_dm(user_id, started_from)
    if ok:
        return await message.reply_text("✅ Check your private chat with me. The String Session Generator has been opened there.")
    return await message.reply_text(
        "❌ I can't message you privately. Open my bot in DM and press Start, then send /string again."
    )


@app.on_callback_query(filters.regex(r"^session_backend:(pyrogram|pyrofork|telethon)$"))
async def session_backend_select(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    state = _SESSIONS.get(user_id)
    if not state:
        return await callback.answer("Session generator expired. Use /string again.", show_alert=True)
    backend = callback.data.split(":", 1)[1]
    if backend == "telethon" and TelegramClient is None:
        return await callback.answer("Telethon is not installed on this bot.", show_alert=True)
    state.update({"backend": backend, "step": "api_id"})
    await callback.answer(BACKENDS[backend])
    try:
        await callback.message.edit_text(
            f"🔐 <b>{BACKENDS[backend]} Session Generator</b>\n\n"
            "Send your own <b>API ID</b> (a number) from "
            "<a href=\"https://my.telegram.org/apps\">my.telegram.org/apps</a>.\n\n"
            "Don't have one? Send /skip to use this bot's default API credentials.\n"
            "Use <code>/cancel</code> anytime.",
            reply_markup=_cancel_markup(),
            disable_web_page_preview=True,
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


def _has_active_session(_, __, message) -> bool:
    """Match only while the user is mid-way through the generator.

    Without this the handler claimed EVERY private text message in group 0,
    and Pyrogram stops at the first matching handler per group, so every
    command registered after this module (/speedtest, /stats, /stickerid,
    /stdl, /packkang, /tgm, /telegraph, /upscale, /getdraw, /extract,
    /waifu) never ran in private chat.
    """
    user = message.from_user
    if not user:
        return False
    state = _SESSIONS.get(user.id)
    if not state or state.get("step") == "backend":
        return False
    text = (message.text or "").strip()
    if text.startswith("/"):
        # Only /skip belongs to the generator; other commands keep working.
        return text.split()[0].split("@")[0].lower() == "/skip"
    return True


_active_session_filter = filters.create(_has_active_session)


@app.on_message(
    filters.private & filters.text
    & ~filters.command("string") & ~filters.command("cancel")
    & _active_session_filter
)
async def session_generator_input(client, message: Message):
    user_id = message.from_user.id
    state = _SESSIONS.get(user_id)
    if not state or state.get("step") == "backend":
        return
    state.setdefault("messages", []).append(message)
    step = state.get("step")
    backend = state.get("backend")

    if step == "api_id":
        text = message.text.strip()
        if text.lower() == "/skip":
            state.update({
                "api_id": int(config.API_ID),
                "api_hash": str(config.API_HASH),
                "step": "phone",
            })
            return await message.reply_text(
                "✅ Using this bot's default API credentials.\n\n"
                "Now send your phone number in international format, e.g. <code>+919876543210</code>."
            )
        if not text.isdigit():
            return await message.reply_text(
                "❌ API ID must be a number from my.telegram.org/apps, or send /skip to use the default."
            )
        state.update({"api_id": int(text), "step": "api_hash"})
        return await message.reply_text(
            "Now send your <b>API Hash</b> from the same my.telegram.org/apps page."
        )

    if step == "api_hash":
        text = message.text.strip()
        if not text or " " in text or len(text) < 10:
            return await message.reply_text("❌ That doesn't look like a valid API Hash. Try again, or /cancel.")
        state.update({"api_hash": text, "step": "phone"})
        return await message.reply_text(
            "Send your phone number in international format, e.g. <code>+919876543210</code>."
        )

    if step == "phone":
        phone = message.text.strip().replace(" ", "")
        if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 8:
            return await message.reply_text("❌ Invalid phone format. Send it like <code>+919876543210</code>.")
        try:
            api_id = int(state.get("api_id") or config.API_ID)
            api_hash = str(state.get("api_hash") or config.API_HASH)
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
        except ((SessionPasswordNeeded,) if backend in {"pyrogram", "pyrofork"} else (TeleSessionPasswordNeeded,)):
            state["step"] = "password"
            return await message.reply_text("🔒 <b>Two-step verification is enabled.</b>\nSend your Telegram 2FA password.")
        except ((PhoneCodeInvalid,) if backend in {"pyrogram", "pyrofork"} else (TelePhoneCodeInvalid,)):
            return await message.reply_text("❌ Invalid OTP. Try again.")
        except ((PhoneCodeExpired,) if backend in {"pyrogram", "pyrofork"} else (TelePhoneCodeExpired,)):
            await _cleanup(user_id)
            return await message.reply_text("⌛ OTP expired. Start again with /string.")
        except Exception as e:
            try:
                from AquaVibe.utils.errors import report_exception
                tb = "".join(__import__("traceback").format_exception(type(e), e, e.__traceback__))
                await report_exception(e, tb, "String Session Login Error", {"User ID": user_id, "Backend": backend, "Step": step})
            except Exception:
                pass
            await _cleanup(user_id)
            return await message.reply_text(f"❌ Login failed: <code>{type(e).__name__}</code>\n<code>{str(e)[:300]}</code>")
        return await _finish(user_id)

    if step == "password":
        password = message.text
        try:
            if backend in {"pyrogram", "pyrofork"}:
                await state["client"].check_password(password)
            else:
                await state["client"].sign_in(password=password)
        except Exception as e:
            if type(e).__name__ in {"PasswordHashInvalid", "PasswordHashInvalidError"}:
                return await message.reply_text("❌ Incorrect 2FA password. Try again.")
            try:
                from AquaVibe.utils.errors import report_exception
                tb = "".join(__import__("traceback").format_exception(type(e), e, e.__traceback__))
                await report_exception(e, tb, "String Session 2FA Error", {"User ID": user_id, "Backend": backend, "Step": step})
            except Exception:
                pass
            await _cleanup(user_id)
            return await message.reply_text(f"❌ 2FA verification failed: <code>{type(e).__name__}</code>\n<code>{str(e)[:300]}</code>")
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
        try:
            from AquaVibe.utils.errors import report_exception
            tb = "".join(__import__("traceback").format_exception(type(e), e, e.__traceback__))
            await report_exception(e, tb, "String Session Export Error", {"User ID": user_id, "Backend": backend})
        except Exception:
            pass
        await app.send_message(
            user_id,
            f"❌ <b>Could not export session</b>\n"
            f"Type: <code>{type(e).__name__}</code>\n"
            f"Reason: <code>{str(e)[:500]}</code>"
        )
    finally:
        await _cleanup(user_id)
