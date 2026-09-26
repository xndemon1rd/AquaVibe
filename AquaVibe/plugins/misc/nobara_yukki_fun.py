"""Safe utility/game features inspired by the uploaded music/general bots.

Ports only self-contained, non-privileged ideas: top tracks, reminders,
Telegram polls, RPS and trivia. No eval/shell/dev/broadcast/ban modules.
"""
import asyncio
import html
import random
import re
import time
from collections import defaultdict

import httpx
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from AquaVibe.core.runtime import app
from AquaVibe.utils.database import get_song_history, historydb
from config import BANNED_USERS
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton

# -------------------- /toptracks --------------------
@app.on_message(filters.command(["toptracks", "top"]) & ~BANNED_USERS)
async def toptracks_command(_, message: Message):
    mode = (message.text.split(maxsplit=1)[1].strip().lower() if len(message.text.split(maxsplit=1)) > 1 else "me")
    if mode not in {"me", "global"}:
        mode = "me"
    try:
        if mode == "global":
            rows = await historydb.aggregate([
                {"$match": {"title": {"$exists": True}}},
                {"$group": {"_id": "$title", "plays": {"$sum": 1}, "link": {"$first": "$link"}}},
                {"$sort": {"plays": -1}}, {"$limit": 10},
            ]).to_list(length=10)
        else:
            rows = await get_song_history(message.from_user.id, 50)
            counts = defaultdict(lambda: {"plays": 0, "link": ""})
            for row in rows:
                title = row.get("title") or "Unknown"
                counts[title]["plays"] += 1
                counts[title]["link"] = row.get("link") or ""
            rows = [{"_id": k, **v} for k, v in sorted(counts.items(), key=lambda x: x[1]["plays"], reverse=True)[:10]]
        if not rows:
            return await message.reply_text("🎧 <b>No listening data yet.</b>\nPlay a few tracks and try <code>/toptracks</code> again.")
        title = "🌍 <b>GLOBAL TOP TRACKS</b>" if mode == "global" else "🎧 <b>YOUR TOP TRACKS</b>"
        lines = [title, ""]
        for i, row in enumerate(rows, 1):
            name = html.escape(str(row.get("_id") or "Unknown"))
            lines.append(f"<b>{i:02}.</b> {name}  <code>{row.get('plays', 0)} plays</code>")
        await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await message.reply_text(f"⚠️ Top tracks unavailable: <code>{html.escape(type(exc).__name__)}</code>", parse_mode=ParseMode.HTML)

# -------------------- /remind --------------------
_TIME_RE = re.compile(r"^(\d+)(s|m|h|d)$", re.I)

def _duration(token: str):
    m = _TIME_RE.fullmatch(token.strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    seconds = n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return seconds if 1 <= seconds <= 7 * 86400 else None

@app.on_message(filters.command(["remind", "reminder", "remindme"]) & ~BANNED_USERS)
async def remind_command(_, message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.reply_text("⏰ <b>Usage:</b> <code>/remind 10m Drink water</code>\nUnits: s, m, h, d · max 7 days", parse_mode=ParseMode.HTML)
    seconds = _duration(parts[1])
    if not seconds:
        return await message.reply_text("❌ Invalid duration. Example: <code>30s</code>, <code>10m</code>, <code>2h</code>, <code>1d</code>", parse_mode=ParseMode.HTML)
    note = parts[2].strip()
    if not note:
        return await message.reply_text("❌ Add a reminder message.")
    await message.reply_text(f"⏰ Reminder set for <b>{html.escape(parts[1])}</b>.\n📝 {html.escape(note)}", parse_mode=ParseMode.HTML)
    async def deliver():
        await asyncio.sleep(seconds)
        try:
            await app.send_message(message.chat.id, f"⏰ <b>Reminder!</b>\n📝 {html.escape(note)}", parse_mode=ParseMode.HTML)
        except Exception:
            pass
    asyncio.create_task(deliver())

# -------------------- /poll --------------------
@app.on_message(filters.command(["poll"]) & ~BANNED_USERS)
async def poll_command(_, message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or "|" not in parts[2]:
        return await message.reply_text("📊 <b>Usage:</b> <code>/poll Your question | Option 1 | Option 2 | Option 3</code>", parse_mode=ParseMode.HTML)
    question, *options = [x.strip() for x in parts[2].split("|") if x.strip()]
    if len(options) < 2 or len(options) > 10:
        return await message.reply_text("❌ Provide 2–10 options separated by <code>|</code>.", parse_mode=ParseMode.HTML)
    try:
        await app.send_poll(message.chat.id, question, options, is_anonymous=False)
    except Exception as exc:
        await message.reply_text(f"⚠️ Could not create poll: <code>{html.escape(type(exc).__name__)}</code>", parse_mode=ParseMode.HTML)

# -------------------- /rps --------------------
_RPS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
_RPS_WIN = {("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")}

def _rps_markup():
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("🪨 Rock", callback_data="aqua:rps:rock", aqua_style="primary"),
        InlineKeyboardButton("📄 Paper", callback_data="aqua:rps:paper", aqua_style="success"),
        InlineKeyboardButton("✂️ Scissors", callback_data="aqua:rps:scissors", aqua_style="danger"),
    ]])

