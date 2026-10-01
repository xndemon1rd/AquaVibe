"""Chess played entirely inside Telegram: the board is an inline keyboard. No Mini App needed.

Flow: /chess @user  ->  they tap Accept  ->  a board message appears.
Tap one of your pieces, then a highlighted square. Resign / draw / time-claim buttons sit under the board.
Group ELO is updated when the game ends. Inline games (@bot chess) are unrated.
"""
from __future__ import annotations

import html
import time
import uuid

import chess
from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

import config
from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app
from AquaVibe.plugins.social.ai_social import _enabled, _mention, _name
from AquaVibe.utils.chess_rating import DEFAULT_RATING, apply_result, get_rating

CH = mongodb.aqua_chess

CONTROLS = {"blitz": (300, 0, "5+0"), "rapid": (600, 5, "10+5"), "standard": (600, 0, "10+0"), "unlimited": (0, 0, "∞")}
CHALLENGE_TTL = 600
GLYPH = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}
PROMO = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}
PROMO_GLYPH = {"q": "♕", "r": "♖", "b": "♗", "n": "♘"}
WHY = {
    "CHECKMATE": "Checkmate",
    "STALEMATE": "Stalemate",
    "INSUFFICIENT_MATERIAL": "Insufficient material",
    "SEVENTYFIVE_MOVES": "75-move rule",
    "FIVEFOLD_REPETITION": "Fivefold repetition",
    "FIFTY_MOVES": "50-move rule",
    "THREEFOLD_REPETITION": "Threefold repetition",
}


# ───────────────────────── helpers ─────────────────────────
def _board_of(game: dict) -> chess.Board:
    fen = game.get("fen")
    return chess.Board() if fen in (None, "startpos") else chess.Board(fen)


def _clocks(game: dict, board: chess.Board) -> tuple[float, float]:
    """Remaining seconds for (white, black) right now."""
    w, b = float(game.get("white_clock", 0)), float(game.get("black_clock", 0))
    if game.get("status") == "active" and game.get("base_seconds") and game.get("turn_started_at"):
        spent = max(0.0, time.time() - float(game["turn_started_at"]))
        if board.turn:
            w = max(0.0, w - spent)
        else:
            b = max(0.0, b - spent)
    return w, b


