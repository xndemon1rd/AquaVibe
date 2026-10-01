# Authored By Dev © 2025
import os
import re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

# Load environment variables from .env file
load_dotenv()

# ── Core bot config ────────────────────────────────────────────────────────────
def _required_env(name: str) -> str:
    value = getenv(name)
    if not value:
        raise RuntimeError(f"Missing required Railway/Termux variable: {name}")
    return value


API_ID = int(_required_env("API_ID"))
API_HASH = _required_env("API_HASH")
BOT_TOKEN = _required_env("BOT_TOKEN")

OWNER_ID = int(_required_env("OWNER_ID"))
OWNER_USERNAME = getenv("OWNER_USERNAME", "蒼響")
BOT_USERNAME = getenv("BOT_USERNAME", "aquavibebot").lstrip("@").strip()
BOT_NAME = getenv("BOT_NAME", "蒼響 ♪")
ASSUSERNAME = getenv("ASSUSERNAME", "aquavibebot").lstrip("@").strip()

# ── Database & logging ─────────────────────────────────────────────────────────
MONGO_DB_URI = _required_env("MONGO_DB_URI")
LOGGER_ID = int(getenv("LOGGER_ID", "0") or "0")
# Optional public username or invite link used by assistants to auto-join the log chat.
# Examples: @my_log_group or https://t.me/+InviteHash
LOGGER_CHAT = getenv("LOGGER_CHAT", "").strip()
LOGGER_INVITE_LINK = getenv("LOGGER_INVITE_LINK", "").strip()

# ── Limits (durations in min/sec; sizes in bytes) ──────────────────────────────
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 300))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION", "1200"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "1800"))
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "157286400"))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "1288490189"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "30"))
MAX_DOWNLOAD_BYTES = int(getenv("MAX_DOWNLOAD_BYTES", "1288490189"))
MAX_AUDIO_DOWNLOAD_BYTES = int(getenv("MAX_AUDIO_DOWNLOAD_BYTES", str(TG_AUDIO_FILESIZE_LIMIT)))
DIRECT_DOWNLOAD_TIMEOUT = int(getenv("DIRECT_DOWNLOAD_TIMEOUT", "600"))
API_POLL_TIMEOUT = int(getenv("API_POLL_TIMEOUT", "180"))
DOWNLOAD_RETENTION_HOURS = int(getenv("DOWNLOAD_RETENTION_HOURS", "24"))
CACHE_RETENTION_HOURS = int(getenv("CACHE_RETENTION_HOURS", "48"))
MAX_CACHE_BYTES = int(getenv("MAX_CACHE_BYTES", "536870912"))
STORAGE_CLEANUP_INTERVAL = int(getenv("STORAGE_CLEANUP_INTERVAL", "1800"))
STARTUP_VOICE_CHECK = getenv("STARTUP_VOICE_CHECK", "false").lower() in {"1", "true", "yes", "on"}

# ── AI ─────────────────────────────────────────────────────────────────────────
# Text-chat fallback order (see AquaVibe/utils/ai.py):
#   Gemini -> Groq -> Mistral -> OpenRouter(free) -> Ollama -> LLM7 (no key) -> OVHcloud (no key)
# Providers without a key are skipped. LLM7 and OVHcloud need NO key, so the bot
# can always answer. Reorder with AI_PROVIDER_ORDER=groq,gemini,llm7,ovh ...
GEMINI_API_KEY = getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = getenv("GROQ_API_KEY", "")
MISTRAL_API_KEY = getenv("MISTRAL_API_KEY", "")
OPENROUTER_API_KEY = getenv("OPENROUTER_API_KEY", "")
ANTHROPIC_API_KEY = getenv("ANTHROPIC_API_KEY", "")  # optional; self-healing repairs only, never used for chat