@app.on_message(filters.command(["rps", "rockpaperscissors"]) & ~BANNED_USERS)
async def rps_command(_, message: Message):
    sent = await message.reply_text("🤜 <b>ROCK • PAPER • SCISSORS</b>\n\nChoose your move:", parse_mode=ParseMode.HTML, reply_markup=_rps_markup())
    # The callback validates by message id, so different users cannot reuse old sessions.
    try:
        sent._aqua_rps_owner = message.from_user.id
    except Exception:
        pass

@app.on_callback_query(filters.regex(r"^aqua:rps:(rock|paper|scissors)$") & ~BANNED_USERS)
async def rps_callback(_, query):
    choice = query.data.rsplit(":", 1)[-1]
    bot_choice = random.choice(tuple(_RPS))
    if choice == bot_choice:
        result = "🤝 <b>Draw!</b>"
    elif (choice, bot_choice) in _RPS_WIN:
        result = "🎉 <b>You win!</b>"
    else:
        result = "💀 <b>Bot wins!</b>"
    text = f"{result}\n\n👤 You: {_RPS[choice]} {choice.title()}\n🤖 Bot: {_RPS[bot_choice]} {bot_choice.title()}"
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Play Again", callback_data="aqua:rps:again", aqua_style="success")]]))
    await query.answer()

@app.on_callback_query(filters.regex(r"^aqua:rps:again$") & ~BANNED_USERS)
async def rps_again(_, query):
    await query.message.edit_text("🤜 <b>ROCK • PAPER • SCISSORS</b>\n\nChoose your move:", parse_mode=ParseMode.HTML, reply_markup=_rps_markup())
    await query.answer("New game!")

# -------------------- /quiz --------------------
_quiz = {}

