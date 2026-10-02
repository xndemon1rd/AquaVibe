"""蒼響's categorized command/help interface with Telegram custom emoji."""
from typing import Union

from pyrogram import Client, filters, types
from pyrogram.enums import MessageEntityType
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.database import get_lang
from AquaVibe.utils import bot_sys_stats
from AquaVibe.utils.decorators.language import LanguageStart, languageCB
from AquaVibe.utils.inline.start import private_panel
from AquaVibe.utils.welcome import welcome_caption
from AquaVibe.utils.owner_commands import OWNER_COMMANDS
from AquaVibe.utils.premium_emoji import custom_emoji_entities, _utf16_len
from config import BANNED_USERS, HELP_IMG_URL
from strings import get_string
from AquaVibe.utils.command_catalog import ALL_COMMANDS
from AquaVibe.utils.command_help import COMMAND_HELP, OWNER as _OWNER_LABEL, get_help
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
InlineKeyboardButton = ColoredInlineKeyboardButton

# ─────────────────────────── catalogue layout ───────────────────────────
# Order here = order on screen.  A command lives in the FIRST category that
# lists it (no duplicates), and only commands that really exist are shown.
CATEGORY_ORDER = ["music", "vc", "ai", "tools", "profile", "economy", "anime", "fun", "mod", "group", "other"]

CATEGORY_EMOJI = {
    "music": "🎶", "vc": "📡", "ai": "🤖", "tools": "🧩", "profile": "👤", "economy": "💎",
    "anime": "🌸", "fun": "🎲", "mod": "🔨", "group": "⚙️", "other": "📦", "owner": "🚧",
}
CATEGORY_TITLES = {
    "music": "Music", "vc": "Channel & VC", "ai": "AI Studio", "tools": "Tools",
    "profile": "Profile", "economy": "Economy", "anime": "Anime", "fun": "Fun & Games", "mod": "Moderation",
    "group": "Group Setup", "other": "More", "owner": "Owner Panel",
}
CATEGORY_BLURB = {
    "music": "Play songs & control the queue",
    "vc": "Channel play, voice-chat tools & modes",
    "ai": "Chat, images & smart helpers",
    "tools": "Utilities, converters & diagnostics",
    "profile": "Profiles, levels & user info",
    "economy": "Coins, rewards & the shop",
    "anime": "Anime search, waifus & anime GIF reactions",
    "fun": "Games, reactions & social fun",
    "mod": "Ban, mute, warn & clean-up",
    "group": "Rules, welcome, filters & protection",
    "other": "Everything else",
}

CATEGORY_COMMANDS = {
    "music": {
        "play", "vplay", "pause", "resume", "skip", "stop", "end", "queue", "player",
        "playing", "next", "shuffle", "seek", "seekback", "speed", "slow", "loop",
        "history", "myhistory", "toptracks", "lyrics", "playback", "playforce", "vplayforce", "vend",
    },
    "vc": {
        "cloop", "cnext", "cpause", "cresume", "cskip", "cseek", "cseekback", "cshuffle",
        "channelplay", "activevc", "ac", "vcinfo", "vcmembers", "vstart", "voiceall",
        "autoend", "playmode", "mode", "assistantjoin", "cplay", "cvplay", "cplayforce", "cvplayforce",
    },
    "ai": {"ai", "chat", "cimage", "imposter", "upscale", "voices", "tts", "remember", "forget"},
    "tools": {
        "ping", "stats", "speedtest", "spt", "bug", "lang", "setlang", "font", "fonts",
        "encode", "decode", "short", "unshort", "qr", "rmbg", "stickerid", "string", "pypi",
        "domain", "getdraw", "check", "ip", "weather", "telegraph", "tgm", "write", "extract",
        "remind", "reminder", "remindme", "poll", "day", "sg", "stdl", "q", "kang", "packkang",
    },
    "profile": {
        "profile", "setphoto", "setbanner",
        "banner", "id", "info", "user",
        "userinfo", "groupinfo", "level", "levels", "mylevel", "rank", "rep", "reputation",
        "leaderboard", "top", "ranking", "rankings", "afk", "membership",
    },
    "economy": {
        "balance", "bal", "daily", "weekly", "wallet", "coins", "economy", "give", "toprich",
        "rich", "shop", "store", "jackpot", "vip", "rob", "checkin",
    },
    "anime": {
        # search + images
        "anime", "asearch", "waifu",
        # anime GIF reactions (nekos.best) -- exactly the keys of misc/waifufxn.py
        "punch", "slap", "hug", "bite", "kiss", "highfive", "shoot", "dance", "happy", "baka",
        "pat", "nod", "nope", "cuddle", "feed", "bored", "nom", "yawn", "facepalm", "tickle",
        "yeet", "think", "blush", "smug", "wink", "peck", "smile", "wave", "poke", "stare",
        "shrug", "sleep", "lurk",
    },
    "fun": {
        "rps", "rockpaperscissors", "quiz", "trivia", "wordle", "word", "chess", "elo", "chesstop",
        "uno", "unoend", "whisper", "dice", "ball", "basket", "dart", "football", "truth", "dare", "wish",
        "movie", "meme", "couple", "love", "cute", "cutie", "mmf", "lesbian", "gay",
        "baka", "bite", "blush", "bored", "cuddle", "dance",
        "facepalm", "feed", "happy", "highfive", "hug", "kiss", "lurk", "nod", "nom", "nope",
        "pat", "peck", "poke", "punch", "shoot", "slap", "sleep", "smile",
        "chessleaderboard", "kill", "shield", "protection", "revive", "topkill",
        "propose", "marriage", "married", "divorce", "shippering",
    },
    "mod": {
        "ban", "unban", "tban", "dban", "sban", "kick", "kickme", "mute", "unmute", "tmute",
        "warn", "warnings", "unwarn", "clearwarnings", "setwarnlimit", "promote", "fullpromote",
        "demote", "tempadmin", "purge", "spurge", "purgefrom", "deleteall", "del", "pin",
        "unpin", "unpinall", "muteall", "banall", "report", "zombies",
        "hide", "tagall",
    },
    "group": {
        "settings", "groupdata", "gstats", "staff", "admins", "auth", "unauth", "authlist",
        "authusers", "setphoto", "removephoto", "settitle", "setdiscription", "rules", "setrules", "setwelcome", "setgoodbye", "goodbye", "antilink",
        "addbadword", "removebadword", "badwords", "setfloodlimit", "flood", "lock", "unlock",
        "captcha", "raidmode", "raidstatus", "protect", "cleanup", "link", "givelink",
        "filter", "filters", "get", "save", "notes", "clear", "cancel",
        "checkins", "reactions", "quiet", "chatty", "groupbot", "groupmode",
    },
}

