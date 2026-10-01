# 2026-09-30
- Removed `/approve` and `/unapprove` (handlers, help cards, help lists, catalog). Join requests still get Accept / Reject buttons.
- Added 50 commands to the catalog with help cards: addemail, ask, paid, cvideo, unomap, kickall, banall, unbanall, muteall, unmuteall, cutie, gay, lesbian, and 32 reaction GIF commands (hug, slap, kiss ...).
- Button colour delay: warm-up + keep-alive for the Bot API connection, IPv4-only fast connect, shorter rate-limit wait.
- `PREMIUM_EMOJI_CANDIDATES.md`: emoji used in the bot that are not yet premium emoji.
- Premium emoji: `DEFAULT_EMOJI` rewritten with the 36 new IDs (⚡ 🌍 🧠 🥀 😴 🪽 🌸 🤝 💜 🤍 🦋 💕 💞 🫧 🕊 🍒 🥰 ❤ 💍 🧸 🌐 🎧 🏠 📅 🤔 ↝ ↜ 🏓 🕚 🏀 😫 🙂 🌈 🪄 🎁 🍷). Old placeholder keys that pointed at those same IDs were removed. `custom_emoji_entities()` now also covers a trailing U+FE0F (e.g. 🕊️).
- Premium emoji (round 3): added 🔒 💗 🤖 ✨ 🥀 ✅ ❌. 🥀 now uses the new ID; ⚡ and 💓 were removed because their IDs were reassigned to 🔒 and 💗. Fixed 💍, which had silently kept an older ID instead of `5267334530171169409`.
- `utils/decorator.py`: `admin_required` now replies instead of crashing when `get_member` raises `ChannelPrivate`.
- AI error fix (self-healing) made stricter and more accurate: edit-based patches with pre-checks instead of full-file rewrites, cooldown + hourly cap, retry with rejection reason, stale-file check on approve, long diffs as a file, optional Claude provider (`ANTHROPIC_API_KEY`). `utils/ai.py` `ask()` gained `system`, `max_tokens`, `temperature`, `max_input`, `timeout`, `prefer`, `strict`; normal chat behaviour is unchanged. Fixed: the old flow cut the file to 8,000 chars and the reply to 1,800 tokens, so a proposed "complete replacement file" could be truncated and then applied.


## Aqua Whisper + Aqua Anime
- Inline whisper now uses `whisper @username message`.
- Both the sender and addressed user can open the secret via the inline button; other group members receive only the placeholder/locked button.
- Each whisper expires after 15 minutes and is removed after both participants have opened it.
- Inline whisper results are personal to reduce result reuse.
- Added Aqua-branded anime integration documentation based on the documented AniPlay architecture; no inactive upstream API endpoint is hard-coded.

## Fix pass (whisper / anime / start)
- Aqua Anime was documentation only (no handler). Added `plugins/anime/search.py`: `/anime <name>` via Jikan, with details, official watch links and paged episodes.
- Whisper: the addressed user is now matched by their own @username first (no `get_users` network lookup that could fail); deletion after both opened no longer needs a second lookup.
- /start: welcome media file_id is now saved in Mongo (survives restarts, so no 5 MB re-upload on the first /start after deploy); the plain-text fallback is sent before the error report instead of after it.

## Catalog: Anime category
- New help category "Anime" (🌸) in the Command Center, listed before Fun & Games. It holds only anime commands: /anime, /asearch, /waifu and the 32 nekos.best anime GIF reactions (hug, slap, kiss, pat, ...). /waifu moved here from AI Studio and the reactions moved out of Fun & Games.
- /anime and /asearch added to the command catalog (ALL_COMMANDS) with help cards. Audit: every statically registered command is now in the catalog.
- The joke-percentage commands (/cute, /gay ...) are not anime GIFs and stay in Fun & Games.
- /start?start=help (group /help -> DM) now opens the catalog as plain text, no image.

## AI chat+ (plugins/social/ai_chat_plus.py)
- Any language: persona + "reply in the user's language and script" rules now go through `ask(system=...)`. Before, the prompt was inserted as the first history message, and `ask()` only keeps the last 8 messages, so after ~4 exchanges the bot forgot its persona and language rules.
- Memory turns are stored as "Name: text" so the bot knows who is talking in a group; replies to other people's messages include the quoted text as context. Memory capped at 80 turns per chat.
- Provider failures no longer get saved/sent as if they were answers (`strict=True`).
- Removed `app.get_me()` on every group message (uses `app.id` / `app.username`). The old duplicate listener in ai_social.py is gone; `/ai` uses the same engine.
- Sticker -> sticker: a sticker sent in reply to the bot is answered with a sticker from the same pack (same emoji if possible), else one the bot has seen in the chat, else the same sticker. Toggle: `AI_STICKER_REPLY`.
- Random reactions: ~8% of normal group messages and ~40% of messages addressed to the bot get an emoji reaction (keyword-aware: laugh, love, congrats, thanks ...), max one per 20 s per group. Admins toggle with `/reactions on|off` (now ON by default). Env: `AI_REACT_CHANCE`, `AI_REACT_CHANCE_DIRECT`, `AI_REACT_COOLDOWN`. `/quiet` mode silences all of it.