def _fmt_clock(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def _side_name(game: dict, white: bool) -> str:
    return html.escape(game.get("white_name" if white else "black_name") or "Player")


def _text_board(board: chess.Board) -> str:
    rows = []
    for rank in range(7, -1, -1):
        cells = []
        for file in range(8):
            p = board.piece_at(chess.square(file, rank))
            cells.append(GLYPH[p.symbol()] if p else ("·" if (rank + file) % 2 == 0 else " "))
        rows.append(f"{rank + 1} " + " ".join(cells))
    rows.append("  a b c d e f g h")
    return "<pre>" + "\n".join(rows) + "</pre>"


def _header(game: dict, board: chess.Board) -> str:
    w, b = _clocks(game, board)
    timed = bool(game.get("base_seconds"))
    wl = f"  ⏱ {_fmt_clock(w)}" if timed else ""
    bl = f"  ⏱ {_fmt_clock(b)}" if timed else ""
    lines = [
        "♟️ <b>Chess</b> · " + html.escape(game.get("time_control", "10+0")) + (" · unrated" if not game.get("chat_id") else ""),
        f"⚪ {_side_name(game, True)}{wl}",
        f"⚫ {_side_name(game, False)}{bl}",
    ]
    if game.get("last"):
        lines.append(f"Last move: <code>{html.escape(game['last'])}</code>")
    return "\n".join(lines)


def _grid(game: dict, board: chess.Board) -> list[list[InlineKeyboardButton]]:
    gid = game["game_id"]
    sel = game.get("sel")
    targets: dict[int, bool] = {}  # square -> is_capture
    if sel is not None:
        for mv in board.legal_moves:
            if mv.from_square == sel:
                targets[mv.to_square] = board.is_capture(mv)
    rows = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            glyph = GLYPH[piece.symbol()] if piece else None
            if sq == sel:
                label = f"[{glyph}]"
            elif sq in targets:
                label = f"×{glyph}" if piece else "🟢"
            elif glyph:
                label = glyph
            else:
                label = "⬜" if (rank + file) % 2 else "⬛"
            row.append(InlineKeyboardButton(label, callback_data=f"CHS:{gid}:{sq}"))
        rows.append(row)
    return rows


def _controls(game: dict) -> list[list[InlineKeyboardButton]]:
    gid = game["game_id"]
    if game.get("promo"):
        row = [InlineKeyboardButton(PROMO_GLYPH[k], callback_data=f"CHP:{gid}:{k}") for k in "qrbn"]
        row.append(InlineKeyboardButton("✖️", callback_data=f"CHP:{gid}:x"))
        return [row]
    if game.get("resign_ask"):
        return [[InlineKeyboardButton("✅ Yes, resign", callback_data=f"CHR:{gid}:y"),
                 InlineKeyboardButton("↩️ Cancel", callback_data=f"CHR:{gid}:n")]]
    if game.get("draw_offer"):
        return [[InlineKeyboardButton("🤝 Accept draw", callback_data=f"CHD:{gid}:a"),
                 InlineKeyboardButton("✖️ Decline", callback_data=f"CHD:{gid}:d")]]
    row = [InlineKeyboardButton("🏳️ Resign", callback_data=f"CHR:{gid}:a"),
           InlineKeyboardButton("🤝 Draw", callback_data=f"CHD:{gid}:o")]
    if game.get("base_seconds"):
        row.append(InlineKeyboardButton("⏱ Time", callback_data=f"CHT:{gid}"))
    return [row]


def _render(game: dict) -> tuple[str, InlineKeyboardMarkup | None]:
    board = _board_of(game)
    if game.get("status") != "active":
        text = _header(game, board) + "\n\n" + _text_board(board) + "\n" + game.get("result_text", "Game over.")
        return text, None
    turn_white = board.turn
    who = _side_name(game, turn_white)
    text = _header(game, board) + f"\n\n{'⚪' if turn_white else '⚫'} <b>{who}</b> to move" + (" — <b>check!</b>" if board.is_check() else "")
    if game.get("draw_offer"):
        offerer = _side_name(game, int(game["draw_offer"]) == int(game["white"]))
        text += f"\n🤝 {offerer} offers a draw."
    if game.get("promo"):
        text += "\n👑 Choose the promotion piece."
    return text, InlineKeyboardMarkup(_grid(game, board) + _controls(game))


async def _show(cb: CallbackQuery, game: dict) -> None:
    text, markup = _render(game)
    try:
        await cb.edit_message_text(text, reply_markup=markup)
    except Exception as e:  # "message is not modified" etc. is harmless
        if "MESSAGE_NOT_MODIFIED" not in str(e).upper():
            raise


async def _finish(cb: CallbackQuery, game: dict, winner: int | None, reason: str) -> None:
    board = _board_of(game)
    change = await apply_result(game.get("chat_id", 0), game["white"], game["black"], winner)
    if winner is None:
        line = f"🤝 <b>Draw</b> — {html.escape(reason)}"
    else:
        wn = _side_name(game, int(winner) == int(game["white"]))
        line = f"🏆 <b>{wn} wins</b> — {html.escape(reason)}"
    if change:
        (wa, wb), (ba, bb) = change["white"], change["black"]
        line += f"\n📈 ELO: ⚪ {wa}→<b>{wb}</b> · ⚫ {ba}→<b>{bb}</b>"
    game.update({"status": "finished", "winner": winner, "result_text": line})
    await CH.update_one(
        {"type": "game", "game_id": game["game_id"]},
        {"$set": {"status": "finished", "winner": winner, "result_text": line, "updated_at": time.time(),
                  "fen": board.fen(), "promo": None, "sel": None, "draw_offer": None, "resign_ask": None}},
    )
    await _show(cb, game)


async def _load_active(cb: CallbackQuery, gid: str) -> dict | None:
    game = await CH.find_one({"type": "game", "game_id": gid})
    if not game or game.get("status") != "active":
        await cb.answer("This game is over.", show_alert=True)
        return None
    return game


def _player_side(game: dict, uid: int):
    if int(uid) == int(game["white"]):
        return True
    if int(uid) == int(game["black"]):
        return False
    return None


async def _flag_check(cb: CallbackQuery, game: dict) -> bool:
    """If the side to move has run out of time, end the game. Returns True if it ended."""
    if not game.get("base_seconds"):
        return False
    board = _board_of(game)
    w, b = _clocks(game, board)
    if board.turn and w <= 0:
        await _finish(cb, game, game["black"], "White ran out of time")
        return True
    if not board.turn and b <= 0:
        await _finish(cb, game, game["white"], "Black ran out of time")
        return True
    return False


# ───────────────────────── challenge ─────────────────────────
async def _busy(chat_id: int, uid: int) -> bool:
    return bool(await CH.find_one({"type": "game", "status": "active", "chat_id": int(chat_id),
                                   "$or": [{"white": int(uid)}, {"black": int(uid)}]}))


@app.on_message(filters.command("chess") & filters.group, group=31)
async def chess_cmd(_, m: Message):
    if not await _enabled(m.chat.id, "games"):
        return
    args = list(m.command[1:])
    mode = "standard"
    if args and args[0].lower() in {"blitz", "rapid", "unlimited", "standard"}:
        mode = args.pop(0).lower()
    target = None
    if m.reply_to_message and m.reply_to_message.from_user and not m.reply_to_message.from_user.is_bot:
        target = m.reply_to_message.from_user
    elif args and args[0].startswith("@"):
        try:
            target = await app.get_users(args[0])
        except Exception:
            return await m.reply_text("❌ User not found.")
    if target is not None and (target.id == m.from_user.id or target.is_bot):
        return await m.reply_text("Pick a real opponent 😄")
    if await _busy(m.chat.id, m.from_user.id):
        return await m.reply_text("♟️ You already have a game running here. Finish or resign it first.")
    base, inc, tc = CONTROLS[mode]
    gid = uuid.uuid4().hex[:12]
    await CH.insert_one({
        "type": "challenge", "game_id": gid, "chat_id": m.chat.id, "challenger": m.from_user.id,
        "challenger_name": _name(m.from_user), "opponent": target.id if target else None,
        "opponent_name": _name(target) if target else None, "status": "pending", "mode": mode,
        "time_control": tc, "created_at": time.time(),
    })
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Accept", callback_data=f"CHACC:{gid}"),
                                InlineKeyboardButton("❌ Reject" if target else "🚫 Cancel", callback_data=f"CHREJ:{gid}")]])
    vs = _mention(target) if target else "<b>anyone</b>"
    await m.reply_text(f"♟️ {_mention(m.from_user)} challenged {vs} to chess!\n\n⏱️ <b>{tc}</b> · {mode.title()}\n"
                       f"<i>Played right here in the chat — no Mini App.</i>", reply_markup=kb)


