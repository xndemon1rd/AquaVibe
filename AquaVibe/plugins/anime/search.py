"""Aqua Anime: /anime <name> -> results -> details (+official watch links) -> episodes.

Data comes from the public Jikan API (unofficial MyAnimeList API, no key needed).
Watch buttons are the *official* streaming links MyAnimeList lists for the
title (Crunchyroll, Netflix, ...), so nothing here depends on a pirate stream
host that can disappear.
"""
from __future__ import annotations

import asyncio
import html
import time

import aiohttp
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from AquaVibe.core.runtime import app
from AquaVibe.utils.database import get_ai_plan

JIKAN = "https://api.jikan.moe/v4"
_TTL = 600
_CACHE: dict = {}
_LOCK = asyncio.Lock()
_LAST_CALL = 0.0
_MIN_GAP = 0.45  # Jikan allows ~3 req/s; stay well under it


async def _get(path: str, params: dict | None = None):
    """GET from Jikan with a tiny cache, spacing between calls and one 429 retry."""
    global _LAST_CALL
    key = (path, tuple(sorted((params or {}).items())))
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    timeout = aiohttp.ClientTimeout(total=12)
    for attempt in (1, 2):
        async with _LOCK:
            wait = _MIN_GAP - (time.time() - _LAST_CALL)
            if wait > 0:
                await asyncio.sleep(wait)
            _LAST_CALL = time.time()
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(JIKAN + path, params=params) as resp:
                if resp.status == 429 and attempt == 1:
                    await asyncio.sleep(1.5)
                    continue
                if resp.status != 200:
                    raise RuntimeError(f"Jikan HTTP {resp.status}")
                data = await resp.json(content_type=None)
        if len(_CACHE) > 300:
            _CACHE.clear()
        _CACHE[key] = (time.time(), data)
        return data
    raise RuntimeError("Jikan rate limited")


def _clip(text: str | None, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


@app.on_message(filters.command(["anime", "asearch"]))
async def anime_search(_, m: Message):
    plan = await get_ai_plan(m.from_user.id)
    if plan == "none":
        return await m.reply_text("🔒 <b>Aqua Anime</b> is available only for VIP and VIP Pro members.\nUse <code>/vip</code> to view plans.")
    query = " ".join(m.command[1:]).strip()
    if not query and m.reply_to_message and (m.reply_to_message.text or m.reply_to_message.caption):
        query = (m.reply_to_message.text or m.reply_to_message.caption).strip()
    if not query:
        return await m.reply_text("🌸 <b>Aqua Anime</b>\nUsage: <code>/anime naruto</code>")
    status = await m.reply_text("🔎 Searching anime…")
    try:
        data = await _get("/anime", {"q": query[:100], "limit": 8, "sfw": "true"})
    except Exception:
        return await status.edit_text("❌ Anime service is busy or unreachable. Try again in a moment.")
    items = data.get("data") or []
    if not items:
        return await status.edit_text(f"😔 No anime found for <b>{html.escape(query[:60])}</b>.")
    rows = []
    for a in items:
        title = a.get("title_english") or a.get("title") or "Unknown"
        year = a.get("year") or ""
        label = _clip(f"{title} {('(' + str(year) + ')') if year else ''}", 56)
        rows.append([InlineKeyboardButton(label, callback_data=f"AN:i:{a['mal_id']}")])
    await status.edit_text(
        f"🌸 <b>Aqua Anime</b> — results for <b>{html.escape(query[:60])}</b>",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@app.on_callback_query(filters.regex(r"^AN:i:\d+$"))
async def anime_info(_, cb: CallbackQuery):
    if (await get_ai_plan(cb.from_user.id)) == "none":
        return await cb.answer("🔒 VIP or VIP Pro is required for Anime.", show_alert=True)
    mal_id = int(cb.data.split(":")[2])
    await cb.answer("Loading…")
    try:
        a = (await _get(f"/anime/{mal_id}/full")).get("data") or {}
    except Exception:
        return await cb.answer("❌ Anime service is busy, try again.", show_alert=True)
    title = a.get("title_english") or a.get("title") or "Unknown"
    genres = ", ".join(g["name"] for g in a.get("genres", [])[:5]) or "—"
    caption = (
        f"🌸 <b>{html.escape(title)}</b>\n"
        f"<i>{html.escape(a.get('title_japanese') or a.get('title') or '')}</i>\n\n"
        f"⭐ <b>Score:</b> {a.get('score') or 'N/A'}   📺 <b>Type:</b> {a.get('type') or '—'}\n"
        f"🎞 <b>Episodes:</b> {a.get('episodes') or '?'}   📡 <b>Status:</b> {html.escape(a.get('status') or '—')}\n"
        f"🎭 <b>Genres:</b> {html.escape(genres)}\n\n"
        f"{html.escape(_clip(a.get('synopsis'), 420))}"
    )
    rows = []
    links = [s for s in (a.get("streaming") or []) if s.get("url")][:4]
    if links:
        rows.append([InlineKeyboardButton(f"▶ {_clip(s.get('name') or 'Watch', 18)}", url=s["url"]) for s in links[:2]])
        if len(links) > 2:
            rows.append([InlineKeyboardButton(f"▶ {_clip(s.get('name') or 'Watch', 18)}", url=s["url"]) for s in links[2:4]])
    tail = [InlineKeyboardButton("📃 Episodes", callback_data=f"AN:e:{mal_id}:1")]
    if a.get("url"):
        tail.append(InlineKeyboardButton("🔗 MyAnimeList", url=a["url"]))
    rows.append(tail)
    markup = InlineKeyboardMarkup(rows)
    poster = ((a.get("images") or {}).get("jpg") or {}).get("large_image_url")
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    try:
        if poster:
            await app.send_photo(chat_id, poster, caption=caption[:1020], reply_markup=markup)
        else:
            await app.send_message(chat_id, caption, reply_markup=markup)
    except Exception:
        await app.send_message(chat_id, caption[:4000], reply_markup=markup)


@app.on_callback_query(filters.regex(r"^AN:e:\d+:\d+(:n)?$"))
async def anime_episodes(_, cb: CallbackQuery):
    if (await get_ai_plan(cb.from_user.id)) == "none":
        return await cb.answer("🔒 VIP or VIP Pro is required for Anime.", show_alert=True)
    parts = cb.data.split(":")
    mal_id, page = int(parts[2]), max(1, int(parts[3]))
    try:
        data = await _get(f"/anime/{mal_id}/episodes", {"page": page})
    except Exception:
        return await cb.answer("❌ Anime service is busy, try again.", show_alert=True)
    eps = data.get("data") or []
    if not eps:
        return await cb.answer("No episode list available for this title.", show_alert=True)
    lines = [f"<b>{e.get('mal_id')}.</b> {html.escape(_clip(e.get('title') or 'Episode', 60))}" for e in eps]
    text = "📃 <b>Episodes</b> (page %d)\n\n%s" % (page, "\n".join(lines))
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"AN:e:{mal_id}:{page - 1}:n"))
    if (data.get("pagination") or {}).get("has_next_page"):
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"AN:e:{mal_id}:{page + 1}:n"))
    markup = InlineKeyboardMarkup([nav]) if nav else None
    await cb.answer()
    if cb.data.endswith(":n") and cb.message:  # paging: edit the list in place
        try:
            return await cb.message.edit_text(text[:4000], reply_markup=markup)
        except Exception:
            return
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    await app.send_message(chat_id, text[:4000], reply_markup=markup)