# Bot-admin / owner tools: NOT shown to normal users.  They appear in the Owner Panel.
OWNER_EXTRA = {
    "social": "Switch social features on or off for a group.",
    "unomap": "Link a UNO sticker to a card (reply to a sticker).",
    "reboot": "Restart the bot process.",
    "maintenance": "Toggle maintenance mode for the whole bot.",
    "audit": "Run a repository/error audit.",
    "repoaudit": "Alias of /audit.",
    "errorscan": "Alias of /audit.",
    "runtimeerrors": "Show recent runtime errors.",
    "recenterrors": "Alias of /runtimeerrors.",
    "logs": "Fetch the bot logs.",
    "logger": "Toggle activity logging to the log group.",
    "mongochk": "Check the MongoDB connection.",
    "reload": "Refresh the admin cache in this group.",
    "refresh": "Alias of /reload.",
    "admincache": "Alias of /reload.",
    "botschk": "Check which bots are in this group.",
    "bots": "List the bots in this group.",
    "block": "Block a user from using the bot.",
    "unblock": "Unblock a user.",
    "blocked": "List blocked users.",
    "blockedusers": "Alias of /blocked.",
    "blusers": "Alias of /blocked.",
    "blchat": "Blacklist a chat.",
    "blchats": "List blacklisted chats.",
    "blacklistedchats": "Alias of /blchats.",
    "unblchat": "Remove a chat from the blacklist.",
    "unblacklistchat": "Alias of /unblchat.",
    "whitelistchat": "Alias of /unblchat.",
    "userbotleave": "Make the assistant leave this group.",
}

DESCRIPTIONS = {
    "start": "Open 蒼響's welcome menu and quick-access buttons.",
    "toptracks": "Show your most-played tracks or global listening trends.",
    "remind": "Set a reminder for seconds, minutes, hours or days.",
    "poll": "Create a Telegram poll with 2–10 options.",
    "rps": "Play Rock, Paper, Scissors with inline buttons.",
    "quiz": "Play a random trivia question.",
    "trivia": "Alias for /quiz.",
    "wordle": "Play a 5-letter Wordle game.",
    "word": "Alias for /wordle.",
    "help": "Open this categorized command guide.",
    "play": "Search for a song and start audio playback.",
    "q": "Create a quote sticker from a replied message.",
    "kang": "Add replied media to your Telegram sticker pack.",
    "vplay": "Search for a video and start video playback when supported.",
    "pause": "Pause the current playback.",
    "resume": "Resume paused playback.",
    "skip": "Skip the current track and continue the queue.",
    "stop": "Stop playback and clear the active player session.",
    "queue": "Show tracks currently waiting in the queue.",
    "player": "Open the current player and its controls.",
    "playing": "Show information about the track currently playing.",
    "lyrics": "Find lyrics for a requested song when available.",
    "ai": "Ask 蒼響's configured AI provider a question.",
    "cimage": "Request an AI-generated image through the configured provider.",
    "profile": "View your 蒼響 profile information.",
    "settings": "Open group settings available to authorized users.",
    "id": "Show the Telegram ID of yourself or a replied user.",
    "info": "Show Telegram information about a user.",
    "ping": "Check 蒼響's response latency.",
    "string": "Generate a Pyrogram, Pyrofork or Telethon StringSession.",
    "bug": "Send a bug report through the configured reporting system.",
    "backup": "Create a configured bot/database backup; owner only.",
    "banner": "Show a configured bot banner; /banner 1 or /banner 2 selects a slot.",
    "raidmode": "Enable or disable raid protection with a join-rate trigger.",
    "raidstatus": "Show current raid and advanced protection status.",
    "protect": "Toggle AquaVibe's umbrella advanced group-protection mode.",
    "setgoodbye": "Set a custom goodbye message with {name} and {group} variables.",
    "goodbye": "Enable or disable custom goodbye messages.",
    "cleanup": "Delete recent messages sent by AquaVibe.",
    "purgefrom": "Delete messages from a replied starting point through the command.",
    "unpinall": "Remove all pinned messages from the group.",
    "setbanner1": "Owner only: reply to an image with /setbanner1 to save banner slot 1.",
    "setbanner2": "Owner only: reply to an image with /setbanner2 to save banner slot 2.",
}



