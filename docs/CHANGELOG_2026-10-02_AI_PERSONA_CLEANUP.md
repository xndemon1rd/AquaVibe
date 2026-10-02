# 2026-10-02 — AI persona, owner rules, command removal, cleanup

## AI
- Aqua is now very casual and highly emotional/expressive (system prompt in `plugins/social/ai_chat_plus.py`; also `utils/ai.py`, `plugins/social/ai_social.py`; defaults in `utils/persona_engine.py`). Safety rules for crisis / grief / serious moments are unchanged and still override the playful tone.
- Owner rules: Aqua is loyal and respectful towards the owner and never reveals who he is. When someone asks who the owner/creator/developer is (English, Hinglish, Hindi — `_asks_about_owner`), Aqua refuses playfully ("my owner is a mystery, you're not worthy of knowing him yet") in the user's language. When the owner (`OWNER_ID`) is the one talking, Aqua greets with extra warmth and respect.

## Removed commands (code + help entries)
- `/setprofilebanner`, `/setprofilephoto`, `/refer`.
- Removed their help/catalog entries (`plugins/bot/help.py`, `utils/command_help.py`, `utils/command_catalog.py`).
- Removed now-unused DB helpers from `utils/database.py`: profile photo/banner, custom (VIP) banners, referrer, group-referral records.
- Deleted `AquaVibe/_disabled_plugins/` (the unloaded economy/VIP plugin that contained these commands).

## Cleanup
- Moved loose changelog/audit notes into `docs/` (README.md and RAILWAY_SETUP.md stay in the root).
- Removed `__pycache__` / `.pyc` files.
