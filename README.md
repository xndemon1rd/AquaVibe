# 蒼響 (アクアバイブ)

> Japanese brand name for the bot: 蒼響 / アクアバイブ

A Telegram group voice-chat music bot built with Pyrogram and PyTgCalls.

## Current stack
- Python 3.12
- Pyrofork 2.3.69
- PyTgCalls 2.3.3
- ntgcalls 2.2.5
- MongoDB
- alternative providers public audio/video metadata and direct media files
- alternative providers primary source with  public-API audio backup
- Optional Gemini, Groq and OpenAI AI providers

## Deployment
Railway can run the repository root with the included `Dockerfile` and `start` launcher.

Required environment variables:
`API_ID`, `API_HASH`, `BOT_TOKEN`, `OWNER_ID`, `MONGO_DB_URI`, and at least one assistant `STRING_SESSION`.

See `RAILWAY_SETUP.md` for the deployment variables.