@app.on_callback_query(filters.regex(r"^CH(ACC|REJ):"))
async def chess_challenge_cb(_, cb: CallbackQuery):
    gid = cb.data.split(":", 1)[1]
    doc = await CH.find_one({"type": "challenge", "game_id": gid, "status": "pending"})
    if not doc:
        return await cb.answer("Challenge expired.", show_alert=True)
    if time.time() - float(doc.get("created_at", 0)) > CHALLENGE_TTL:
        await CH.update_one({"game_id": gid, "type": "challenge"}, {"$set": {"status": "expired"}})
        return await cb.edit_message_text("♟️ Challenge expired.")
    uid, challenger, opponent = int(cb.from_user.id), int(doc["challenger"]), doc.get("opponent")
    if cb.data.startswith("CHREJ"):
        if uid not in {challenger, int(opponent or 0)}:
            return await cb.answer("Only the challenger or the challenged player can do that.", show_alert=True)
        await CH.update_one({"game_id": gid, "type": "challenge"}, {"$set": {"status": "rejected"}})
        return await cb.edit_message_text("♟️ Challenge cancelled." if uid == challenger else "♟️ Challenge rejected.")
    if uid == challenger:
        return await cb.answer("Waiting for your opponent to accept.", show_alert=True)
    if opponent and uid != int(opponent):
        return await cb.answer("Only the challenged player can accept.", show_alert=True)
    if await _busy(doc["chat_id"], uid) or await _busy(doc["chat_id"], challenger):
        return await cb.answer("One of you already has a game running here.", show_alert=True)
    claimed = await CH.update_one({"game_id": gid, "type": "challenge", "status": "pending"}, {"$set": {"status": "accepted"}})
    if claimed.modified_count != 1:
        return await cb.answer("Challenge already taken.", show_alert=True)
    base, inc, tc = CONTROLS.get(doc.get("mode", "standard"), CONTROLS["standard"])
    game = {
        "type": "game", "game_id": uuid.uuid4().hex[:16], "chat_id": doc["chat_id"], "white": challenger, "black": uid,
        "white_name": doc.get("challenger_name") or "Player", "black_name": _name(cb.from_user), "status": "active",
        "fen": "startpos", "moves": [], "mode": doc.get("mode", "standard"), "time_control": tc, "base_seconds": base,
        "increment": inc, "white_clock": base, "black_clock": base, "turn_started_at": time.time(),
        "created_at": time.time(), "sel": None, "promo": None, "draw_offer": None, "resign_ask": None, "last": "",
    }
    await CH.insert_one(dict(game))
    await _show(cb, game)
    await cb.answer("Game on! ♟️")


