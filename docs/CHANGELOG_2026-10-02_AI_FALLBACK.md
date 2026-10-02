# 2026-10-02 - AI providers cleaned up, free no-key AI added

- Removed xAI/Grok and OpenAI (paid credits, failed without billing) and all dead Gemini image/video code (`/cimage`, `/getdraw`, `/cvideo` already use the free Nebula bridge).
- Added free **no-key** providers: LLM7.io and OVHcloud AI Endpoints (anonymous tier).
- New fallback order: Gemini -> Groq -> Mistral -> OpenRouter (free router) -> Ollama -> LLM7 -> OVHcloud. Override with `AI_PROVIDER_ORDER`.
- Anthropic is no longer in the chat chain; only used for self-healing (`prefer="Anthropic"`).
- Gemini: default model is now the stable `gemini-3.5-flash`; automatic model fallback on 404/429/5xx; thinking tokens no longer returned as text; every provider failure is now written to the log with the API's own message.
- OpenRouter default changed from `openrouter/auto` (paid) to `openrouter/free`.

## Chat not replying (same day)
- Root cause: `persona_engine.ensure()` put `name` in both `$setOnInsert` and `$set`; MongoDB rejected it (code 40), and because it runs before the AI call, every chat reply failed with "Owner info: Updating the path 'name'...".
- Fixed `ensure()`; it also no longer overwrites a saved name with "Friend" when called without a name (`dream_if_due`).
- `ai_reply_ex()` now continues without companion memory if the persona database step ever fails, so a DB problem can no longer silence the bot.
