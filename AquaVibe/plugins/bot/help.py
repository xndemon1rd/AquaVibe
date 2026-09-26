"""蒼響's categorized command/help interface with Telegram custom emoji."""
from typing import Union

from pyrogram import Client, filters, types
from pyrogram.enums import MessageEntityType
from pyrogram.enums import MessageEntityType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.database import get_lang
from AquaVibe.utils.decorators.language import LanguageStart, languageCB
from AquaVibe.utils.inline.start import private_panel
from AquaVibe.utils.owner_commands import OWNER_COMMANDS
from AquaVibe.utils.premium_emoji import custom_emoji_entities, _utf16_len
from config import BANNED_USERS, HELP_IMG_URL
from strings import get_string
from AquaVibe.utils.command_catalog import ALL_COMMANDS
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton

# The five Premium Custom Emoji IDs are inherited from the original
# TrebelxMusic premium-emoji system.  The visible characters below are the
# fallbacks Telegram uses when custom entities cannot be rendered.
CATEGORY_EMOJI = {
    "music": "✨",
    "ai": "❤️‍🔥",
    "tools": "🪄",
    "profile": "✨",
    "group": "🚧",
    "fun": "❤️‍🔥",
    "other": "📦",
    "owner": "🚧",
}

CATEGORY_TITLES = {
    "music": "Music",
    "ai": "AI",
    "tools": "Tools & Utilities",
    "profile": "Profile",
    "group": "Group Management",
    "fun": "Fun & Social",
    "other": "Other Commands",
    "owner": "Owner Commands",
}

# Explicit categorisation for the command catalogue. Commands not listed here
# are placed in Other Commands, so no registered command disappears from Help.
CATEGORY_COMMANDS = {
    "music": {
        "play", "vplay", "pause", "resume", "skip", "stop", "end",
        "queue", "player", "playing", "next", "shuffle", "seek", "seekback",
        "speed", "slow", "loop", "cloop", "cnext", "cpause", "cresume", "cskip",
        "playback", "activevc", "autoend", "mode", "playmode",
        "history", "myhistory", "lyrics",
    },
    "ai": {"ai", "cimage", "imposter"},
    "tools": {
        "ping", "stats", "speedtest", "bug", "lang", "setlang", "font", "fonts",
        "encode", "decode", "short", "unshort", "qr", "rmbg", "tts", "stickerid", "string",
        "pypi", "domain", "getdraw", "check", "refresh", "reload",
        "logs", "logger", "mongochk", "ip",
        "admincache", "botschk", "bots", "blocked", "blockedusers", "blusers",
    },
    "profile": {
        "profile", "setprofilephoto", "setprofilebanner", "setphoto", "setbanner",
        "removephoto", "banner", "setdiscription", "settitle", "id", "info",
    },
    "group": {
        "settings", "groupdata", "gstats", "staff", "admins",
        "promote", "fullpromote", "demote", "mute", "unmute", "ban",
        "unban", "kick", "kickme", "purge", "deleteall", "del", "pin",
        "muteall", "banall", "sban", "blchat", "blchats", "blacklistedchats",
        "hide", "auth", "authlist", "authusers", "assistantjoin",
        "warn", "warnings", "unwarn", "clearwarnings", "setwarnlimit",
        "rules", "setrules", "setwelcome", "report",
        "antilink", "addbadword", "removebadword", "badwords", "setfloodlimit", "flood",
        "lock", "unlock", "captcha", "approve", "unapprove", "raidmode", "raidstatus", "protect", "setgoodbye", "goodbye", "cleanup", "purgefrom", "unpinall",
    },
    "fun": {
        "rps", "quiz", "trivia", "wordle", "word",
        "baka", "bite", "blush", "bored", "couple", "cuddle", "cute", "cutie", "dance",
        "dare", "dart", "facepalm", "feed", "happy", "highfive", "hug", "kiss", "kang",
        "lesbian", "love", "lurk", "meme", "mmf", "nod", "nom", "nope", "packkang",
        "pat", "peck", "poke", "punch", "shoot", "slap", "sleep",
        "smile", "sexy", "horny", "hot", "boob", "cock", "gay", "football",
    },
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
    "approve": "Approve a pending join request by user ID, username or reply.",
    "unapprove": "Decline a pending join request by user ID, username or reply.",
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
    "approve": "/approve <user_id|@username>  — or reply to a user",
    "unapprove": "/unapprove <user_id|@username>  — or reply to a user",
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

def _usage(command: str) -> str:
    return USAGE.get(command, f"/{command}")

def _description(command: str) -> str:
    return DESCRIPTIONS.get(
        command,
        f"Use /{command} to open this feature. 蒼響 will show the required options or usage when needed.",
    )


def _build_categories():
    assigned = set()
    result = {}
    for category, commands in CATEGORY_COMMANDS.items():
        actual = sorted(set(commands) & set(ALL_COMMANDS))
        if actual:
            result[category] = actual
            assigned.update(actual)
    other = sorted(set(ALL_COMMANDS) - assigned - {"help", "start"})
    if other:
        result["other"] = other
    return result

CATEGORIES = _build_categories()


def _category_markup():
    rows = []
    entries = list(CATEGORIES.items())
    for i in range(0, len(entries), 2):
        row = []
        for key, _commands in entries[i:i + 2]:
            row.append(InlineKeyboardButton(
                text=f"{CATEGORY_EMOJI[key]} {CATEGORY_TITLES[key]}",
                callback_data=f"helpcat:{key}",
            ))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="👑 Owner", callback_data="open_owner"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="back_to_main"),
    ])
    return InlineKeyboardMarkup(rows)


