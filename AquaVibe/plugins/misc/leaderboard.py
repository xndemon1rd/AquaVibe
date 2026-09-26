"""AquaVibe group XP, levels, reputation, streaks and leaderboards.

Inspired by common Telegram gamification patterns (XP/ranks/reputation), but
implemented natively for AquaVibe's MongoDB/Pyrofork stack.
"""
from __future__ import annotations

import html
import random
from datetime import datetime, timezone

from pyrogram import filters
from pyrogram.types import Message

from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app

DB = mongodb.aquavibe_leaderboard
XP_COOLDOWN = 45


def _level(xp: int) -> int:
    # Gentle early levels, progressively more expensive later.
    level = 1
    need = 100
    total = 0
    while xp >= total + need:
        total += need
        level += 1
        need = int(100 * (level ** 1.25))
    return level


def _rank_title(level: int) -> str:
    titles = (
        (1, "New Traveler"),
        (5, "Aqua Wanderer"),
        (10, "Wave Rider"),
        (20, "Ocean Guardian"),
        (35, "Aqua Knight"),
        (50, "Void Explorer"),
        (75, "Astral Traveler"),
        (100, "AQUA Legend"),
    )
    result = titles[0][1]
    for minimum, title in titles:
        if level >= minimum:
            result = title
    return result


def _mention(user) -> str:
    name = html.escape((user.first_name or "User").strip())
    return f'<a href="tg://user?id={int(user.id)}">{name}</a>'


async def _award(message: Message):
    user = message.from_user
    if not user or user.is_bot:
        return None
    now = datetime.now(timezone.utc)
    doc = await DB.find_one({"chat_id": message.chat.id, "user_id": user.id})
    if doc and (now.timestamp() - float(doc.get("last_xp_at", 0))) < XP_COOLDOWN:
        return doc

    xp = random.randint(5, 12)
    day = now.strftime("%Y-%m-%d")
    last_day = doc.get("last_day") if doc else None
    streak = int(doc.get("streak", 0)) if doc else 0
    if last_day != day:
        if last_day:
            try:
                previous = datetime.strptime(last_day, "%Y-%m-%d").date()
                if (now.date() - previous).days == 1:
                    streak += 1
                else:
                    streak = 1
            except ValueError:
                streak = 1
        else:
            streak = 1

    old_xp = int(doc.get("xp", 0)) if doc else 0
    old_level = _level(old_xp)
    new_xp = old_xp + xp
    new_level = _level(new_xp)
    update = {
        "$set": {
            "xp": new_xp,
            "level": new_level,
            "streak": streak,
            "last_day": day,
            "last_xp_at": now.timestamp(),
            "name": user.first_name or "User",
            "username": user.username,
        },
        "$setOnInsert": {"chat_id": message.chat.id, "user_id": user.id},
    }
    await DB.update_one({"chat_id": message.chat.id, "user_id": user.id}, update, upsert=True)
    return {"xp": new_xp, "level": new_level, "streak": streak, "leveled_up": new_level > old_level}


@app.on_message(filters.group & ~filters.service)
async def leaderboard_xp_tracker(client, message: Message):
    try:
        result = await _award(message)
        if result and result.get("leveled_up"):
            await message.reply_text(
                f"🎉 {_mention(message.from_user)} reached <b>Level {result['level']}</b>!\n"
                f"🏅 {_rank_title(result['level'])} • +{result['xp']} XP total"
            )
    except Exception:
        # Gamification must never break normal group commands/messages.
        return


async def _get_rank(chat_id: int, user_id: int):
    doc = await DB.find_one({"chat_id": chat_id, "user_id": user_id}) or {
        "xp": 0, "level": 1, "streak": 0, "rep": 0,
    }
    higher = await DB.count_documents({"chat_id": chat_id, "xp": {"$gt": int(doc.get("xp", 0))}})
    return doc, higher + 1


@app.on_message(filters.command(["rank", "level", "mylevel"]) & filters.group)
async def rank_command(client, message: Message):
    user = message.from_user
    doc, position = await _get_rank(message.chat.id, user.id)
    xp = int(doc.get("xp", 0))
    level = _level(xp)
    rep = int(doc.get("rep", 0))
    streak = int(doc.get("streak", 0))
    await message.reply_text(
        f"💠 <b>AQUA RANK</b>\n\n"
        f"👤 {_mention(user)}\n"
        f"⭐ Level: <b>{level}</b> — {_rank_title(level)}\n"
        f"✨ XP: <b>{xp}</b>\n"
        f"🏆 Group Rank: <b>#{position}</b>\n"
        f"🔥 Streak: <b>{streak}</b> day(s)\n"
        f"💖 Reputation: <b>{rep}</b>"
    )


@app.on_message(filters.command(["leaderboard", "levels"]) & filters.group)
async def leaderboard_command(client, message: Message):
    cursor = DB.find({"chat_id": message.chat.id}).sort("xp", -1).limit(10)
    rows = []
    position = 0
    async for doc in cursor:
        position += 1
        name = html.escape((doc.get("name") or "User").strip())
        level = _level(int(doc.get("xp", 0)))
        rows.append(
            f"{position}. <a href=\"tg://user?id={int(doc['user_id'])}\">{name}</a> "
            f"— Lv.{level} • {int(doc.get('xp', 0))} XP"
        )
    if not rows:
        return await message.reply_text("🏆 No XP data yet. Start chatting to enter the leaderboard!")
    await message.reply_text("🏆 <b>AQUA LEADERBOARD</b>\n\n" + "\n".join(rows))


@app.on_message(filters.command(["rep", "reputation"]) & filters.group)
async def reputation_command(client, message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target or target.is_bot:
        return await message.reply_text("↩️ Reply to a user's message with <code>/rep</code> to give +1 reputation.")
    if target.id == message.from_user.id:
        return await message.reply_text("❌ You cannot give reputation to yourself.")
    doc = await DB.find_one({"chat_id": message.chat.id, "user_id": target.id}) or {}
    rep = int(doc.get("rep", 0)) + 1
    await DB.update_one(
        {"chat_id": message.chat.id, "user_id": target.id},
        {"$set": {"rep": rep, "name": target.first_name or "User", "username": target.username}, "$setOnInsert": {"xp": 0, "level": 1}},
        upsert=True,
    )
    await message.reply_text(f"💖 {_mention(target)} received <b>+1 reputation</b>! Total: <b>{rep}</b>")
