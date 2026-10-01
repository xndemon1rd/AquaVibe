"""/ranking - group rankings for Economy (coins), Songs played and XP, with tab buttons."""
from __future__ import annotations

from AquaVibe.utils.economy import money
import html

from pyrogram import filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app
from AquaVibe.utils.play_stats import PLAYS
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
InlineKeyboardButton = ColoredInlineKeyboardButton

XP = mongodb.aquavibe_leaderboard
ECO = mongodb.aqua_economy
LIMIT = 10
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

TABS = {
    "economy": ("💰", "Economy"),
    "songs": ("🎵", "Songs Played"),
    "xp": ("✨", "XP"),
}


def _row(pos: int, doc: dict, value: str) -> str:
    name = html.escape((doc.get("name") or "User").strip())[:24]
    tag = MEDALS.get(pos, f"<b>{pos}.</b>")
    return f'{tag} <a href="tg://user?id={int(doc["user_id"])}">{name}</a> — {value}'


async def _rows(chat_id: int, kind: str):
    if kind == "economy":
        col, field = ECO, "balance"
        fmt = lambda d: f"<b>{money(d.get('balance', 0))}</b>"
    elif kind == "songs":
        col, field = PLAYS, "plays"
        fmt = lambda d: f"<b>{int(d.get('plays', 0)):,}</b> songs"
    else:
        col, field = XP, "xp"
        fmt = lambda d: f"<b>{int(d.get('xp', 0)):,}</b> XP"
    rows = []
    async for d in col.find({"chat_id": chat_id, field: {"$gt": 0}}).sort(field, -1).limit(LIMIT):
        rows.append(_row(len(rows) + 1, d, fmt(d)))
    return rows


async def _my_line(chat_id: int, user_id: int, kind: str) -> str:
    col, field = {"economy": (ECO, "balance"), "songs": (PLAYS, "plays"), "xp": (XP, "xp")}[kind]
    doc = await col.find_one({"chat_id": chat_id, "user_id": user_id})
    if not doc or int(doc.get(field, 0)) <= 0:
        return "You: not ranked yet"
    higher = await col.count_documents({"chat_id": chat_id, field: {"$gt": int(doc[field])}})
    return f"You: <b>#{higher + 1}</b>"


async def _render(chat_id: int, user_id: int, kind: str):
    icon, title = TABS[kind]
    rows = await _rows(chat_id, kind)
    body = "\n".join(rows) if rows else "No data yet."
    if kind == "songs" and not rows:
        body = "No songs played yet. Use /play to get on the board!"
    if kind == "economy" and not rows:
        body = "No coins yet. Use /daily to get started!"
    if kind == "xp" and not rows:
        body = "No XP yet. Chat in the group to earn some!"
    text = f"{icon} <b>{title.upper()} RANKING</b>\n\n{body}\n\n{await _my_line(chat_id, user_id, kind)}"
    buttons = [
        InlineKeyboardButton(
            text=(f"• {i} {t} •" if k == kind else f"{i} {t}"),
            callback_data=f"rank:{k}",
            **({"aqua_style": "primary"} if k == kind else {}),
        )
        for k, (i, t) in TABS.items()
    ]
    markup = InlineKeyboardMarkup([buttons[:2], buttons[2:], [InlineKeyboardButton(text="✖ Close", callback_data="close")]])
    return text, markup


@app.on_message(filters.command(["ranking", "rankings"]) & filters.group)
async def ranking_cmd(_, message: Message):
    kind = "economy"
    if len(message.command) > 1:
        arg = message.command[1].lower()
        kind = {"eco": "economy", "coins": "economy", "song": "songs", "music": "songs", "level": "xp"}.get(arg, arg)
        if kind not in TABS:
            kind = "economy"
    text, markup = await _render(message.chat.id, message.from_user.id, kind)
    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


@app.on_callback_query(filters.regex(r"^rank:(economy|songs|xp)$"))
async def ranking_cb(_, cb: CallbackQuery):
    kind = cb.data.split(":", 1)[1]
    text, markup = await _render(cb.message.chat.id, cb.from_user.id, kind)
    await cb.answer()
    try:
        await cb.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except MessageNotModified:
        pass
