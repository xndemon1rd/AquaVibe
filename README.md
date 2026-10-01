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
- AI chat with fallback: Gemini, Groq, Mistral, OpenRouter(free), Ollama, plus free no-key LLM7 and OVHcloud

## Deployment
Railway can run the repository root with the included `Dockerfile` and `start` launcher.

Required environment variables:
`API_ID`, `API_HASH`, `BOT_TOKEN`, `OWNER_ID`, `MONGO_DB_URI`, and at least one assistant `STRING_SESSION`.

See `RAILWAY_SETUP.md` for the deployment variables.

## Aqua VIP / VIP Pro Coding Agent

- `/vip` opens the ₹500 VIP and ₹700 VIP Pro interface.
- `/addemail user@example.com` records a user's Puter email identity. The bot never asks for a Puter password or auth token.
- `/paid vip UTR` or `/paid pro UTR` sends a manual payment approval request to the owner. Configure `VIP_UPI_ID` and/or `VIP_CRYPTO_ADDRESS`.
- `/ask <task>` is available to active VIP/VIP Pro users. Reply to a `.zip` with `/ask <task>` to edit a repository and receive a new ZIP.
- Coding work is performed in a disposable workspace and basic Python compilation is run before packaging.
- VIP Pro is intended for larger repositories, longer jobs and priority processing; the exact resource limits are controlled by environment variables.
- Self-healing never edits production automatically. Runtime errors can produce an owner-only proposal with **VIEW DIFF / APPROVE / REJECT**. Approval creates a backup and runs a Python compile check; failed patches are rolled back.
- `PUTER_CODING_ENDPOINT` is an optional bridge for a legitimate user-authenticated Puter/Claude workflow. The normal fallback uses AquaVibe's existing AI providers.