# Command-specific usage examples. Commands that accept a reply or optional
# argument get a concrete example instead of the generic /command placeholder.
USAGE = {
    "play": "/play <song name or URL>  — e.g. /play Blinding Lights",
    "vplay": "/vplay <video/song name or URL>",
    "pause": "/pause  — pause the current track",
    "resume": "/resume  — resume playback",
    "skip": "/skip  — skip current track",
    "stop": "/stop  — stop playback and clear queue",
    "end": "/end  — stop the voice chat player",
    "queue": "/queue  — show waiting tracks",
    "player": "/player  — open player controls",
    "playing": "/playing  — show current track",
    "next": "/next  — play the next queued track",
    "shuffle": "/shuffle  — shuffle the queue",
    "seek": "/seek <seconds>  — e.g. /seek 90",
    "seekback": "/seekback <seconds>  — e.g. /seekback 15",
    "speed": "/speed <0.5-2.0>  — e.g. /speed 1.25",
    "slow": "/slow  — lower playback speed",
    "loop": "/loop  — toggle track loop",
    "cloop": "/cloop  — toggle current-track loop",
    "lyrics": "/lyrics <song name>  — e.g. /lyrics Believer",
    "ai": "/ai <question>  or reply to a message with /ai",
    "cimage": "/cimage <prompt>  — e.g. /cimage cyberpunk ocean",
    "string": "/string  — select Pyrogram, Pyrofork or Telethon",
    "q": "Reply to a message, then send /q",
    "kang": "Reply to a sticker/photo, then send /kang",
    "stickerid": "Reply to a sticker, then send /stickerid",
    "stdl": "Reply to a sticker, then send /stdl",
    "packkang": "Reply to sticker/media, then send /packkang",
    "raidmode": "/raidmode on|off [join_limit] [seconds]",
    "raidstatus": "/raidstatus  — show raid-protection status",
    "protect": "/protect on|off  — enable/disable advanced protection",
    "setgoodbye": "/setgoodbye Goodbye {name} from {group}!",
    "goodbye": "/goodbye on|off",
    "cleanup": "/cleanup <1-100>  — remove recent bot messages",
    "purgefrom": "Reply to the first message, then /purgefrom",
    "unpinall": "/unpinall  — clear all pinned messages",
    "id": "/id  — or reply to a user/message with /id",
    "info": "/info  — or reply to a user with /info",
    "profile": "/profile  — view your profile",
    "setlang": "/setlang <language>",
    "lang": "/lang  — choose/set language",
    "font": "/font <text>  — e.g. /font Hello Aqua",
    "encode": "/encode <text>",
    "decode": "/decode <hex text>",
    "short": "/short <URL>",
    "unshort": "/unshort <short URL>",
    "qr": "/qr <text or URL>",
    "rmbg": "Reply to an image, then send /rmbg",
    "tts": "/tts <text>",
    "telegraph": "Reply to media/text, then send /telegraph",
    "tgm": "Reply to media/text, then send /tgm",
    "weather": "/weather <city>  — e.g. /weather Pune",
    "pypi": "/pypi <package>",
    "domain": "/domain <domain>",
    "ip": "/ip <IP or domain>",
    "check": "/check <username/link/value>",
    "stats": "/stats  — bot/system statistics",
    "speedtest": "/speedtest  — run network speed test",
    "spt": "/spt  — speed-test shortcut",
    "warn": "Reply to a user, then /warn [reason]",
    "warnings": "Reply to a user, then /warnings",
    "unwarn": "Reply to a user, then /unwarn",
    "clearwarnings": "Reply to a user, then /clearwarnings",
    "setwarnlimit": "/setwarnlimit <number>  — e.g. /setwarnlimit 3",
    "rules": "/rules  — show group rules",
    "setrules": "/setrules <rules text>  — admin only",
    "setwelcome": "/setwelcome <welcome text>  — admin only",
    "report": "Reply to a message, then /report [reason]",
    "antilink": "/antilink on|off",
    "addbadword": "/addbadword <word>",
    "removebadword": "/removebadword <word>",
    "badwords": "/badwords  — list configured words",
    "flood": "/flood on|off",
    "setfloodlimit": "/setfloodlimit <messages>  — e.g. /setfloodlimit 6",
    "lock": "/lock <type>  — e.g. /lock links",
    "unlock": "/unlock <type>  — e.g. /unlock links",
    "captcha": "/captcha on|off",
    "mute": "Reply to a user, then /mute [reason]",
    "unmute": "Reply to a user, then /unmute",
    "ban": "Reply to a user, then /ban [reason]",
    "unban": "Reply to a user, then /unban",
    "kick": "Reply to a user, then /kick",
    "tmute": "Reply to a user, then /tmute <duration>  — e.g. /tmute 10m",
    "tban": "Reply to a user, then /tban <duration>",
    "purge": "Reply to the first message, then /purge",
    "pin": "Reply to a message, then /pin",
    "unpin": "Reply to a pinned message, then /unpin",
    "promote": "Reply to a user, then /promote",
    "demote": "Reply to an admin, then /demote",
    "admins": "/admins  — list group admins",
    "staff": "/staff  — show group staff",
    "groupdata": "/groupdata  — show stored group configuration",
    "settings": "/settings  — open group settings",
    "link": "/link  — get group invite link",
    "givelink": "/givelink  — get group invite link",
    "activevc": "/activevc  — show active voice chats",
    "ac": "/ac  — active VC shortcut",
    "vcinfo": "/vcinfo  — show VC information",
    "vcmembers": "/vcmembers  — show VC participants",
    "vstart": "/vstart  — start the configured VC session",
    "playback": "/playback  — show playback controls/info",
    "playmode": "/playmode <mode>",
    "mode": "/mode <mode>",
    "history": "/history  — show playback history",
    "myhistory": "/myhistory  — show your playback history",
    "toptracks": "/toptracks  — show top tracks",
    "remind": "/remind <time> <text>  — e.g. /remind 10m Drink water",
    "poll": "/poll <question> | <option 1> | <option 2> ...",
    "quiz": "/quiz  — start a quiz",
    "trivia": "/trivia  — start trivia",
    "wordle": "/wordle  — start Wordle",
    "word": "/word  — Wordle shortcut",
    "rps": "/rps  — start Rock Paper Scissors",
    "couple": "/couple  — find a group couple",
    "meme": "/meme  — get a meme",
    "football": "/football  — football game",
}


