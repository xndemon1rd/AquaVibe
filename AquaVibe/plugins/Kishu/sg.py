import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.raw.functions.messages import DeleteHistory
from AquaVibe.core.runtime import userbot as us, app
from AquaVibe.core.userbot import assistants


def _active_userbot():
    for index in assistants:
        bot = getattr(us, {1:"one", 2:"two", 3:"three", 4:"four", 5:"five"}.get(index, ""), None)
        if bot:
            return bot
    return None


@app.on_message(filters.command("sg"))
async def sg(client: Client, message: Message):
    if not assistants:
        return await message.reply("❌ No active assistant is available for /sg.")

    ubot = _active_userbot()
    if not ubot:
        return await message.reply("❌ No active assistant is available for /sg.")

    status = await message.reply("🔎 Checking username history...")
    try:
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user_id = message.reply_to_message.from_user.id
        elif len(message.command) > 1:
            target = message.command[1].strip()
            if target.isdigit():
                target_user_id = int(target)
            else:
                target_user_id = (await client.get_users(target)).id
        else:
            return await status.edit("❌ Reply to a user or use `/sg username_or_id`.")

        bot_name = "sangmata_bot"
        sent = await ubot.send_message(bot_name, str(target_user_id))
        await sent.delete()
        await asyncio.sleep(2)

        found = None
        async for result in ubot.search_messages(bot_name, query=str(target_user_id), limit=10):
            if result and (result.text or result.caption):
                found = result.text or result.caption
                break

        if not found:
            async for result in ubot.get_chat_history(bot_name, limit=10):
                if result and (result.text or result.caption):
                    found = result.text or result.caption
                    break

        if found:
            await message.reply_text(found)
        else:
            await message.reply_text("🤖 No username history was returned.")
    except Exception:
        await status.edit("❌ /sg could not contact the history service. Try again later.")
        return
    finally:
        try:
            peer = await ubot.resolve_peer(bot_name)
            await ubot.send(DeleteHistory(peer=peer, max_id=0, revoke=True))
        except Exception:
            pass

    try:
        await status.delete()
    except Exception:
        pass