# ───────────────────────── moves ─────────────────────────
@app.on_callback_query(filters.regex(r"^CHS:"))
async def chess_square_cb(_, cb: CallbackQuery):
    _, gid, sq_s = cb.data.split(":")
    sq = int(sq_s)
    game = await _load_active(cb, gid)
    if not game:
        return
    side = _player_side(game, cb.from_user.id)
    if side is None:
        return await cb.answer("👀 You're watching this game.", show_alert=True)
    board = _board_of(game)
    if side != board.turn:
        return await cb.answer("⏳ Not your turn.", show_alert=True)
    if await _flag_check(cb, game):
        return await cb.answer("⏱ Time is up!")
    if game.get("promo"):
        return await cb.answer("Choose the promotion piece first.", show_alert=True)

    sel = game.get("sel")
    piece = board.piece_at(sq)
    own = piece is not None and piece.color == board.turn

    if sel is None or (own and sq != sel):
        if not own:
            return await cb.answer("Tap one of your own pieces first.")
        if not any(mv.from_square == sq for mv in board.legal_moves):
            return await cb.answer("That piece has no legal moves.")
        game["sel"] = sq
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"sel": sq}})
        await _show(cb, game)
        return await cb.answer()
    if sq == sel:
        game["sel"] = None
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"sel": None}})
        await _show(cb, game)
        return await cb.answer()

    candidates = [mv for mv in board.legal_moves if mv.from_square == sel and mv.to_square == sq]
    if not candidates:
        return await cb.answer("❌ Illegal move.")
    if len(candidates) > 1 or candidates[0].promotion:  # pawn reaching the last rank
        game["promo"] = {"from": sel, "to": sq}
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"promo": game["promo"]}})
        await _show(cb, game)
        return await cb.answer()
    await _apply_move(cb, game, board, candidates[0])


@app.on_callback_query(filters.regex(r"^CHP:"))
async def chess_promo_cb(_, cb: CallbackQuery):
    _, gid, k = cb.data.split(":")
    game = await _load_active(cb, gid)
    if not game or not game.get("promo"):
        return await cb.answer()
    board = _board_of(game)
    if _player_side(game, cb.from_user.id) != board.turn:
        return await cb.answer("⏳ Not your turn.", show_alert=True)
    if k == "x":
        game["promo"] = game["sel"] = None
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"promo": None, "sel": None}})
        await _show(cb, game)
        return await cb.answer()
    mv = chess.Move(game["promo"]["from"], game["promo"]["to"], promotion=PROMO[k])
    if mv not in board.legal_moves:
        return await cb.answer("❌ Illegal move.")
    await _apply_move(cb, game, board, mv)


