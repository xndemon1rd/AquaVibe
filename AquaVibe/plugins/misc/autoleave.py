# Authored By Dev © 2025
import asyncio
from datetime import datetime

from pyrogram.enums import ChatType

import config
from AquaVibe.core.runtime import app
from AquaVibe.core.call import StreamController, autoend
from AquaVibe.utils.database import get_assistant_number, get_client, is_active_chat, is_autoend


async def auto_leave():
    if config.AUTO_LEAVING_ASSISTANT:
        while not await asyncio.sleep(config.AUTO_LEAVE_ASSISTANT_TIME):
            from AquaVibe.core.userbot import assistants

            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ]:
                            if (
                                i.chat.id != config.LOGGER_ID
                                and i.chat.id != -1002077986660
                                and i.chat.id != -1002166290494
                            ):
                                if left == 20:
                                    continue
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except Exception:
                                        continue
                except Exception:
                    pass


asyncio.create_task(auto_leave())


async def auto_end():
    while not await asyncio.sleep(5):
        ender = await is_autoend()
        if not ender:
            continue
        for chat_id in autoend:
            timer = autoend.get(chat_id)
            if not timer:
                continue
            if datetime.now() > timer:
                if not await is_active_chat(chat_id):
                    autoend[chat_id] = {}
                    continue
                # The timer is created when only the assistant is present.
                # Re-check the VC before stopping: a listener may have joined
                # during that minute. Use the assistant assigned to this chat,
                # not a hard-coded assistant number.
                try:
                    assistant_number = await get_assistant_number(chat_id)
                    client = await get_client(assistant_number) if assistant_number else None
                    if client is not None:
                        participants = await client.get_participants(chat_id)
                        if len(participants) > 1:
                            autoend[chat_id] = {}
                            continue
                except Exception as exc:
                    # Never auto-leave on an uncertain participant check.
                    from AquaVibe.log_config import LOGGER
                    LOGGER(__name__).warning(
                        "Auto-end participant check failed for %s: %s: %s",
                        chat_id, type(exc).__name__, exc,
                    )
                    continue
                autoend[chat_id] = {}
                try:
                    await StreamController.stop_stream(chat_id)
                except Exception:
                    continue
                try:
                    await app.send_message(
                        chat_id,
                        "» ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʟᴇғᴛ ᴠɪᴅᴇᴏᴄʜᴀᴛ ʙᴇᴄᴀᴜsᴇ ɴᴏ ᴏɴᴇ ᴡᴀs ʟɪsᴛᴇɴɪɴɢ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
                    )
                except Exception:
                    continue


asyncio.create_task(auto_end())
