# Authored By Dev © 2025
"""Inline mode (@bot ...).

Served here: whispers (``@bot @user your message``), the chess quick-challenge
(``@bot chess``) and the UNO hand picker (``@bot uno``).  Music search and the
play-related command shortcuts are not part of inline mode; any other query
simply gets an empty answer so Telegram never shows a stale result.
"""
from AquaVibe.core.runtime import app, LOGGER
from AquaVibe.plugins.social.ai_social import inline_social_router
from config import BANNED_USERS


@app.on_inline_query(~BANNED_USERS)
async def inline_query_handler(client, query):
    try:
        if await inline_social_router(query, client):
            return
    except Exception as exc:
        LOGGER("AquaVibe.inline").warning("Inline router failed: %s: %s", type(exc).__name__, exc)
    try:
        await client.answer_inline_query(query.id, results=[], cache_time=1)
    except Exception:
        return