def _command_markup(category: str, page: int = 1):
    commands = CATEGORIES.get(category, [])
    page_size = 12
    pages = max(1, (len(commands) + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    chunk = commands[(page - 1) * page_size: page * page_size]
    rows = []
    for i in range(0, len(chunk), 2):
        rows.append([
            InlineKeyboardButton(text=f"/{cmd}", callback_data=f"cmdinfo:{category}:{cmd}:{page}")
            for cmd in chunk[i:i + 2]
        ])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀ Back", callback_data=f"helpcat:{category}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data=f"catpage:{category}"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"helpcat:{category}:{page + 1}"))
    rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="📚 Categories", callback_data="open_help"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="back_to_main"),
    ])
    return InlineKeyboardMarkup(rows)


def _help_text():
    return (
        "✨ 蒼響 HELP ✨\n\n"
        "📦 Choose a category below to explore commands.\n"
        "❤️‍🔥 Tap any command to see what it does and how to use it.\n\n"
        "🚧 Owner commands are protected and shown only to the configured owner."
    )


def _category_text(category: str, page: int):
    emoji = CATEGORY_EMOJI[category]
    title = CATEGORY_TITLES[category]
    commands = CATEGORIES[category]
    page_size = 12
    pages = max(1, (len(commands) + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    chunk = commands[(page - 1) * page_size: page * page_size]
    lines = [f"{emoji} {title.upper()}", ""]
    # Keep category pages compact because the Help message starts as a media
    # message. Telegram media captions are limited to 1024 characters.
    # Command descriptions are shown on the individual command page instead.
    for cmd in chunk:
        lines.append(f"✨ /{cmd}")
    lines.append("")
    lines.append(f"📦 Page {page}/{pages} • Tap a command for details.")
    return "\n".join(lines)


def _owner_markup():
    commands = list(OWNER_COMMANDS)
    rows = []
    for i in range(0, len(commands), 2):
        rows.append([
            InlineKeyboardButton(text=f"🚧 /{cmd}", callback_data=f"ownerinfo:{cmd}")
            for cmd in commands[i:i + 2]
        ])
    rows.append([InlineKeyboardButton(text="📚 Categories", callback_data="open_help")])
    return InlineKeyboardMarkup(rows)


def _owner_text():
    return (
        "🚧 OWNER PANEL 🚧\n\n"
        "❤️‍🔥 These commands are protected and available only to the configured owner.\n"
        "✨ Tap a command for its purpose and usage."
    )


async def _edit(update, text, markup):
    entities = custom_emoji_entities(text, blockquote=False)
    if update.message and update.message.photo:
        await update.message.edit_caption(text, caption_entities=entities, reply_markup=markup)
    else:
        await update.message.edit_text(text, entities=entities, reply_markup=markup)


@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("^open_help$") & ~BANNED_USERS)
@LanguageStart
async def helper_private(client: Client, update: Union[Message, types.CallbackQuery], _):
    keyboard = _category_markup()
    text = _help_text()
    if isinstance(update, types.CallbackQuery):
        await update.answer()
        await _edit(update, text, keyboard)
    else:
        await update.delete()
        await update.reply_photo(
            photo=HELP_IMG_URL,
            caption=text,
            caption_entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=keyboard,
        )


@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client: Client, message: Message, _):
    text = "✨ Open 蒼響 Help\n\n🎵 Explore music, AI, tools, profiles, groups and more."
    await message.reply_text(
        text,
        entities=custom_emoji_entities(text, blockquote=False),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="✨ Help", callback_data="open_help")]]),
    )


@app.on_callback_query(filters.regex(r"^helpcat:[a-z_]+(?::\d+)?$") & ~BANNED_USERS)
@languageCB
async def help_category_cb(client: Client, callback: types.CallbackQuery, _):
    parts = callback.data.split(":")
    category = parts[1]
    if category not in CATEGORIES:
        return await callback.answer("Unknown category.", show_alert=True)
    page = int(parts[2]) if len(parts) > 2 else 1
    await callback.answer()
    text = _category_text(category, page)
    if callback.message and callback.message.photo:
        await callback.message.edit_caption(
            text,
            caption_entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=_command_markup(category, page),
        )
    else:
        await callback.message.edit_text(
            text,
            entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=_command_markup(category, page),
        )