async def _apply_move(cb: CallbackQuery, game: dict, board: chess.Board, mv: chess.Move) -> None:
    gid, now = game["game_id"], time.time()
    prefix = f"{board.fullmove_number}{'.' if board.turn else '...'} "
    san = board.san(mv)
    mover_white = board.turn
    w, b = _clocks(game, board)
    base, inc = float(game.get("base_seconds", 0)), float(game.get("increment", 0))
    if base:
        if mover_white:
            w += inc
        else:
            b += inc
    n_moves = len(game.get("moves", []))
    board.push(mv)
    fen = board.fen()
    res = await CH.update_one(
        {"type": "game", "game_id": gid, "status": "active", "moves": {"$size": n_moves}},
        {"$set": {"fen": fen, "white_clock": w, "black_clock": b, "turn_started_at": now, "updated_at": now,
                  "sel": None, "promo": None, "draw_offer": None, "resign_ask": None, "last": prefix + san},
         "$push": {"moves": mv.uci()}},
    )
    if res.modified_count != 1:
        return await cb.answer("Board changed, try again.", show_alert=True)
    game.update({"fen": fen, "white_clock": w, "black_clock": b, "turn_started_at": now, "sel": None, "promo": None,
                 "draw_offer": None, "resign_ask": None, "last": prefix + san, "moves": game.get("moves", []) + [mv.uci()]})
    outcome = board.outcome()
    if outcome is not None:
        winner = None
        if outcome.winner is True:
            winner = game["white"]
        elif outcome.winner is False:
            winner = game["black"]
        reason = WHY.get(outcome.termination.name, outcome.termination.name.replace("_", " ").title())
        return await _finish(cb, game, winner, reason)
    await _show(cb, game)
    await cb.answer()


# ───────────────────────── resign / draw / time ─────────────────────────
@app.on_callback_query(filters.regex(r"^CHR:"))
async def chess_resign_cb(_, cb: CallbackQuery):
    _, gid, act = cb.data.split(":")
    game = await _load_active(cb, gid)
    if not game:
        return
    side = _player_side(game, cb.from_user.id)
    if side is None:
        return await cb.answer("👀 You're watching this game.", show_alert=True)
    if act == "a":
        game["resign_ask"] = int(cb.from_user.id)
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"resign_ask": game["resign_ask"]}})
        await _show(cb, game)
        return await cb.answer("Tap “Yes, resign” to confirm.")
    if int(game.get("resign_ask") or 0) != int(cb.from_user.id):
        return await cb.answer("Only the player who asked can answer.", show_alert=True)
    if act == "n":
        game["resign_ask"] = None
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"resign_ask": None}})
        await _show(cb, game)
        return await cb.answer()
    winner = game["black"] if side else game["white"]
    await _finish(cb, game, winner, f"{'White' if side else 'Black'} resigned")
    await cb.answer()


@app.on_callback_query(filters.regex(r"^CHD:"))
async def chess_draw_cb(_, cb: CallbackQuery):
    _, gid, act = cb.data.split(":")
    game = await _load_active(cb, gid)
    if not game:
        return
    uid = int(cb.from_user.id)
    if _player_side(game, uid) is None:
        return await cb.answer("👀 You're watching this game.", show_alert=True)
    offer = game.get("draw_offer")
    if act == "o":
        game["draw_offer"] = uid
        await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"draw_offer": uid}})
        await _show(cb, game)
        return await cb.answer("Draw offered.")
    if not offer:
        return await cb.answer("No draw offer is pending.")
    if act == "a":
        if int(offer) == uid:
            return await cb.answer("Waiting for your opponent.", show_alert=True)
        await _finish(cb, game, None, "agreed draw")
        return await cb.answer()
    game["draw_offer"] = None  # decline / withdraw
    await CH.update_one({"game_id": gid, "type": "game"}, {"$set": {"draw_offer": None}})
    await _show(cb, game)
    await cb.answer("Draw declined.")