# ─────────────────────────── text builder ───────────────────────────
_KIND = {
    "b": MessageEntityType.BOLD,
    "i": MessageEntityType.ITALIC,
    "c": MessageEntityType.CODE,
    "q": MessageEntityType.BLOCKQUOTE,
}


class _Text:
    """Tiny rich-text builder: exact UTF-16 offsets for bold/italic/code/quote
    entities, plus the bot's premium custom-emoji entities on top."""

    def __init__(self):
        self._buf = []
        self._len = 0
        self._ents = []

    def add(self, text, *kinds):
        if not text:
            return self
        start = self._len
        self._buf.append(text)
        self._len += _utf16_len(text)
        for k in kinds:
            self._ents.append((k, start, self._len - start))
        return self

    def nl(self, n=1):
        return self.add("\n" * n)

    def mark(self):
        return self._len

    def wrap(self, kind, start):
        if self._len > start:
            self._ents.append((kind, start, self._len - start))
        return self

    @property
    def text(self):
        return "".join(self._buf)

    @property
    def length(self):
        return self._len

    @property
    def entities(self):
        ents = [MessageEntity(type=_KIND[k], offset=o, length=n) for k, o, n in self._ents if n > 0]
        ents += custom_emoji_entities(self.text, blockquote=False)
        ents.sort(key=lambda e: (e.offset, -e.length))
        return ents


# ─────────────────────────── catalogue data ───────────────────────────
_FIRST = [
    "play", "vplay", "pause", "resume", "skip", "stop", "end", "queue", "player", "loop",
    "shuffle", "seek", "lyrics", "ai", "cimage", "ping", "stats", "profile", "id", "info",
    "daily", "balance", "bal", "ban", "mute", "warn", "kick", "promote", "settings",
    "rps", "quiz", "wordle", "chess", "uno",
    "anime", "asearch", "waifu",
]
PAGE_SIZE = 12
CAPTION_LIMIT = 980  # Telegram caption cap is 1024


def _sort_key(cmd):
    return (_FIRST.index(cmd) if cmd in _FIRST else 999, cmd)