# Several models can be given comma-separated; they are tried in order.
# gemini-3.5-flash is a stable model; GEMINI_MODEL is tried first, then the built-in fallbacks.
GEMINI_MODEL = getenv("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_MODEL = getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MISTRAL_MODEL = getenv("MISTRAL_MODEL", "mistral-large-latest")
OPENROUTER_MODEL = getenv("OPENROUTER_MODEL", "openrouter/free")
ANTHROPIC_MODEL = getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

# Free providers that need no API key.
LLM7_ENABLED = getenv("LLM7_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
LLM7_API_KEY = getenv("LLM7_API_KEY", "")  # optional free token from token.llm7.io (higher limits)
LLM7_MODEL = getenv("LLM7_MODEL", "gpt-oss:20b,mistral-Nemo-Instruct-2407")
OVH_AI_ENABLED = getenv("OVH_AI_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
OVH_AI_API_KEY = getenv("OVH_AI_API_KEY", "")  # optional; anonymous works (2 requests/min per model)
OVH_AI_MODEL = getenv("OVH_AI_MODEL", "gpt-oss-120b,Meta-Llama-3_3-70B-Instruct,gpt-oss-20b")
AI_PROVIDER_ORDER = getenv("AI_PROVIDER_ORDER", "")

LAST_IMAGE_ERROR = ""
LAST_VIDEO_ERROR = ""
LAST_AI_ERROR = ""
AI_MAX_INPUT = int(getenv("AI_MAX_INPUT", "8000"))
OLLAMA_ENABLED = getenv("OLLAMA_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
OLLAMA_BASE_URL = getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
OLLAMA_MODEL = getenv("OLLAMA_MODEL", "llama3.2").strip()
OLLAMA_TIMEOUT = float(getenv("OLLAMA_TIMEOUT", "90"))

# Free keyless providers are always available, so AI only needs this switch.
AI_ENABLED = getenv("AI_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

# ── Aqua Coding / VIP ─────────────────────────────────────────────────────────
VIP_PRICE_INR = int(getenv("VIP_PRICE_INR", "500"))
VIP_PRO_PRICE_INR = int(getenv("VIP_PRO_PRICE_INR", "700"))
VIP_DAYS = int(getenv("VIP_DAYS", "30"))
VIP_PRO_DAYS = int(getenv("VIP_PRO_DAYS", "30"))
VIP_UPI_ID = getenv("VIP_UPI_ID", "lucifer.dabre@fam")
VIP_CRYPTO_ADDRESS = getenv("VIP_CRYPTO_ADDRESS", "")
VIP_PAYMENT_NOTE = getenv("VIP_PAYMENT_NOTE", "Send payment proof/UTR to owner for manual approval.")
CODING_WORKSPACE_DIR = getenv("CODING_WORKSPACE_DIR", "coding_workspaces")
CODING_MAX_ZIP_MB = int(getenv("CODING_MAX_ZIP_MB", "45"))
CODING_PRO_MAX_ZIP_MB = int(getenv("CODING_PRO_MAX_ZIP_MB", "100"))
CODING_PRO_MAX_FILES = int(getenv("CODING_PRO_MAX_FILES", "1000"))
CODING_PRO_MAX_FILE_MB = int(getenv("CODING_PRO_MAX_FILE_MB", "5"))
CODING_PRO_JOB_TIMEOUT = int(getenv("CODING_PRO_JOB_TIMEOUT", "1800"))
CODING_MAX_FILES = int(getenv("CODING_MAX_FILES", "500"))
CODING_MAX_FILE_MB = int(getenv("CODING_MAX_FILE_MB", "2"))
CODING_JOB_TIMEOUT = int(getenv("CODING_JOB_TIMEOUT", "900"))
CODING_MAX_CONCURRENT = int(getenv("CODING_MAX_CONCURRENT", "1"))
CODING_AI_MAX_INPUT = int(getenv("CODING_AI_MAX_INPUT", "28000"))
PUTER_BRIDGE_URL = getenv("PUTER_BRIDGE_URL", "")
PUTER_CODING_ENDPOINT = getenv("PUTER_CODING_ENDPOINT", "")
CODING_AGENT_ENABLED = getenv("CODING_AGENT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
SELF_HEALING_ENABLED = getenv("SELF_HEALING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
SELF_HEALING_AUTO_APPLY = False  # Owner approval is always required.
SELF_HEALING_MAX_TOKENS = int(getenv("SELF_HEALING_MAX_TOKENS", "8000"))      # room for the edit list
SELF_HEALING_MAX_INPUT = int(getenv("SELF_HEALING_MAX_INPUT", "60000"))       # chars of file + error sent to the AI
SELF_HEALING_COOLDOWN = int(getenv("SELF_HEALING_COOLDOWN", "3600"))          # s before the same error is analysed again
SELF_HEALING_MAX_CHANGED_LINES = int(getenv("SELF_HEALING_MAX_CHANGED_LINES", "80"))

# ── Aqua Social / AI ───────────────────────────────────────────────────────────
SOCIAL_AI_ENABLED = getenv("SOCIAL_AI_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
AI_GROUP_AUTO_REPLY = getenv("AI_GROUP_AUTO_REPLY", "true").lower() in {"1", "true", "yes", "on"}
AI_MEMORY_TURNS = int(getenv("AI_MEMORY_TURNS", "12"))
AI_STICKER_REPLY = getenv("AI_STICKER_REPLY", "true").lower() in {"1", "true", "yes", "on"}   # sticker -> sticker
AI_REACT_CHANCE = float(getenv("AI_REACT_CHANCE", "0.2"))               # random reaction on normal group messages
AI_REACT_CHANCE_DIRECT = float(getenv("AI_REACT_CHANCE_DIRECT", "0.4"))  # ...on messages addressed to the bot
AI_REACT_COOLDOWN = int(getenv("AI_REACT_COOLDOWN", "10"))               # min seconds between reactions per group
AI_PRIVATE_CHAT = getenv("AI_PRIVATE_CHAT", "true").lower() in {"1", "true", "yes", "on"}    # AI answers plain DMs
AI_CHATTY_CHANCE = float(getenv("AI_CHATTY_CHANCE", "0.15"))             # /chatty groups: chance to jump into a chat
AI_CHATTY_COOLDOWN = int(getenv("AI_CHATTY_COOLDOWN", "45"))             # min seconds between unprompted replies per group
AI_STICKER_CHANCE_CHATTY = float(getenv("AI_STICKER_CHANCE_CHATTY", "0.25"))  # /chatty groups: answer a random sticker
AI_EMOTE_STICKER = getenv("AI_EMOTE_STICKER", "true").lower() in {"1", "true", "yes", "on"}  # add a feeling-matched sticker to some text replies
AI_EMOTE_STICKER_CHANCE = float(getenv("AI_EMOTE_STICKER_CHANCE", "0.6"))     # chance when the AI itself asks for a sticker
AI_STICKER_WINDOW = int(getenv("AI_STICKER_WINDOW", "120"))                   # seconds after talking to the bot in which a user's sticker gets a sticker back
AI_STICKER_PACKS = getenv("AI_STICKER_PACKS", "").strip()                      # comma-separated sticker pack short names used for emotion replies
AQUA_MINIAPP_URL = getenv("AQUA_MINIAPP_URL", "").strip().rstrip("/")
AQUA_WEBAPP_ENABLED = getenv("AQUA_WEBAPP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
AQUA_WEBAPP_HOST = getenv("AQUA_WEBAPP_HOST", "0.0.0.0")
AQUA_WEBAPP_PORT = int(getenv("PORT", getenv("AQUA_WEBAPP_PORT", "8080")))
ECONOMY_START_BALANCE = int(getenv("ECONOMY_START_BALANCE", "1000"))
ECONOMY_DAILY_MIN = int(getenv("ECONOMY_DAILY_MIN", "100"))
ECONOMY_DAILY_MAX = int(getenv("ECONOMY_DAILY_MAX", "500"))
CURRENCY_SYMBOL = getenv("CURRENCY_SYMBOL", "¥").strip() or "¥"  # single source for every money display

# Whisper (inline private messages). Optional: secret used to encrypt stored whispers.
# Leave empty to derive the key from BOT_TOKEN. Changing it makes older whispers unreadable.
WHISPER_SECRET = getenv("WHISPER_SECRET", "").strip()

# Action-game limits (/rob /kill /shield /revive). Cooldowns are seconds; daily caps reset at 00:00 UTC.
ROB_COOLDOWN = int(getenv("ROB_COOLDOWN", "600"))
ROB_DAILY_LIMIT = int(getenv("ROB_DAILY_LIMIT", "5"))
ROB_VICTIM_IMMUNITY = int(getenv("ROB_VICTIM_IMMUNITY", "300"))  # victim can't be robbed again for this long
ROB_MIN_VICTIM_BALANCE = int(getenv("ROB_MIN_VICTIM_BALANCE", "100"))
KILL_COOLDOWN = int(getenv("KILL_COOLDOWN", "900"))
KILL_DAILY_LIMIT = int(getenv("KILL_DAILY_LIMIT", "5"))
KNOCKOUT_DURATION = int(getenv("KNOCKOUT_DURATION", "1800"))
SHIELD_COST = int(getenv("SHIELD_COST", "150"))
SHIELD_DURATION = int(getenv("SHIELD_DURATION", "900"))
SHIELD_COOLDOWN = int(getenv("SHIELD_COOLDOWN", "1800"))
SHIELD_DAILY_LIMIT = int(getenv("SHIELD_DAILY_LIMIT", "3"))
REVIVE_COST = int(getenv("REVIVE_COST", "200"))

# In-chat games (no Mini App needed)
UNO_WIN_REWARD = int(getenv("UNO_WIN_REWARD", "5000"))
UNO_TURN_TIMEOUT = int(getenv("UNO_TURN_TIMEOUT", "90"))  # seconds before an idle player is auto-skipped
UNO_MAX_PLAYERS = int(getenv("UNO_MAX_PLAYERS", "8"))

# ── External APIs ──────────────────────────────────────────────────────────────
AI_HEALER_ENABLED = "disabled"  # Railway-lite build: no self-healing runtime
API_URL = getenv("API_URL")        # optional
VIDEO_API_URL = getenv("VIDEO_API_URL")  # optional
API_KEY = getenv("API_KEY")        # optional
TMDB_API_KEY = getenv("TMDB_API_KEY", "").strip()
IPINFO_TOKEN = getenv("IPINFO_TOKEN", "").strip()
IPQUALITYSCORE_API_KEY = getenv("IPQUALITYSCORE_API_KEY", "").strip()
REMOVE_BG_API_KEY = getenv("REMOVE_BG_API_KEY", "").strip()
WEATHER_API_KEY = getenv("WEATHER_API_KEY", "").strip()
CHATLOG_ENABLED = getenv("CHATLOG_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
AUTO_BACKUP_ENABLED = getenv("AUTO_BACKUP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
DATA_EXPORT_ENABLED = getenv("DATA_EXPORT_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
# Advanced error system: enabled by default when LOGGER_ID is configured.
ERROR_SYSTEM_ENABLED = getenv("ERROR_SYSTEM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
REMOTE_ERROR_REPORTING = getenv("REMOTE_ERROR_REPORTING", "true").lower() in {"1", "true", "yes", "on"}
ERROR_DEDUP_WINDOW_SEC = int(getenv("ERROR_DEDUP_WINDOW_SEC", "300"))
ERROR_MAX_PER_WINDOW = int(getenv("ERROR_MAX_PER_WINDOW", "30"))
ERROR_LOG_FILE = getenv("ERROR_LOG_FILE", "runtime_errors.jsonl")
ERROR_INCLUDE_TRACEBACK = getenv("ERROR_INCLUDE_TRACEBACK", "true").lower() in {"1", "true", "yes", "on"}
ERROR_REDACT_SECRETS = getenv("ERROR_REDACT_SECRETS", "true").lower() in {"1", "true", "yes", "on"}
REMOTE_PLAY_LOGGING = getenv("REMOTE_PLAY_LOGGING", "false").lower() in {"1", "true", "yes", "on"}
EXTERNAL_UPLOADS_ENABLED = getenv("EXTERNAL_UPLOADS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
ASSISTANTS_ENABLED = getenv("ASSISTANTS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

# ── Hosting / deployment ───────────────────────────────────────────────────────
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

# ── Git / updates ──────────────────────────────────────────────────────────────

# ── Support links ──────────────────────────────────────────────────────────────
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/AstrixVeyra")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/zpaveldurov")

# ── Assistant auto-leave ───────────────────────────────────────────────────────
AUTO_LEAVING_ASSISTANT = False
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("ASSISTANT_LEAVE_TIME", "3600"))

# ── Debug ──────────────────────────────────────────────────────────────────────
DEBUG_IGNORE_LOG = True

# ── Spotify (optional) ─────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET")

# ── Session strings (optional) ─────────────────────────────────────────────────
COOKIE_URL = getenv("COOKIE_URL", "").strip()

STRING1 = getenv("STRING_SESSION") or getenv("STRING_SESSION1")
STRING2 = getenv("STRING_SESSION2")
STRING3 = getenv("STRING_SESSION3")
STRING4 = getenv("STRING_SESSION4")
STRING5 = getenv("STRING_SESSION5")

# ── Media assets ───────────────────────────────────────────────────────────────
START_VIDS = [
    "https://files.catbox.moe/6d0ejr.mp4",
    "https://files.catbox.moe/d941ku.mp4",
    "https://www.image2url.com/r2/default/videos/1789542560216-1e47a2d4-449c-494b-97b4-b9fefb4d4972.mp4",
]
STICKERS = [
    "CAACAgUAAx0Cd6nKUAACASBl_rnalOle6g7qS-ry-aZ1ZpVEnwACgg8AAizLEFfI5wfykoCR4hjp",
    "CAACAgUAAx0Cd6nKUAACATJl_rsEJOsaaPSYGhU7bo7iEwL8AAPMDgACu2PYV8Vb8aT4_HUPHgQ",
]
HELP_IMG_URL = "https://files.catbox.moe/ag0igk.png"
# Media used by the main /start screen and group member welcome.
# Local fallbacks are kept in the handlers so a temporary Catbox outage does not break them.
START_IMG_URL = "https://files.catbox.moe/r71t39.png"
# Optional Telegram sticker file_id for the private /start intro. Leave empty to disable.
START_STICKER_FILE_ID = ""
GROUP_WELCOME_IMG_URL = "https://files.catbox.moe/zq3tue.jpg"
PING_VID_URL = "https://files.catbox.moe/3ivvgo.mp4"
PLAYBACK_GIF_URL = "https://files.catbox.moe/ge1piy.gif"
STATS_VID_URL = "https://telegra.ph/file/e2ab6106ace2e95862372.mp4"

# ── Playback card image ────────────────────────────────────────────────────────
# One image is used on every Now Playing / playback card (YouTube, Telegram
# audio/video, SoundCloud, live streams, skip/next).  It ships with the bot as a
# local file so a third-party host outage can never break the card.  Set the
# PLAYBACK_CARD_IMG env var to a file path or an https:// URL to override it.
_DEFAULT_PLAYBACK_CARD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AquaVibe", "assets", "AquaVibe", "playback_card.jpg",
)
PLAYBACK_CARD_IMG = getenv("PLAYBACK_CARD_IMG", "").strip() or _DEFAULT_PLAYBACK_CARD
PLAYLIST_IMG_URL = PLAYBACK_CARD_IMG
STREAM_IMG_URL = PLAYBACK_CARD_IMG
TELEGRAM_AUDIO_URL = PLAYBACK_CARD_IMG
TELEGRAM_VIDEO_URL = PLAYBACK_CARD_IMG
SOUNCLOUD_IMG_URL = PLAYBACK_CARD_IMG
MUSIC_IMG_URL = "https://files.catbox.moe/veykzq.jpg"
SPOTIFY_ARTIST_IMG_URL = SPOTIFY_ALBUM_IMG_URL = SPOTIFY_PLAYLIST_IMG_URL = MUSIC_IMG_URL

# ── Helpers ────────────────────────────────────────────────────────────────────
def time_to_seconds(time: str) -> int:
    return sum(int(x) * 60**i for i, x in enumerate(reversed(time.split(":"))))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

# ───── Bot Introduction Messages ───── #
AYU = ["💞", "🦋", "🔍", "🧪", "⚡️", "🔥", "🎩", "🌈", "🍷", "🥂", "🥃", "🕊️", "🪄", "💌", "🧨"]
AYUV = [
    "ʜᴇʟʟᴏ {0}, 🥀\n\n ɪᴛ'ꜱ ᴍᴇ {1} !\n\n┏━━━━━━━━━━━━━━━━━⧫\n┠┗━━━━━━━━━━━━━━━━━⧫\n┏━━━━━━━━━━━━━━━━━⧫\n┠ ➥ Uᴘᴛɪᴍᴇ : {2}\n┠ ➥ SᴇʀᴠᴇʀSᴛᴏʀᴀɢᴇ : {3}\n┠ ➥ CPU Lᴏᴀᴅ : {4}\n┠ ➥ RAM Cᴏɴsᴜᴘᴛɪᴏɴ : {5}\n┠ ➥ ᴜꜱᴇʀꜱ : {6}\n┠ ➥ ᴄʜᴀᴛꜱ : {7}\n┗━━━━━━━━━━━━━━━━━⧫\n\n🫧 ᴅᴇᴠᴇʟᴏᴩᴇʀ 🪽 ➪ [𝑫𝒆𝒗](https://t.me/xtmonk)",
    "ʜɪɪ, {0} ~\n\n◆ ɪ'ᴍ ᴀ {1} ᴛᴇʟᴇɢʀᴀᴍ ꜱᴛʀᴇᴀᴍɪɴɢ ʙᴏᴛ ᴡɪᴛʜ ꜱᴏᴍᴇ ᴜꜱᴇꜰᴜʟ\n◆ ᴜʟᴛʀᴀ ғᴀsᴛ ᴠᴄ ᴘʟᴀʏᴇʀ ꜰᴇᴀᴛᴜʀᴇꜱ.\n\n✨ ꜰᴇᴀᴛᴜʀᴇꜱ ⚡️\n◆ ʙᴏᴛ ғᴏʀ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴘs.\n◆ Sᴜᴘᴇʀғᴀsᴛ ʟᴀɢ Fʀᴇᴇ ᴘʟᴀʏᴇʀ.\n◆ ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ ᴍᴜꜱɪᴄ + ᴠɪᴅᴇᴏ.\n◆ ʟɪᴠᴇ ꜱᴛʀᴇᴀᴍɪɴɢ.\n◆ ɴᴏ ᴘʀᴏᴍᴏ.\n◆ ʙᴇꜱᴛ ꜱᴏᴜɴᴅ Qᴜᴀʟɪᴛʏ.\n◆ 24×7 ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ ᴍᴜꜱɪᴄ.\n◆ ᴀᴅᴅ ᴛʜɪꜱ ʙᴏᴛ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ᴍᴀᴋᴇ ɪᴛ ᴀᴅᴍɪɴ ᴀɴᴅ ᴇɴᴊᴏʏ ᴍᴜꜱɪᴄ 🎵.\n\n┏━━━━━━━━━━━━━━━━━⧫\n┠ ◆ ꜱᴜᴘᴘᴏʀᴛɪɴɢ ᴘʟᴀᴛꜰᴏʀᴍꜱ : ʏᴏᴜᴛᴜʙᴇ, ꜱᴘᴏᴛɪꜰʏ,\n┠ ◆ ʀᴇꜱꜱᴏ, ᴀᴘᴘʟᴇᴍᴜꜱɪᴄ , ꜱᴏᴜɴᴅᴄʟᴏᴜᴅ ᴇᴛᴄ.\n┗━━━━━━━━━━━━━━━━━⧫\n┏━━━━━━━━━━━━━━━━━⧫\n┠ ➥ Uᴘᴛɪᴍᴇ : {2}\n┠ ➥ SᴇʀᴠᴇʀSᴛᴏʀᴀɢᴇ : {3}\n┠ ➥ CPU Lᴏᴀᴅ : {4}\n┠ ➥ RAM Cᴏɴsᴜᴘᴛɪᴏɴ : {5}\n┠ ➥ ᴜꜱᴇʀꜱ : {6}\n┠ ➥ ᴄʜᴀᴛꜱ : {7}\n┗━━━━━━━━━━━━━━━━━⧫\n\n🫧 ᴅᴇᴠᴇʟᴏᴩᴇʀ 🪽 ➪ [𝐃ᴇᴠ](https://t.me/jesterxd)",
]

# ── Runtime structures ─────────────────────────────────────────────────────────
BANNED_USERS = filters.user()
adminlist, lyrical, autoclean, confirmer = {}, {}, [], {}

# ── Minimal validation ─────────────────────────────────────────────────────────
if SUPPORT_CHANNEL and not re.match(r"^https?://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHANNEL URL. Must start with https://")

if SUPPORT_CHAT and not re.match(r"^https?://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - Invalid SUPPORT_CHAT URL. Must start with https://")

# ── Free Nebula-compatible AI generation ─────────────────────────────────────
NEBULA_HORDE_BASE = getenv("NEBULA_HORDE_BASE", "https://stablehorde.net/api/v2")
NEBULA_HORDE_KEY = getenv("NEBULA_HORDE_KEY", "0000000000")
NEBULA_IMAGE_MODEL = getenv("NEBULA_IMAGE_MODEL", "AlbedoBase XL")
NEBULA_VIDEO_SPACE = getenv("NEBULA_VIDEO_SPACE", "cbensimon/wan2-2-fp8da-aoti-preview2")
NEBULA_IMAGE_TIMEOUT = int(getenv("NEBULA_IMAGE_TIMEOUT", "180"))
NEBULA_VIDEO_MAX_SECONDS = float(getenv("NEBULA_VIDEO_MAX_SECONDS", "4.5"))
NEBULA_VIDEO_STEPS = int(getenv("NEBULA_VIDEO_STEPS", "20"))