@app.on_callback_query(filters.regex(r"^CHT:"))
async def chess_time_cb(_, cb: CallbackQuery):
    gid = cb.data.split(":", 1)[1]
    game = await _load_active(cb, gid)
    if not game:
        return
    if _player_side(game, cb.from_user.id) is None:
        return await cb.answer("👀 You're watching this game.", show_alert=True)
    if await _flag_check(cb, game):
        return await cb.answer("Time's up!")
    board = _board_of(game)
    w, b = _clocks(game, board)
    await _show(cb, game)  # refresh clocks in the header
    await cb.answer(f"⚪ {_fmt_clock(w)}  ⚫ {_fmt_clock(b)}", show_alert=True)


# ───────────────────────── ratings ─────────────────────────
@app.on_message(filters.command("elo") & filters.group, group=31)
async def elo_cmd(_, m: Message):
    uid = m.reply_to_message.from_user.id if m.reply_to_message and m.reply_to_message.from_user else m.from_user.id
    d = await get_rating(m.chat.id, uid)
    try:
        who = _mention(await app.get_users(uid))
    except Exception:
        who = "Player"
    await m.reply_text(f"♟️ {who}\nELO: <b>{int(d.get('rating', DEFAULT_RATING))}</b>\n"
                       f"Games: {int(d.get('games', 0))} · W {int(d.get('wins', 0))} · D {int(d.get('draws', 0))} · L {int(d.get('losses', 0))}")


@app.on_message(filters.command(["chesstop", "chessleaderboard"]) & filters.group, group=31)
async def chess_top(_, m: Message):
    rows, i = [], 1
    async for d in CH.find({"type": "rating", "chat_id": m.chat.id}).sort("rating", -1).limit(10):
        try:
            nm = html.escape(_name(await app.get_users(int(d["user_id"]))))
        except Exception:
            nm = "Player"
        rows.append(f"{i}. <a href=\"tg://user?id={d['user_id']}\">{nm}</a> — <b>{int(d.get('rating', DEFAULT_RATING))}</b>")
        i += 1
    await m.reply_text("♟️ <b>Chess ELO — this group</b>\n\n" + "\n".join(rows) if rows else "No chess ratings yet.")


# ───────────────────────── inline quick-challenge (unrated) ─────────────────────────
async def chess_inline(query) -> bool:
    parts = query.query.strip().lower().split()
    if not parts or parts[0] != "chess" or len(parts) > 2:
        return False
    mode = parts[1] if len(parts) == 2 else "standard"
    if mode not in CONTROLS:
        return False
    tc = CONTROLS[mode][2]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Accept", callback_data=f"CHO:{query.from_user.id}:{mode}")]])
    text = f"♟️ {_mention(query.from_user)} wants to play chess!\n⏱ <b>{tc}</b> · {mode.title()} · unrated\nFirst person to tap Accept plays."
    r = InlineQueryResultArticle(id=f"chess-{mode}-{uuid.uuid4().hex[:8]}", title=f"♟️ Chess · {mode.title()} ({tc})",
                                 description="Open challenge — played in the chat, no Mini App",
                                 input_message_content=InputTextMessageContent(text), reply_markup=kb)
    await query.answer([r], cache_time=0, is_personal=True)
    return True


@app.on_callback_query(filters.regex(r"^CHO:"))
async def chess_open_cb(_, cb: CallbackQuery):
    _, creator, mode = cb.data.split(":")
    if int(creator) == int(cb.from_user.id):
        return await cb.answer("Waiting for an opponent.", show_alert=True)
    if mode not in CONTROLS:
        return await cb.answer("Invalid challenge.", show_alert=True)
    base, inc, tc = CONTROLS[mode]
    try:
        creator_name = _name(await app.get_users(int(creator)))
    except Exception:
        creator_name = "Player"
    game = {
        "type": "game", "game_id": uuid.uuid4().hex[:16], "chat_id": 0, "white": int(creator), "black": int(cb.from_user.id),
        "white_name": creator_name, "black_name": _name(cb.from_user), "status": "active", "fen": "startpos", "moves": [],
        "mode": mode, "time_control": tc, "base_seconds": base, "increment": inc, "white_clock": base, "black_clock": base,
        "turn_started_at": time.time(), "created_at": time.time(), "sel": None, "promo": None, "draw_offer": None,
        "resign_ask": None, "last": "",
    }
    await CH.insert_one(dict(game))
    await _show(cb, game)
    await cb.answer("Game on! ♟️")
