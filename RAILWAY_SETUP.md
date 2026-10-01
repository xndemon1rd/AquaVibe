# AquaVibe — Railway Setup

## Required Variables

Set these in Railway → Variables before deploying:

- `API_ID` — Telegram API ID
- `API_HASH` — Telegram API hash
- `BOT_TOKEN` — bot token from BotFather
- `OWNER_ID` — numeric Telegram user ID of the owner
- `MONGO_DB_URI` — MongoDB connection URI
- `STRING_SESSION` — Pyrogram assistant session string

At least one `STRING_SESSION` is required for voice playback. `STRING_SESSION2` through `STRING_SESSION5` are optional.

## Recommended Variables

- `LOGGER_ID` — numeric Telegram log group/channel ID. Leave unset (`0`) if Telegram logging is not wanted.
- `LOGGER_CHAT` — public log chat username or joinable invite link target for assistants.
- `LOGGER_INVITE_LINK` — private log-chat invite link, if needed.
- `GROUPS_TO_JOIN` — optional comma-separated public groups/chats that assistants should join at startup.

Example:

```text
GROUPS_TO_JOIN=@musicgroup,@anothergroup
```

## AI (works with no key at all)

Chat AI tries providers in this order and uses the first one that answers:

1. Gemini (`GEMINI_API_KEY`) - free tier; falls back through `gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gemini-3.8-flash` if a model is retired, over quota or busy
2. Groq (`GROQ_API_KEY`) - free tier
3. Mistral (`MISTRAL_API_KEY`) - free tier
4. OpenRouter (`OPENROUTER_API_KEY`) - uses the free-models router
5. Ollama (`OLLAMA_ENABLED=true`) - your own server
6. LLM7.io - **no key needed**
7. OVHcloud AI Endpoints - **no key needed** (2 requests/min per model)

Providers without a key are skipped, so 6 and 7 always keep the bot answering. Optional variables:

- `AI_PROVIDER_ORDER` e.g. `groq,gemini,llm7,ovh` (names: gemini, groq, mistral, openrouter, ollama, llm7, ovh)
- `GEMINI_MODEL`, `GROQ_MODEL`, `MISTRAL_MODEL`, `OPENROUTER_MODEL` (comma-separated lists are tried in order)
- `LLM7_API_KEY` (free token from token.llm7.io for higher limits), `LLM7_MODEL`, `LLM7_ENABLED`
- `OVH_AI_MODEL`, `OVH_AI_ENABLED`
- `ANTHROPIC_API_KEY` is only used for self-healing repairs, never for chat

xAI/Grok and OpenAI were removed (paid credits required). `/cimage`, `/getdraw` and `/cvideo` use the free Nebula bridge and need no key.

### Local Ollama (no API key / no credits)
AquaVibe can use a locally running Ollama server as an optional text-AI provider.

For a machine where Ollama is installed and running:
- `OLLAMA_ENABLED=true`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=llama3.2` (or another model you have pulled)
- `OLLAMA_TIMEOUT=90`

Install a model first, for example: `ollama pull llama3.2`.

**Important for Railway:** `127.0.0.1` means the Railway container itself, not your phone/PC. To use Ollama from Railway, run Ollama on a separate reachable server and set `OLLAMA_BASE_URL` to that server's URL. Do not expose an unauthenticated Ollama endpoint to the public internet.

### AI chat, stickers and reactions

- No key required (free providers are built in); add `GEMINI_API_KEY` for the best quality. Owner command `/aistatus` live-tests every provider and shows the exact error.
- The AI answers in DMs, and in groups when mentioned, replied to, or called by name ("aqua ..."). `/chatty` lets it join in on its own.
- For random reactions and `/chatty` in groups the bot must see every message: **BotFather -> /setprivacy -> Disable** (or make the bot a group admin). Replies to the bot (incl. sticker replies) work even with privacy on.
- Optional tuning: `AI_PRIVATE_CHAT`, `AI_REACT_CHANCE`, `AI_REACT_CHANCE_DIRECT`, `AI_REACT_COOLDOWN`, `AI_CHATTY_CHANCE`, `AI_CHATTY_COOLDOWN`, `AI_STICKER_CHANCE_CHATTY`, `AI_STICKER_REPLY`.

## Important Telegram permissions

For music playback in a group, the assistant account must be able to access the group and manage the voice/video chat. The bot should also have the permissions required by the commands you use, including managing video chats where applicable.

## Deployment

Railway uses the included `Dockerfile` and starts the bot with:

```text
python3 -m AquaVibe
```

Do not upload `.env`, Telegram session files, cookies, or API keys to the repository.

## Whisper (inline private messages)
- Uses inline mode, so enable it in BotFather (`/setinline`). Optionally also `/setinlinefeedback` (set it to Enabled).
- `WHISPER_SECRET` (optional): secret used to encrypt stored whispers. If empty, the key is derived from `BOT_TOKEN`.
  Changing it makes whispers that are still stored unreadable (they expire anyway).
- Requires the `cryptography` package (already in `requirements.txt`).