_EXTRA_DESCRIPTIONS = {
    "ac": "Shortcut for /activevc.", "activevc": "Show the voice chats currently active.",
    "addbadword": "Add a word to the group's banned-words list.", "admins": "List the admins of this group.",
    "afk": "Mark yourself away; the bot tells people who mention you.",
    "antilink": "Automatically delete links sent by members.", "assistantjoin": "Invite the assistant account to this group.",
    "auth": "Authorize a user to control the player without being admin.", "authlist": "Show authorized users.",
    "authusers": "Show authorized users.", "autoend": "Auto-leave the voice chat when nobody is listening.",
    "badwords": "Show this group's banned words.", "bal": "Show your coin balance.", "ball": "Play a ball game.",
    "ban": "Ban a user from the group.", "basket": "Play a basketball game.", "bored": "Send a bored reaction.",
    "cancel": "Cancel the current pending action.", "captcha": "Ask new members to verify they are human.",
    "channelplay": "Link a channel and play music into it from a group.", "check": "Check a username, link or value.",
    "clear": "Delete a saved note or filter.", "clearwarnings": "Reset all warnings of a user.",
    "cloop": "Loop the current track (channel play).", "cnext": "Play the next track (channel play).",
    "coins": "Show your coin balance.", "couple": "Pick today's couple from the group.",
    "cpause": "Pause playback (channel play).", "cresume": "Resume playback (channel play).",
    "cseek": "Seek forward (channel play).", "cseekback": "Seek backward (channel play).",
    "cshuffle": "Shuffle the queue (channel play).", "cskip": "Skip the track (channel play).",
    "cute": "Rate how cute someone is.", "daily": "Claim your daily coin reward.", "dare": "Get a random dare.",
    "dart": "Throw a dart.", "day": "Show today's day and date info.", "dban": "Delete the replied message and ban its sender.",
    "decode": "Decode hex text back to normal text.", "del": "Delete the replied message.",
    "deleteall": "Delete all messages of a user in the group.", "demote": "Remove a user's admin rights.",
    "dice": "Roll a dice.", "domain": "Look up information about a domain.", "economy": "Show economy info and settings.",
    "encode": "Encode text to hex.", "end": "Stop the voice-chat player.", "extract": "Extract text or data from a message or file.",
    "filter": "Save an auto-reply for a keyword.", "filters": "List this group's filters.", "flood": "Turn anti-flood protection on or off.",
    "font": "Convert text into stylish fonts.", "football": "Play a football game.", "fullpromote": "Promote a user with full admin rights.",
    "get": "Get a saved note.", "getdraw": "Get a drawing or image from a link.", "givelink": "Get the group's invite link.",
    "groupdata": "Show stored settings for this group.", "groupinfo": "Show information about this group.",
    "hide": "Hide the replied message or content.", "history": "Show this chat's playback history.",
    "imposter": "Play the imposter word game.", "ip": "Look up an IP address or domain.", "jackpot": "Try your luck at the jackpot.",
    "kick": "Remove a user from the group (they can rejoin).", "kickme": "Leave the group yourself.",
    "lang": "Choose the bot's language.", "leaderboard": "Show the top members.", "level": "Show your level and XP.",
    "levels": "Show the level leaderboard.", "link": "Get the group's invite link.", "lock": "Lock a message type in the group.",
    "loop": "Toggle loop for the current track.", "love": "Check love compatibility.", "membership": "Show your membership status.",
    "meme": "Get a random meme.", "mmf": "Send a group-fun reaction.", "mode": "Change the playback mode.",
    "movie": "Search for a movie.", "mute": "Mute a user in the group.", "myhistory": "Show your own playback history.",
    "mylevel": "Show your level.", "next": "Play the next track in the queue.", "notes": "List this group's saved notes.",
    "packkang": "Copy a whole sticker pack to yours.", "pin": "Pin the replied message.", "playback": "Show playback status and controls.",
    "playmode": "Choose who can use the player controls.", "promote": "Give a user admin rights.", "purge": "Delete messages up to the replied one.",
    "pypi": "Look up a Python package on PyPI.", "qr": "Turn text or a link into a QR code.", "rank": "Show your rank.",
    "reminder": "Set a reminder.", "remindme": "Set a reminder for yourself.",
    "removebadword": "Remove a word from the banned list.", "removephoto": "Remove your profile photo.", "rep": "Give reputation to a user.",
    "report": "Report a message to the group admins.", "reputation": "Show a user's reputation.", "rmbg": "Remove the background of an image.",
    "rockpaperscissors": "Play Rock, Paper, Scissors.", "rules": "Show the group rules.", "save": "Save a note in this group.",
    "sban": "Silently ban a user (removes the command).", "seek": "Jump forward in the current track.", "seekback": "Jump back in the current track.",
    "setdiscription": "Set your profile description.", "setfloodlimit": "Set how many messages count as flooding.",
    "setlang": "Set the bot language for this chat.", "setphoto": "Set your profile photo.",
    "setrules": "Set the group rules.", "settitle": "Set your profile title.",
    "setwarnlimit": "Set how many warnings lead to a ban.", "setwelcome": "Set the welcome message for new members.",
    "sg": "Look up a user's name history.", "shop": "Browse items you can buy with coins.", "short": "Shorten a URL.",
    "shuffle": "Shuffle the queue.", "slow": "Slow the playback speed down.", "speed": "Change the playback speed.",
    "speedtest": "Run a network speed test.", "spt": "Shortcut for /speedtest.", "spurge": "Purge messages silently.",
    "staff": "Show the group's staff.", "stats": "Show bot and system statistics.", "stdl": "Download a sticker as an image.",
    "stickerid": "Get the ID of a sticker.", "store": "Browse items you can buy with coins.", "tagall": "Mention all group members.",
    "tban": "Ban a user for a set time.", "telegraph": "Upload media or text to Telegraph.", "tempadmin": "Give someone temporary admin rights.",
    "tgm": "Upload media to Telegraph.", "tmute": "Mute a user for a set time.", "top": "Show the top members.",
    "truth": "Get a random truth question.", "tts": "Turn text into speech.", "unauth": "Remove a user's authorization.",
    "unban": "Unban a user.", "unlock": "Unlock a message type in the group.", "unmute": "Unmute a user.",
    "unpin": "Unpin the replied message.", "unshort": "Expand a shortened URL.", "unwarn": "Remove one warning from a user.",
    "upscale": "Enhance and upscale an image.", "user": "Show information about a user.", "userinfo": "Show detailed information about a user.",
    "vcinfo": "Show voice-chat information.", "vcmembers": "List who is in the voice chat.", "vip": "Show VIP plans and perks.",
    "voiceall": "Invite everyone to the voice chat.", "voices": "List the available text-to-speech voices.",
    "vstart": "Start a voice chat in this group.", "waifu": "Get a random waifu image.", "wallet": "Show your coin balance.",
    "warn": "Warn a user.", "warnings": "Show a user's warnings.", "weather": "Show the weather for a city.",
    "weekly": "Claim your weekly coin reward.", "wish": "Make a wish.", "write": "Turn text into a handwritten-style image.",
    "zombies": "Remove deleted accounts from the group.",
}
for _k, _v in _EXTRA_DESCRIPTIONS.items():
    DESCRIPTIONS.setdefault(_k, _v)

