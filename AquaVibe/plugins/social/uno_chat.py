"""UNO played in the group chat itself using Telegram inline mode — no Mini App.

How it plays (same idea as the classic @unobot):
  /uno            -> lobby message with Join / Start buttons
  🃏 Play a card   -> opens the inline picker in the chat: only YOUR playable cards are listed.
                     Pick one and it is played. Wild cards list one entry per colour.
  🎴 Draw / ⏭ Pass / 👀 My hand are normal buttons under the game message.

Needs BotFather:  /setinline (enable)  and  /setinlinefeedback -> Enabled (100%).
Optional: register real UNO stickers with /unomap so the picker shows stickers instead of text cards.
"""
from __future__ import annotations

import asyncio
import html
import time
import uuid

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

try:  # not present in every Pyrogram fork; we fall back to text cards
    from pyrogram.types import InlineQueryResultCachedSticker
except Exception:  # pragma: no cover
    InlineQueryResultCachedSticker = None

import config
from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app
from AquaVibe.plugins.social.ai_social import _enabled, _mention, _name
from AquaVibe.utils import uno_engine as eng
from AquaVibe.utils.economy import credit, money

UNOC = mongodb.aqua_uno_chat
STK = mongodb.aqua_uno_stickers

_locks: dict[str, asyncio.Lock] = {}
_tasks: set[asyncio.Task] = set()
STALE_LOBBY = 1800


def _lock(gid: str) -> asyncio.Lock:
    return _locks.setdefault(gid, asyncio.Lock())


def _nm(game: dict, uid: int) -> str:
    return html.escape(game.get("names", {}).get(str(uid), "Player"))


def _mn(game: dict, uid: int) -> str:
    return f'<a href="tg://user?id={int(uid)}">{_nm(game, uid)}</a>'


async def _save(game: dict) -> None:
    game["updated_at"] = time.time()
    await UNOC.replace_one({"game_id": game["game_id"]}, game)


async def _is_admin(chat_id: int, uid: int) -> bool:
    if int(uid) == int(config.OWNER_ID):
        return True
    try:
        m = await app.get_chat_member(chat_id, uid)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


# ───────────────────────── lobby ─────────────────────────
def _lobby_view(game: dict):
    names = "\n".join(f"• {_mn(game, p)}" + (" 👑" if p == game["host"] else "") for p in game["players"])
    text = (f"🃏 <b>UNO lobby</b>\nHost: {_mn(game, game['host'])}\n\n<b>Players ({len(game['players'])}/{config.UNO_MAX_PLAYERS}):</b>\n{names}\n\n"
            f"Winner takes <b>{money(config.UNO_WIN_REWARD)}</b>. Needs 2+ players.")
    gid = game["game_id"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🙋 Join", callback_data=f"UNOJ:{gid}"), InlineKeyboardButton("🚪 Leave", callback_data=f"UNOL:{gid}")],
        [InlineKeyboardButton("▶️ Start (host)", callback_data=f"UNOS:{gid}"), InlineKeyboardButton("✖️ Cancel", callback_data=f"UNOX:{gid}")],
    ])
    return text, kb


@app.on_message(filters.command("uno") & filters.group, group=31)
async def uno_cmd(_, m: Message):
    if not await _enabled(m.chat.id, "games"):
        return
    now = time.time()
    old = await UNOC.find_one({"chat_id": m.chat.id, "status": {"$in": ["lobby", "active"]}})
    if old:
        if now - float(old.get("updated_at", 0)) < STALE_LOBBY:
            return await m.reply_text("🃏 A UNO game is already running here. Host or an admin can stop it with <code>/unoend</code>.")
        await UNOC.update_one({"game_id": old["game_id"]}, {"$set": {"status": "ended"}})
    game = {
        "game_id": uuid.uuid4().hex[:12], "chat_id": m.chat.id, "host": m.from_user.id, "players": [m.from_user.id],
        "names": {str(m.from_user.id): _name(m.from_user)}, "status": "lobby", "created_at": now, "updated_at": now,
        "msg_id": 0, "afk": {}, "log": "",
    }
    text, kb = _lobby_view(game)
    sent = await m.reply_text(text, reply_markup=kb)
    game["msg_id"] = sent.id
    await UNOC.insert_one(game)


