"""Shared runtime objects.

Keeping the clients and provider objects in a dedicated module prevents
package-level circular imports when the bot is started with ``python -m
AquaVibe``.  Other modules import these objects from here instead of from
``AquaVibe.__init__``.
"""
from AquaVibe.core.bot import MusicBotClient
from AquaVibe.core.dir import StorageManager
from AquaVibe.core.userbot import Userbot
from AquaVibe.misc import dbb, heroku
from AquaVibe.log_config import LOGGER

# Prepare local directories and lightweight state before creating clients.
StorageManager()
dbb()
heroku()

# Create shared clients before loading modules that reference them.
app = MusicBotClient()
userbot = Userbot()

# Premium/custom emoji are attached explicitly by features that request them.
# Do not monkey-patch Pyrogram's global send/edit methods: that can inject
# unsupported entities into unrelated commands and break normal messages.

# Provider instances are created only after app/userbot exist.  This avoids the
# classic partial-package import failure during module startup.
from AquaVibe.platforms.Apple import AppleAPI
from AquaVibe.platforms.Carbon import CarbonAPI
from AquaVibe.platforms.Spotify import SpotifyAPI
from AquaVibe.platforms.Telegram import TeleAPI
from AquaVibe.platforms.AlternativeMedia import AlternativeMediaAPI

Apple = AppleAPI()
Carbon = CarbonAPI()
Spotify = SpotifyAPI()
Telegram = TeleAPI()
AlternativeMedia = AlternativeMediaAPI()

__all__ = [
    "LOGGER", "app", "userbot", "Apple", "Carbon", "Spotify",
    "Telegram", "AlternativeMedia",
]