def _usage(command: str) -> str:
    return get_help(command)[1] or USAGE.get(command, f"/{command}")


def _description(command: str) -> str:
    return (
        get_help(command)[0]
        or DESCRIPTIONS.get(command)
        or OWNER_COMMANDS.get(command)
        or OWNER_EXTRA.get(command)
        or f"Use /{command} to open this feature. 蒼響 shows the required options when needed."
    )


def _trim(text: str, limit: int = 50) -> str:
    text = " ".join(str(text).split()).rstrip(".")
    if text[:1].islower():
        text = text[:1].upper() + text[1:]
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _short(command: str) -> str:
    """One-line summary for the category list."""
    desc = get_help(command)[0] or DESCRIPTIONS.get(command) or OWNER_COMMANDS.get(command) or OWNER_EXTRA.get(command)
    if desc:
        return _trim(desc)
    usage = USAGE.get(command, "")
    if "—" in usage:
        tail = usage.split("—", 1)[1].split(" — e.g")[0].strip()
        if tail and not tail.lower().startswith("e.g"):
            return _trim(tail)
    return ""


def _public_commands():
    hidden = set(OWNER_COMMANDS) | set(OWNER_EXTRA) | {"help", "start"}
    return [c for c in ALL_COMMANDS if c not in hidden]


def _build_categories():
    available = set(_public_commands())
    assigned, result = set(), {}
    for cat in CATEGORY_ORDER:
        if cat == "other":
            continue
        cmds = (CATEGORY_COMMANDS.get(cat, set()) & available) - assigned
        if cmds:
            result[cat] = sorted(cmds, key=_sort_key)
            assigned.update(cmds)
    other = available - assigned
    if other:
        result["other"] = sorted(other, key=_sort_key)
    return result


CATEGORIES = _build_categories()


def _owner_commands():
    return sorted({*OWNER_COMMANDS, *OWNER_EXTRA})


def _commands_of(category: str):
    return _owner_commands() if category == "owner" else CATEGORIES.get(category, [])


def _is_owner(user_id) -> bool:
    return bool(user_id) and int(user_id) == int(config.OWNER_ID)