@app.on_callback_query(filters.regex(r"^UNO[JLSX]:"))
async def uno_lobby_cb(_, cb: CallbackQuery):
    act, gid = cb.data[3], cb.data.split(":", 1)[1]
    async with _lock(gid):
        game = await UNOC.find_one({"game_id": gid})
        if not game or game.get("status") != "lobby":
            return await cb.answer("This lobby is closed.", show_alert=True)
        uid = int(cb.from_user.id)
        if act == "J":
            if uid in game["players"]:
                return await cb.answer("You're already in.")
            if len(game["players"]) >= config.UNO_MAX_PLAYERS:
                return await cb.answer("Lobby is full.", show_alert=True)
            game["players"].append(uid)
            game["names"][str(uid)] = _name(cb.from_user)
        elif act == "L":
            if uid == game["host"]:
                return await cb.answer("The host can't leave — use Cancel.", show_alert=True)
            if uid not in game["players"]:
                return await cb.answer("You're not in this lobby.")
            game["players"].remove(uid)
        elif act == "X":
            if uid != game["host"] and not await _is_admin(game["chat_id"], uid):
                return await cb.answer("Only the host or an admin can cancel.", show_alert=True)
            game["status"] = "ended"
            await _save(game)
            await cb.edit_message_text("🃏 UNO lobby cancelled.")
            return await cb.answer()
        elif act == "S":
            if uid != game["host"]:
                return await cb.answer("Only the host can start.", show_alert=True)
            if len(game["players"]) < 2:
                return await cb.answer("Need at least 2 players.", show_alert=True)
            state = eng.new_game(game["players"])
            game.update(state)
            game["status"] = "active"
            game["afk"] = {}
            game["log"] = "Cards dealt — good luck!"
            await _save(game)
            await cb.answer("Game started!")
            try:
                await cb.message.delete()
            except Exception:
                pass
            await _post_status(game, repost=True, first=True)
            return
        await _save(game)
        text, kb = _lobby_view(game)
        try:
            await cb.edit_message_text(text, reply_markup=kb)
        except Exception:
            pass
        await cb.answer()


# ───────────────────────── status message ─────────────────────────
def _status_view(game: dict, first: bool = False):
    cur = eng.current(game)
    lines = [f"🃏 <b>UNO</b> · top card: <b>{eng.label(game['top'])}</b>"]
    if game["top"].startswith("wild"):
        lines[0] += f"  (color {eng.COLOR_EMOJI[game['color']]})"
    lines.append("")
    for p in game["players"]:
        n = len(game["hands"].get(str(p), []))
        arrow = "▶️" if p == cur else "▫️"
        lines.append(f"{arrow} {_nm(game, p)} — {n} card{'s' if n != 1 else ''}" + (" 🔔 UNO!" if n == 1 else ""))
    if game.get("log"):
        lines += ["", f"<i>{game['log']}</i>"]
    lines += ["", f"👉 <b>{_mn(game, cur)}</b>, your turn ({config.UNO_TURN_TIMEOUT}s)."]
    if game.get("drawn"):
        lines.append("You drew a playable card — play it or pass.")
    if first:
        lines.append(f"\nTap 🃏 Play a card, or type <code>@{config.BOT_USERNAME} uno</code>.")
    gid = game["game_id"]
    row2 = [InlineKeyboardButton("🎴 Draw", callback_data=f"UNOD:{gid}")]
    if game.get("drawn"):
        row2 = [InlineKeyboardButton("⏭ Pass", callback_data=f"UNOP:{gid}")]
    row2.append(InlineKeyboardButton("👀 My hand", callback_data=f"UNOH:{gid}"))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 Play a card", switch_inline_query_current_chat="uno")],
        row2,
        [InlineKeyboardButton("🛑 End game", callback_data=f"UNOE:{gid}")],
    ])
    return "\n".join(lines), kb


