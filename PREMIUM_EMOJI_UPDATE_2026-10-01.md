# Premium emoji update — 2026-10-01
- Added 66 owner-supplied custom emoji IDs (`NEW_PREMIUM_EMOJI` in `AquaVibe/core/premium_emoji.py`); they override older IDs for the same emoji (🔒 🤖 🧠 🌐 🤝 🎧 🎁 🔨 ✍️). 🥳 was supplied twice; the first ID is used.
- Every mapped emoji now also works on inline buttons (leading emoji, or trailing if none leading) via `BUTTON_ICON_EMOJI`.
- New `install_html_emoji_hooks()` (enabled in `core/bot.py`): converts mapped emoji in all normal messages/captions to `<emoji id=..>` tags, so `parse_mode` / `<b>` / `<a>` keep working. Skipped for explicit entities, non-HTML parse modes, and text inside <code>/<pre>/tags.
- Heart set (`HEART_PREMIUM_EMOJI`): 💗 💞 🩷 💚 💙 💜 🖤 🤍 🌹 💋 now use owner-supplied IDs (replaces old 💗 💞 💜 🤍 🖤 💋 IDs; adds 🩷 💚 💙 🌹). 💞 no longer shares 🎲's ID.

## Whisper update
- New owner batch `OWNER_PREMIUM_EMOJI_2`: 🏆 💗 🔥 🐾 💔 🔐 🔧 💊 ⭐ 🔄 (overrides older IDs for the same emoji).
- Whisper: deep-link / usage text now use the live bot username (`app.username`) instead of the `BOT_USERNAME` env default (`aquavibebot`).
- Whisper requires `cryptography` (in requirements.txt). Without it whispers are memory-only and vanish on restart.