@app.on_message(filters.command(["quiz", "trivia"]) & ~BANNED_USERS)
async def quiz_command(_, message: Message):
    loading = await message.reply_text("🧠 Fetching a trivia question…")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            data = (await client.get("https://opentdb.com/api.php", params={"amount": 1, "type": "multiple"})).json()
        item = (data.get("results") or [None])[0]
        if not item:
            raise ValueError("No question returned")
        question = html.unescape(item["question"])
        correct = html.unescape(item["correct_answer"])
        options = [correct] + [html.unescape(x) for x in item.get("incorrect_answers", [])]
        random.shuffle(options)
        token = f"{message.chat.id}:{loading.id}"
        _quiz[token] = (correct, options, time.time())
        rows = [[InlineKeyboardButton(str(opt)[:50], callback_data=f"aqua:quiz:{loading.id}:{i}", aqua_style="primary")] for i, opt in enumerate(options)]
        # Store answer by index after shuffle; style is decorative only.
        await loading.edit_text(f"🧠 <b>QUIZ TIME</b>\n\n❓ {html.escape(question)}\n\nChoose an answer:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
    except Exception:
        await loading.edit_text("⚠️ Trivia service is unavailable right now. Try again later.")

@app.on_callback_query(filters.regex(r"^aqua:quiz:") & ~BANNED_USERS)
async def quiz_callback(_, query):
    parts = query.data.split(":")
    # callback_data is aqua:quiz:<message_id>:<option_index> (4 parts).
    if len(parts) != 4:
        return await query.answer("Invalid quiz.", show_alert=True)
    try:
        message_id = int(parts[2])
        idx = int(parts[3])
    except (TypeError, ValueError):
        return await query.answer("Invalid quiz.", show_alert=True)
    if not query.message or not query.message.chat:
        return await query.answer("Quiz message is unavailable.", show_alert=True)
    token = f"{query.message.chat.id}:{message_id}"
    item = _quiz.get(token)
    if not item:
        return await query.answer("Quiz expired.", show_alert=True)
    if time.time() - item[2] > 300:
        _quiz.pop(token, None)
        return await query.answer("Quiz expired.", show_alert=True)
    correct, options, _ = item
    if idx < 0 or idx >= len(options):
        return await query.answer("Invalid answer.", show_alert=True)
    # Remove the session only after validating the selected answer.
    _quiz.pop(token, None)
    chosen = options[idx]
    ok = chosen == correct
    await query.message.edit_text(("🎉 <b>Correct!</b>" if ok else f"❌ <b>Wrong!</b>\nCorrect answer: <b>{html.escape(correct)}</b>"), parse_mode=ParseMode.HTML)
    await query.answer("Correct!" if ok else "Wrong!")

# -------------------- /wordle --------------------
_WORDS = "apple beach chair dance eagle flame grape house jelly lemon mango ocean pizza queen river sugar tiger water zebra brick cloud earth focus glass horse light mouse noise orbit paper smile table vivid whale alpha brave coral elite frost gamer heart magic noble pearl quest steam train urban valve width blaze delta glide karma lunar maple nerve pulse ridge".split()
_wordle = {}

def _wordle_eval(guess, target):
    result = ["⬜"] * 5
    remaining = list(target)
    for i, ch in enumerate(guess):
        if ch == target[i]:
            result[i] = "🟩"; remaining[i] = ""
    for i, ch in enumerate(guess):
        if result[i] == "⬜" and ch in remaining:
            result[i] = "🟨"; remaining[remaining.index(ch)] = ""
    return " ".join(result)

@app.on_message(filters.command(["wordle", "word"]) & ~BANNED_USERS)
async def wordle_command(_, message: Message):
    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2 or args[1].lower().strip() != "start":
        return await message.reply_text("🎯 <b>Wordle</b>\nUse <code>/wordle start</code>, then send 5-letter guesses.\n🟩 right place · 🟨 wrong place · ⬜ absent", parse_mode=ParseMode.HTML)
    _wordle[message.chat.id] = {"word": random.choice(_WORDS), "attempts": 0}
    await message.reply_text("🎯 <b>WORDLE STARTED</b>\nGuess the 5-letter word in 6 tries.", parse_mode=ParseMode.HTML)

@app.on_message(filters.text & ~filters.command([]) & ~BANNED_USERS, group=-50)
async def wordle_guess(_, message: Message):
    game = _wordle.get(message.chat.id)
    if not game or not message.text or message.text.startswith("/"):
        return
    guess = message.text.strip().lower()
    if guess in {"stop", "end"}:
        _wordle.pop(message.chat.id, None)
        return await message.reply_text(f"🛑 Game ended. Word: <b>{game['word'].upper()}</b>", parse_mode=ParseMode.HTML)
    if len(guess) != 5 or not guess.isalpha():
        return
    game["attempts"] += 1
    board = _wordle_eval(guess, game["word"])
    if guess == game["word"]:
        _wordle.pop(message.chat.id, None)
        return await message.reply_text(f"🎉 <b>Correct!</b>\n{board}\nWord: <b>{guess.upper()}</b>", parse_mode=ParseMode.HTML)
    if game["attempts"] >= 6:
        word = game["word"]
        _wordle.pop(message.chat.id, None)
        return await message.reply_text(f"😔 <b>Game Over</b>\n{board}\nWord: <b>{word.upper()}</b>", parse_mode=ParseMode.HTML)
    await message.reply_text(f"📝 <b>{game['attempts']}/6</b> {board}", parse_mode=ParseMode.HTML)
