# /start speed + premium emoji (2026-09-30)

## /start (DM) delay / not starting
- Welcome video (5.7 MB) / image were re-uploaded on every /start -> now the Telegram file_id is cached after the first send (also the catbox GIF).
- Removed unused get_served_chats / get_served_users / bot_sys_stats (bot_sys_stats blocked the event loop 0.5 s via psutil.cpu_percent(interval=0.5)).
- "Hie <name>" emoji animation no longer blocks (was ~2.7 s of sleeps); it runs in the background.
- add_served_user and the LOGGER "just started" notice run in the background; gender is read once.
- If the media send fails, a plain-text welcome with buttons is sent instead of nothing.

## Premium emoji
Mapped in AquaVibe/core/premium_emoji.py: 🎶 👤 💎 🎲 🔨 📦 ⚙️
- UI text: anything built with custom_emoji_entities() (help, start, ping...) and now the private welcome caption.
- Buttons: a leading 🎶/👤/💎/🎲/🔨/📦/⚙ becomes a native icon (icon_custom_emoji_id) automatically (BUTTON_ICON_EMOJI in premium_emoji.py).