async def _post_status(game: dict, repost: bool, first: bool = False) -> None:
    text, kb = _status_view(game, first)
    chat_id, old = game["chat_id"], game.get("msg_id")
    if not repost and old:
        try:
            await app.edit_message_text(chat_id, old, text, reply_markup=kb)
            _arm(game)
            return
        except Exception as e:
            if "MESSAGE_NOT_MODIFIED" in str(e).upper():
                _arm(game)
                return
    if old:
        try:
            await app.delete_messages(chat_id, old)
        except Exception:
            pass
    sent = await app.send_message(chat_id, text, reply_markup=kb)
    game["msg_id"] = sent.id
    await _save(game)
    _arm(game)


def _arm(game: dict) -> None:
    """Start the idle timer for the current turn."""
    t = asyncio.create_task(_watch(game["game_id"], game["seq"]))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _watch(gid: str, seq: int) -> None:
    await asyncio.sleep(config.UNO_TURN_TIMEOUT)
    async with _lock(gid):
        game = await UNOC.find_one({"game_id": gid})
        if not game or game.get("status") != "active" or game.get("seq") != seq:
            return
        uid = eng.current(game)
        strikes = int(game["afk"].get(str(uid), 0)) + 1
        game["afk"][str(uid)] = strikes
        name = _nm(game, uid)
        if strikes >= 2:
            eng.remove_player(game, uid)
            game["log"] = f"{name} was removed for being idle."
            if len(game["players"]) < 2:
                game["status"] = "ended"
                await _save(game)
                try:
                    await app.delete_messages(game["chat_id"], game.get("msg_id"))
                except Exception:
                    pass
                return await app.send_message(game["chat_id"], f"🃏 UNO ended — {name} was idle and not enough players are left. No reward.")
        else:
            eng.force_skip(game, uid)
            game["log"] = f"{name} was idle: drew a card and was skipped."
        await _save(game)
        await _post_status(game, repost=True)


# ───────────────────────── buttons: draw / pass / hand / end ─────────────────────────
@app.on_callback_query(filters.regex(r"^UNO[DPHE]:"))
async def uno_action_cb(_, cb: CallbackQuery):
    act, gid = cb.data[3], cb.data.split(":", 1)[1]
    uid = int(cb.from_user.id)
    async with _lock(gid):
        game = await UNOC.find_one({"game_id": gid})
        if not game or game.get("status") != "active":
            return await cb.answer("This game is over.", show_alert=True)
        if act == "E":
            if uid != game["host"] and not await _is_admin(game["chat_id"], uid):
                return await cb.answer("Only the host or an admin can end the game.", show_alert=True)
            game["status"] = "ended"
            await _save(game)
            await cb.edit_message_text("🃏 UNO game ended by the host/admin. No reward.")
            return await cb.answer()
        if uid not in game["players"]:
            return await cb.answer("You're not playing in this game.", show_alert=True)
        if act == "H":
            hand = game["hands"].get(str(uid), [])
            txt = f"Top: {eng.short(game['top'])}\nYour hand ({len(hand)}): " + " ".join(eng.short(c) for c in sorted(hand))
            return await cb.answer(txt[:195], show_alert=True)
        name = _nm(game, uid)
        if act == "D":
            res = eng.draw(game, uid)
            if not res["ok"]:
                return await cb.answer(res["error"], show_alert=True)
            game["afk"][str(uid)] = 0
            game["log"] = f"{name} " + res["events"][0]
            await _save(game)
            if res.get("card"):
                await cb.answer(f"You drew {eng.label(res['card'])}", show_alert=True)
            else:
                await cb.answer()
            return await _post_status(game, repost=res.get("passed", False))
        res = eng.pass_turn(game, uid)  # act == "P"
        if not res["ok"]:
            return await cb.answer(res["error"], show_alert=True)
        game["afk"][str(uid)] = 0
        game["log"] = f"{name} passes."
        await _save(game)
        await cb.answer()
        await _post_status(game, repost=True)