def _paginate(category: str, page: int):
    commands = _commands_of(category)
    pages = max(1, (len(commands) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(int(page), pages))
    return commands[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], page, pages


# ─────────────────────────── screens ───────────────────────────
def _help_text() -> str:
    return _home_text().text


def _home_text() -> _Text:
    total = sum(len(v) for v in CATEGORIES.values())
    t = _Text()
    t.add("✦ ᴀǫᴜᴀᴠɪʙᴇ ᴄᴏᴍᴍᴀɴᴅ ᴄᴇɴᴛᴇʀ ✦", "b").nl(2)
    t.add(f"{total} commands · {len(CATEGORIES)} categories", "i").nl(2)
    q = t.mark()
    items = list(CATEGORIES)
    for i, key in enumerate(items):
        t.add(f"{CATEGORY_EMOJI[key]} ")
        t.add(CATEGORY_TITLES[key], "b")
        t.add(f" — {CATEGORY_BLURB[key]}")
        if i < len(items) - 1:
            t.nl()
    t.wrap("q", q).nl(2)
    t.add("Pick a category below to browse its commands.")
    return t


def _category_markup(user_id=None):
    rows, keys = [], list(CATEGORIES)
    for i in range(0, len(keys), 2):
        rows.append([
            InlineKeyboardButton(text=f"{CATEGORY_EMOJI[k]} {CATEGORY_TITLES[k]}", callback_data=f"helpcat:{k}")
            for k in keys[i:i + 2]
        ])
    footer = [InlineKeyboardButton(text="🏠 Menu", callback_data="back_to_main", aqua_style="success")]
    if _is_owner(user_id):
        footer.append(InlineKeyboardButton(text="👑 Owner", callback_data="open_owner", aqua_style="danger"))
    rows.append(footer)
    return InlineKeyboardMarkup(rows)


def _category_text(category: str, page: int, with_desc: bool = True) -> _Text:
    chunk, page, pages = _paginate(category, page)
    total = len(_commands_of(category))
    t = _Text()
    t.add(f"{CATEGORY_EMOJI[category]} {CATEGORY_TITLES[category].upper()}", "b").nl()
    t.add(f"{total} commands · page {page} of {pages}", "i").nl(2)
    q = t.mark()
    for i, cmd in enumerate(chunk):
        t.add(f"/{cmd}", "c")
        short = _short(cmd) if with_desc else ""
        if short:
            t.add(f" — {short}")
        if i < len(chunk) - 1:
            t.nl()
    t.wrap("q", q).nl(2)
    t.add("Tap a command below for details.")
    return t


def _category_page(category: str, page: int) -> _Text:
    t = _category_text(category, page, with_desc=True)
    if t.length > CAPTION_LIMIT:  # captions are capped; fall back to a bare list
        t = _category_text(category, page, with_desc=False)
    return t


def _command_markup(category: str, page: int = 1):
    chunk, page, pages = _paginate(category, page)
    per_row = 2 if any(len(c) > 9 for c in chunk) else 3
    rows = [
        [InlineKeyboardButton(text=f"/{c}", callback_data=f"cmdinfo:{category}:{c}:{page}") for c in chunk[i:i + per_row]]
        for i in range(0, len(chunk), per_row)
    ]
    if pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="‹ Prev", callback_data=f"helpcat:{category}:{page - 1}", aqua_style="primary"))
        nav.append(InlineKeyboardButton(text=f"{page} / {pages}", callback_data=f"catpage:{category}"))
        if page < pages:
            nav.append(InlineKeyboardButton(text="Next ›", callback_data=f"helpcat:{category}:{page + 1}", aqua_style="primary"))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="📚 Categories", callback_data="open_help", aqua_style="primary"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="back_to_main", aqua_style="success"),
    ])
    return InlineKeyboardMarkup(rows)


def _command_text(category: str, command: str) -> _Text:
    """Clean 'how to use' card: what it does, usage, example, who can use it, tip."""
    what, usage, example, who, tip = get_help(command)
    what = what or _description(command)
    usage = usage or _usage(command)
    if category == "owner" and not who:
        who = _OWNER_LABEL
    t = _Text()
    t.add(f"{CATEGORY_EMOJI.get(category, '📦')} ")
    t.add(f"/{command}", "b").nl(2)
    q = t.mark()
    t.add(what)
    t.wrap("q", q).nl(2)
    t.add("Usage", "b").nl()
    t.add(usage, "c")
    if example:
        t.nl(2).add("Example", "b").nl()
        t.add(example, "c")
    if who:
        t.nl(2).add(f"👤 {who}", "i")
    if tip:
        t.nl().add(f"💡 {tip}", "i")
    return t


def _command_detail_markup(category: str, page: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="‹ Back", callback_data=f"helpcat:{category}:{page}", aqua_style="primary")],
        [
            InlineKeyboardButton(text="📚 Categories", callback_data="open_help"),
            InlineKeyboardButton(text="🏠 Menu", callback_data="back_to_main", aqua_style="success"),
        ],
    ])


def _owner_text(page: int = 1) -> _Text:
    return _category_page("owner", page)


async def _show(update, t: _Text, markup):
    """Edit the current message (caption if it carries media, text otherwise)."""
    msg = update.message
    try:
        if msg.media:
            await msg.edit_caption(t.text, caption_entities=t.entities, reply_markup=markup)
        else:
            await msg.edit_text(t.text, entities=t.entities, reply_markup=markup, disable_web_page_preview=True)
    except MessageNotModified:
        pass


# ─────────────────────────── handlers ───────────────────────────
@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("^open_help$") & ~BANNED_USERS)
@LanguageStart
async def helper_private(client: Client, update: Union[Message, types.CallbackQuery], _):
    t = _home_text()
    markup = _category_markup(update.from_user.id if update.from_user else None)
    if isinstance(update, types.CallbackQuery):
        await update.answer()
        await _show(update, t, markup)
    else:
        try:
            await update.delete()
        except Exception:
            pass
        await update.reply_photo(photo=HELP_IMG_URL, caption=t.text, caption_entities=t.entities, reply_markup=markup)


