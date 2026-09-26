# Authored By Dev © 2025
import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AquaVibe.core.runtime import LOGGER, app, userbot
from AquaVibe.core.call import StreamController
from AquaVibe.misc import admin
from AquaVibe.plugins import ALL_MODULES
from AquaVibe.utils.database import get_banned_users, get_gbanned
from AquaVibe.utils.storage_guard import storage_maintenance_loop
from config import BANNED_USERS, STARTUP_VOICE_CHECK
from AquaVibe.utils.errors import install_global_error_logging


async def init():
    # Install lightweight global error logging before starting Telegram clients.
    install_global_error_logging()
    try:
        from AquaVibe.utils.error_detector import install as install_error_detector
        install_error_detector()
    except Exception as exc:
        LOGGER("AquaVibe").warning(f"Runtime error logger could not start: {exc}")
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ...")
        exit()

    await admin()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception:
        pass

    # Register every plugin handler BEFORE starting the bot client.
    # Pyrogram's normal plugin lifecycle registers handlers before its update
    # dispatcher starts; doing the same here avoids a race/compatibility issue
    # with pyrofork when handlers are added after app.start().
    loaded_modules = 0
    failed_modules = 0
    for all_module in ALL_MODULES:
        try:
            importlib.import_module("AquaVibe.plugins" + all_module)
            loaded_modules += 1
        except Exception as exc:
            failed_modules += 1
            LOGGER("AquaVibe.plugins").error(
                "Skipping plugin %s because it failed to import: %s: %s",
                all_module, type(exc).__name__, exc,
            )

    LOGGER("AquaVibe.plugins").info(
        "AquaVibe modules loaded: %s; skipped: %s", loaded_modules, failed_modules
    )

    # Pyrofork schedules handler registration on the dispatcher loop. Yield
    # once before starting the client so all decorator registrations queued
    # during module import are committed before Telegram updates arrive.
    await asyncio.sleep(0)

    if failed_modules:
        LOGGER("AquaVibe.plugins").warning(
            "Some plugins failed to import; affected commands will be unavailable."
        )

    # Start the bot only after all successfully imported handlers are registered.
    await app.start()
    # Run a conservative static repository audit after Telegram is connected.
    # It never blocks startup: findings are written locally and summarized to LOGGER_ID.
    try:
        from AquaVibe.utils.repo_audit import audit_repo, write_report
        audit = audit_repo()
        write_report(audit)
        summary = audit["summary"]
        LOGGER("AquaVibe.audit").info(
            "Repository audit: %s issues (high=%s, errors=%s, warnings=%s)",
            summary["issues"], summary["high"], summary["errors"], summary["warnings"],
        )
        if config.LOGGER_ID and (summary["high"] or summary["errors"]):
            await app.send_message(
                config.LOGGER_ID,
                "🧪 <b>AquaVibe repository audit</b>\n"
                f"🔴 High: <code>{summary["high"]}</code> | "
                f"🟠 Errors: <code>{summary["errors"]}</code> | "
                f"🟡 Warnings: <code>{summary["warnings"]}</code>\n"
                "📄 Run <code>/audit</code> as owner for the full report.",
            )
    except Exception as exc:
        LOGGER("AquaVibe.audit").warning("Repository audit failed: %s", exc)
    await userbot.start()
    await StreamController.start()

    # Do not make startup depend on a third-party sample URL or on an active
    # voice chat in LOGGER_ID. Playback is validated when a real /play starts.
    # Set STARTUP_VOICE_CHECK=true if you explicitly want the legacy probe.
    if STARTUP_VOICE_CHECK:
        try:
            await StreamController.stream_call("https://files.catbox.moe/6d0ejr.mp4")
        except NoActiveGroupCall:
            LOGGER("AquaVibe").warning(
                "Startup voice-chat check found no active call in LOGGER_ID; continuing because STARTUP_VOICE_CHECK is enabled."
            )
        except Exception as exc:
            LOGGER("AquaVibe").warning(f"Startup voice-chat check failed: {type(exc).__name__}: {exc}")

    await StreamController.decorators()
    storage_task = asyncio.create_task(storage_maintenance_loop())
    LOGGER("AquaVibe").info(
        "AquaVibe Music Robot Started Successfully..."
    )
    try:
        await idle()
    finally:
        storage_task.cancel()
        try:
            await storage_task
        except asyncio.CancelledError:
            pass
        await app.stop()
        await userbot.stop()
        LOGGER("AquaVibe").info("stopping AquaVibe music bot ...")


if __name__ == "__main__":
    # runtime.app and Pyrogram's dispatcher capture the current asyncio loop
    # when they are created. Keep startup on that exact loop so plugin
    # handlers are registered on the same loop that later receives updates.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