@app.on_callback_query(filters.regex(r"^catpage:") & ~BANNED_USERS)
@languageCB
async def category_page_info_cb(client: Client, callback: types.CallbackQuery, _):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORIES:
        return await callback.answer("Unknown category.", show_alert=True)
    commands = CATEGORIES[category]
    pages = max(1, (len(commands) + 11) // 12)
    await callback.answer(f"{len(commands)} commands • {pages} pages", show_alert=True)


@app.on_callback_query(filters.regex(r"^cmdinfo:") & ~BANNED_USERS)
@languageCB
async def command_info_cb(client: Client, callback: types.CallbackQuery, _):
    parts = callback.data.split(":")
    if len(parts) != 4:
        return await callback.answer("Invalid command.", show_alert=True)
    _, category, command, page = parts
    if category not in CATEGORIES or command not in CATEGORIES[category]:
        return await callback.answer("Unknown command.", show_alert=True)
    await callback.answer()
    usage = _usage(command)
    text = (
        f"{CATEGORY_EMOJI[category]} /{command}\n\n"
        f"✨ What it does:\n{_description(command)}\n\n"
        f"📦 How to use:\n{usage}\n\n"
        "❤️‍🔥 Tip: commands that say ‘reply’ must be used as a reply to the target message. "
        "Admin/owner-only commands require the appropriate permissions."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="◀ Back to category", callback_data=f"helpcat:{category}:{page}")],
        [InlineKeyboardButton(text="📚 Categories", callback_data="open_help")],
    ])
    if callback.message and callback.message.photo:
        await callback.message.edit_caption(
            text,
            caption_entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=markup,
        )
    else:
        await callback.message.edit_text(
            text,
            entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=markup,
        )


@app.on_callback_query(filters.regex(r"^open_owner$") & ~BANNED_USERS)
async def owner_panel_cb(client: Client, callback: types.CallbackQuery):
    if callback.from_user.id != config.OWNER_ID:
        return await callback.answer("Owner only.", show_alert=True)
    await callback.answer()
    text = _owner_text()
    if callback.message and callback.message.photo:
        await callback.message.edit_caption(
            text,
            caption_entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=_owner_markup(),
        )
    else:
        await callback.message.edit_text(
            text,
            entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=_owner_markup(),
        )


@app.on_callback_query(filters.regex(r"^ownerinfo:") & ~BANNED_USERS)
async def owner_info_cb(client: Client, callback: types.CallbackQuery):
    if callback.from_user.id != config.OWNER_ID:
        return await callback.answer("Owner only.", show_alert=True)
    command = callback.data.split(":", 1)[1].strip()
    description = OWNER_COMMANDS.get(command)
    if not description:
        return await callback.answer("Unknown owner command.", show_alert=True)
    await callback.answer()
    text = (
        f"🚧 /{command}\n\n"
        f"✨ What it does:\n{description}\n\n"
        f"📦 How to use:\n{_usage(command)}"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="◀ Back to Owner", callback_data="open_owner")],
        [InlineKeyboardButton(text="📚 Categories", callback_data="open_help")],
    ])
    if callback.message and callback.message.photo:
        await callback.message.edit_caption(
            text,
            caption_entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=markup,
        )
    else:
        await callback.message.edit_text(
            text,
            entities=custom_emoji_entities(text, blockquote=False),
            reply_markup=markup,
        )


@app.on_callback_query(filters.regex("^back_to_main$") & ~BANNED_USERS)
@languageCB
async def back_to_main_cb(client: Client, callback: types.CallbackQuery, _):
    await callback.answer()
    user_name = callback.from_user.first_name or "User"
    caption = (
        "╭───────────────────▣\n"
        f"│❍ ʜᴇʏ • {user_name}\n"
        "│❍ ɪ ᴀᴍ 蒼響\n"
        "├───────────────────▣\n"
        "│❍ ʙᴇsᴛ ǫᴜɪʟɪᴛʏ ғᴇᴀᴛᴜʀᴇs •\n"
        "│❍ sᴛᴀʀᴛ ʏᴏᴜʀ ᴊᴏᴜʀɴᴇʏ ✨\n"
        "╰───────────────────▣"
    )
    entities = custom_emoji_entities(caption, blockquote=False)
    name_start = caption.index(user_name)
    entities.append(
        MessageEntity(
            type=MessageEntityType.TEXT_LINK,
            offset=_utf16_len(caption[:name_start]),
            length=_utf16_len(user_name),
            url=f"tg://user?id={callback.from_user.id}",
        )
    )
    # private_panel() returns the button rows because the normal /start
    # handlers wrap them themselves. Callback edit methods require the
    # actual InlineKeyboardMarkup object.
    markup = InlineKeyboardMarkup(private_panel(_, callback.from_user.id))
    if callback.message and callback.message.photo:
        await callback.message.edit_caption(
            caption,
            caption_entities=entities,
            reply_markup=markup,
        )
    else:
        await callback.message.edit_text(
            caption,
            entities=entities,
            reply_markup=markup,
        )