@app.on_message(filters.command("unoend") & filters.group, group=31)
async def unoend_cmd(_, m: Message):
    game = await UNOC.find_one({"chat_id": m.chat.id, "status": {"$in": ["lobby", "active"]}})
    if not game:
        return await m.reply_text("🃏 No UNO game is running here.")
    if m.from_user.id != game["host"] and not await _is_admin(m.chat.id, m.from_user.id):
        return await m.reply_text("🔒 Only the host or an admin can end the game.")
    await UNOC.update_one({"game_id": game["game_id"]}, {"$set": {"status": "ended"}})
    try:
        if game.get("msg_id"):
            await app.delete_messages(m.chat.id, game["msg_id"])
    except Exception:
        pass
    await m.reply_text("🃏 UNO game ended. No reward.")


# ───────────────────────── inline picker ─────────────────────────
def _sticker_ok() -> bool:
    return InlineQueryResultCachedSticker is not None


def _article(rid: str, title: str, desc: str, body: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(id=rid, title=title, description=desc, input_message_content=InputTextMessageContent(body))


async def uno_inline(query) -> bool:
    if query.query.strip().lower() != "uno":
        return False
    uid = int(query.from_user.id)
    game = await UNOC.find_one({"status": "active", "players": uid}, sort=[("updated_at", -1)])
    if not game:
        r = _article("uno|n", "🃏 No UNO game for you", "Start one in a group with /uno", "🃏 Start a UNO game in the group with /uno")
        await query.answer([r], cache_time=0, is_personal=True)
        return True
    gid, hand = game["game_id"], game["hands"].get(str(uid), [])
    hand_txt = " ".join(eng.short(c) for c in sorted(hand)) or "—"
    me = _nm(game, uid)
    if eng.current(game) != uid:
        r = _article(f"uno|i|{gid}", f"⏳ Waiting for {_nm(game, eng.current(game))}", f"Your hand: {hand_txt}", f"👀 {me} is checking their cards…")
        await query.answer([r], cache_time=0, is_personal=True)
        return True

    results, playable = [], eng.playable(game, uid)
    stickers = {}
    if _sticker_ok() and playable:
        async for d in STK.find({"card": {"$in": list(set(playable))}}):
            stickers[d["card"]] = d["file_id"]
    seen = set()
    for card in playable:
        if card in seen:
            continue
        seen.add(card)
        if card.startswith("wild"):  # a sticker can't carry the colour choice, so wilds are always text entries
            for col in eng.COLORS:
                title = eng.label(card, col)
                results.append(_article(f"uno|p|{gid}|{card}|{col}", title, "Tap to play this card and choose this colour", f"🃏 {me} plays {title}"))
            continue
        rid = f"uno|p|{gid}|{card}|-"
        if card in stickers:
            try:
                results.append(InlineQueryResultCachedSticker(sticker_file_id=stickers[card], id=rid))
                continue
            except Exception:
                pass
        title = eng.label(card)
        results.append(_article(rid, title, "Tap to play this card", f"🃏 {me} plays {title}"))
    if game.get("drawn"):
        results.append(_article(f"uno|s|{gid}", "⏭ Pass", "Keep the card you drew and end your turn", f"⏭ {me} passes"))
    else:
        results.append(_article(f"uno|d|{gid}", "🎴 Draw a card", f"Your hand: {hand_txt}", f"🎴 {me} draws a card"))
    await query.answer(results[:50], cache_time=0, is_personal=True)
    return True


def _parse_rid(rid: str):
    p = rid.split("|")
    return p[1], p[2], (p[3] if len(p) > 3 else None), (p[4] if len(p) > 4 else None)


@app.on_chosen_inline_result()
async def uno_chosen(_, chosen):
    rid = chosen.result_id or ""
    if not rid.startswith("uno|") or rid.count("|") < 2:
        return
    kind, gid, card, col = _parse_rid(rid)
    uid = int(chosen.from_user.id)
    if kind in ("n", "i"):
        return
    async with _lock(gid):
        game = await UNOC.find_one({"game_id": gid})
        if not game or game.get("status") != "active" or uid not in game["players"]:
            return
        chat_id, name = game["chat_id"], _nm(game, uid)
        if kind == "p":
            res = eng.play(game, uid, card, None if col == "-" else col)
        elif kind == "d":
            res = eng.draw(game, uid)
        elif kind == "s":
            res = eng.pass_turn(game, uid)
        else:
            return
        if not res["ok"]:
            return await app.send_message(chat_id, f"⚠️ {_mn(game, uid)}: {res['error']}")
        game["afk"][str(uid)] = 0
        game["log"] = f"{name} " + "; ".join(res["events"])
        if kind == "p" and res.get("victim"):
            game["log"] += f" ({_nm(game, res['victim'])})"
        if res.get("winner"):
            game["status"] = "finished"
            await _save(game)
            await credit(chat_id, uid, config.UNO_WIN_REWARD, _name(chosen.from_user))
            try:
                if game.get("msg_id"):
                    await app.delete_messages(chat_id, game["msg_id"])
            except Exception:
                pass
            rest = ", ".join(f"{_nm(game, p)} ({len(game['hands'].get(str(p), []))})" for p in game["players"] if p != uid)
            return await app.send_message(chat_id, f"🏆 <b>{_mn(game, uid)}</b> wins UNO!\n💰 Reward: <b>{money(config.UNO_WIN_REWARD)}</b>\n\nCards left: {rest}")
        await _save(game)
        await _post_status(game, repost=(kind != "d" or res.get("passed", False)))


# ───────────────────────── optional: real UNO stickers ─────────────────────────
def _parse_card(tokens: list[str]):
    t = " ".join(tokens).lower().replace("+", "draw").replace("wild4", "wild draw4").strip()
    t = t.replace("wilddraw4", "wild draw4").replace("draw 4", "draw4").replace("draw 2", "draw2")
    parts = t.split()
    if parts[:1] == ["wild"]:
        return "wild:draw4" if parts[1:2] == ["draw4"] else "wild:*"
    if len(parts) == 2 and parts[0] in eng.COLORS and (parts[1].isdigit() or parts[1] in ("skip", "reverse", "draw2")):
        return f"{parts[0]}:{parts[1]}"
    return None


@app.on_message(filters.command("unomap") & filters.user(config.OWNER_ID), group=31)
async def unomap_cmd(_, m: Message):
    args = m.command[1:]
    if args[:1] == ["status"]:
        n = await STK.count_documents({})
        return await m.reply_text(f"🃏 {n}/{len(set(eng.new_deck()))} card types have a sticker. "
                                  f"{'Stickers are used in the picker.' if _sticker_ok() else 'Your Pyrogram build has no cached-sticker results, so text cards are shown.'}")
    card = _parse_card(args) if args else None
    rp = m.reply_to_message
    if not card or not rp or not rp.sticker:
        return await m.reply_text("Reply to a sticker with e.g. <code>/unomap red 5</code>, <code>/unomap blue skip</code>, "
                                  "<code>/unomap green +2</code>, <code>/unomap wild</code>, <code>/unomap wild4</code>.\n"
                                  "Check progress with <code>/unomap status</code>.")
    await STK.update_one({"card": card}, {"$set": {"card": card, "file_id": rp.sticker.file_id}}, upsert=True)
    await m.reply_text(f"✅ {eng.label(card)} → sticker saved.")