@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client: Client, message: Message, _):
    t = _Text()
    t.add("✦ ", "b").add("ᴀǫᴜᴀᴠɪʙᴇ ʜᴇʟᴘ", "b").add(" ✦", "b").nl(2)
    t.add("🎶 Music · 🤖 AI · 🧩 Tools · 🛡 Group control · 🎲 Games", "i").nl(2)
    t.add("Open the full command center in private chat.")
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(text="📚 Open Command Center", url=f"https://t.me/{app.username}?start=help", aqua_style="success")
    ]])
    await message.reply_text(t.text, entities=t.entities, reply_markup=markup, disable_web_page_preview=True)


@app.on_callback_query(filters.regex(r"^helpcat:[a-z_]+(?::\d+)?$") & ~BANNED_USERS)
@languageCB
async def help_category_cb(client: Client, callback: types.CallbackQuery, _):
    parts = callback.data.split(":")
    category = parts[1]
    if category == "owner":
        if not _is_owner(callback.from_user.id):
            return await callback.answer("Owner only.", show_alert=True)
    elif category not in CATEGORIES:
        return await callback.answer("Unknown category.", show_alert=True)
    page = int(parts[2]) if len(parts) > 2 else 1
    await callback.answer()
    await _show(callback, _category_page(category, page), _command_markup(category, page))


@app.on_callback_query(filters.regex(r"^catpage:") & ~BANNED_USERS)
@languageCB
async def category_page_info_cb(client: Client, callback: types.CallbackQuery, _):
    category = callback.data.split(":", 1)[1]
    if category != "owner" and category not in CATEGORIES:
        return await callback.answer("Unknown category.", show_alert=True)
    commands = _commands_of(category)
    pages = max(1, (len(commands) + PAGE_SIZE - 1) // PAGE_SIZE)
    await callback.answer(f"{len(commands)} commands • {pages} page{'s' if pages != 1 else ''}", show_alert=True)


@app.on_callback_query(filters.regex(r"^cmdinfo:") & ~BANNED_USERS)
@languageCB
async def command_info_cb(client: Client, callback: types.CallbackQuery, _):
    parts = callback.data.split(":")
    if len(parts) != 4:
        return await callback.answer("Invalid command.", show_alert=True)
    _x, category, command, page = parts
    if category == "owner" and not _is_owner(callback.from_user.id):
        return await callback.answer("Owner only.", show_alert=True)
    if command not in _commands_of(category):
        return await callback.answer("Unknown command.", show_alert=True)
    await callback.answer()
    await _show(callback, _command_text(category, command), _command_detail_markup(category, int(page) if page.isdigit() else 1))


@app.on_callback_query(filters.regex(r"^noop_cmd:") & ~BANNED_USERS)
@languageCB
async def legacy_command_cb(client: Client, callback: types.CallbackQuery, _):
    """Buttons on older 'All Commands' messages: show the same usage card."""
    command = callback.data.split(":", 1)[1].strip()
    if command not in ALL_COMMANDS or command in OWNER_COMMANDS or command in OWNER_EXTRA:
        return await callback.answer("Unknown command.", show_alert=True)
    category = next((c for c, cmds in CATEGORIES.items() if command in cmds), "other")
    await callback.answer()
    await _show(callback, _command_text(category, command), _command_detail_markup(category, 1))


@app.on_callback_query(filters.regex(r"^open_owner$") & ~BANNED_USERS)
async def owner_panel_cb(client: Client, callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Owner only.", show_alert=True)
    await callback.answer()
    await _show(callback, _category_page("owner", 1), _command_markup("owner", 1))


@app.on_callback_query(filters.regex(r"^ownerinfo:") & ~BANNED_USERS)
async def owner_info_cb(client: Client, callback: types.CallbackQuery):
    """Kept for buttons on older messages."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Owner only.", show_alert=True)
    command = callback.data.split(":", 1)[1].strip()
    if command not in _commands_of("owner"):
        return await callback.answer("Unknown owner command.", show_alert=True)
    await callback.answer()
    await _show(callback, _command_text("owner", command), _command_detail_markup("owner", 1))


@app.on_callback_query(filters.regex(r"^open_system$") & ~BANNED_USERS)
async def system_status_cb(client: Client, callback: types.CallbackQuery):
    UP, CPU, RAM, DISK = await bot_sys_stats()
    await callback.answer(
        f"⚡ System Online\n\n"
        f"Uptime: {UP}\n"
        f"CPU: {CPU}\n"
        f"RAM: {RAM}\n"
        f"Disk: {DISK}",
        show_alert=True,
    )


@app.on_callback_query(filters.regex("^back_to_main$") & ~BANNED_USERS)
@languageCB
async def back_to_main_cb(client: Client, callback: types.CallbackQuery, _):
    await callback.answer()
    msg = callback.message
    bot_display_name = (getattr(app.me, "first_name", None) if app.me else None) or config.BOT_NAME
    caption, caption_entities = welcome_caption(callback.from_user.first_name, callback.from_user.id, bot_display_name)
    markup = InlineKeyboardMarkup(private_panel(_, callback.from_user.id))
    try:
        if msg.media:
            await msg.edit_caption(caption, caption_entities=caption_entities, reply_markup=markup)
        else:
            await msg.edit_text(caption, entities=caption_entities, reply_markup=markup)
    except MessageNotModified:
        pass
