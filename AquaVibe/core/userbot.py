# Authored By Dev © 2025
from pyrogram import Client

import config

from ..log_config import LOGGER

assistants = []
assistantids = []

from os import getenv

GROUPS_TO_JOIN = [x.strip() for x in getenv("GROUPS_TO_JOIN", "").split(",") if x.strip()]


# Initialize userbots
class Userbot:
    def __init__(self):
        if not config.ASSISTANTS_ENABLED:
            clients = [None] * 5
            self.one, self.two, self.three, self.four, self.five = clients
            return
        sessions = [config.STRING1, config.STRING2, config.STRING3, config.STRING4, config.STRING5]
        clients = []
        for index, session in enumerate(sessions, 1):
            clients.append(
                Client(
                    f"AquaVibeAssis{index}",
                    config.API_ID,
                    config.API_HASH,
                    session_string=session if session else None,
                    no_updates=True,
                )
            )
        self.one, self.two, self.three, self.four, self.five = clients

    async def start_assistant(self, client: Client, index: int):
        if not config.ASSISTANTS_ENABLED or client is None:
            return
        string_attr = [
            config.STRING1,
            config.STRING2,
            config.STRING3,
            config.STRING4,
            config.STRING5,
        ][index - 1]
        if not string_attr:
            return

        try:
            await client.start()
            # Join normal configured groups plus the log group when a public
            # username or invite link is supplied. Telegram does not allow a
            # userbot to join a private chat from its numeric chat ID alone.
            join_targets = list(GROUPS_TO_JOIN)
            if config.LOGGER_CHAT:
                join_targets.append(config.LOGGER_CHAT)
            elif config.LOGGER_INVITE_LINK:
                join_targets.append(config.LOGGER_INVITE_LINK)

            for group in join_targets:
                try:
                    await client.join_chat(group)
                    LOGGER(__name__).info(f"Assistant {index} joined {group}")
                except Exception as join_error:
                    # Already a member, private/inaccessible chat, or Telegram
                    # rate-limit: continue startup rather than killing assistant.
                    LOGGER(__name__).warning(
                        f"Assistant {index} could not join {group}: {type(join_error).__name__}"
                    )

            me = await client.get_me()
            client.id, client.name, client.username = me.id, me.first_name, me.username
            if index not in assistants:
                assistants.append(index)
            if me.id not in assistantids:
                assistantids.append(me.id)

            try:
                if config.LOGGER_ID:
                    await client.send_message(
                        config.LOGGER_ID, f"蒼響's Assistant {index} Started"
                    )
            except Exception as log_error:
                LOGGER(__name__).warning(
                    f"Assistant {index} could not access LOGGER_ID; continuing: {type(log_error).__name__}"
                )

            LOGGER(__name__).info(f"Assistant {index} Started as {client.name} (@{client.username or 'no_username'})")

        except Exception as e:
            LOGGER(__name__).error(f"Failed to start Assistant {index}: {type(e).__name__}: {e}")
            try:
                if getattr(client, "is_connected", False):
                    await client.stop()
            except Exception:
                pass

    async def start(self):
        LOGGER(__name__).info("Starting 蒼響's Assistants...")
        await self.start_assistant(self.one, 1)
        await self.start_assistant(self.two, 2)
        await self.start_assistant(self.three, 3)
        await self.start_assistant(self.four, 4)
        await self.start_assistant(self.five, 5)

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
            if config.STRING3:
                await self.three.stop()
            if config.STRING4:
                await self.four.stop()
            if config.STRING5:
                await self.five.stop()
        except Exception as e:
            LOGGER(__name__).error(f"Error while stopping assistants: {e}")
