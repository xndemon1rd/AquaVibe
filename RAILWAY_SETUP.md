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

## Optional AI

Text AI supports provider fallback. Add one or more:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENAI_API_KEY`

Optional model overrides:

- `GEMINI_MODEL`
- `GROQ_MODEL`
- `AI_MODEL`
- `AI_IMAGE_MODEL`

`/cimage` requires `OPENAI_API_KEY`.


## Important Telegram permissions

For music playback in a group, the assistant account must be able to access the group and manage the voice/video chat. The bot should also have the permissions required by the commands you use, including managing video chats where applicable.

## Deployment

Railway uses the included `Dockerfile` and starts the bot with:

```text
python3 -m AquaVibe
```

Do not upload `.env`, Telegram session files, cookies, or API keys to the repository.
