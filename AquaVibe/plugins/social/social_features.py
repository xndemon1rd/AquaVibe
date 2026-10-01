"""AquaVibe social features: actions, romance, check-ins and group AI controls."""
from __future__ import annotations

import html
import random
import time
import uuid

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

import config
from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app

SOCIAL = mongodb.aqua_social_config
ACTION = mongodb.aqua_social_actions
REL = mongodb.aqua_social_relationships


def _mention(user):
    name = html.escape((getattr(user, "first_name", None) or getattr(user, "username", None) or "User").strip())
    return f'<a href="tg://user?id={int(user.id)}">{name}</a>'


from AquaVibe.utils.economy import credit as _credit, debit as _debit, money as _money, wallet as _wallet_shared


async def _wallet(chat_id, uid):
    return await _wallet_shared(chat_id, uid)


async def _target(message: Message, index: int = 1):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command or []) > index:
        raw = message.command[index]
        if raw.startswith("@"):
            try:
                return await app.get_users(raw)
            except Exception:
                return None
    return None


async def _social_cfg(chat_id):
    return await SOCIAL.find_one({"chat_id": int(chat_id)}) or {"chat_id": int(chat_id), "ai": True, "memory": True, "economy": True, "games": True, "ai_auto": True, "mode": "normal", "checkins": False, "reactions": True}


async def _set_cfg(chat_id, **values):
    await SOCIAL.update_one({"chat_id": int(chat_id)}, {"$set": values}, upsert=True)


async def _admin(message):
    try:
        member = await app.get_chat_member(message.chat.id, message.from_user.id)
        return str(member.status) in {"administrator", "owner", "ChatMemberStatus.ADMINISTRATOR", "ChatMemberStatus.OWNER"}
    except Exception:
        return False


# ---------- Group AI controls ----------
@app.on_message(filters.command("quiet") & filters.group, group=32)
async def quiet_cmd(_, message: Message):
    if not await _admin(message): return await message.reply_text("🔒 Admin only.")
    await _set_cfg(message.chat.id, ai_auto=False, mode="quiet")
    await message.reply_text("🤫 Aqua AI is now quiet in this group. Direct /ai still works.")


@app.on_message(filters.command("chatty") & filters.group, group=32)
async def chatty_cmd(_, message: Message):
    if not await _admin(message): return await message.reply_text("🔒 Admin only.")
    await _set_cfg(message.chat.id, ai=True, ai_auto=True, mode="chatty")
    await message.reply_text("💬 Aqua AI is now chatty in this group.")


@app.on_message(filters.command("groupbot") & filters.group, group=32)
async def groupbot_cmd(_, message: Message):
    if not await _admin(message): return await message.reply_text("🔒 Admin only.")
    if len(message.command or []) < 2 or message.command[1].lower() not in {"on", "off"}:
        cfg = await _social_cfg(message.chat.id)
        return await message.reply_text(f"🤖 Group bot: <b>{'ON' if cfg.get('ai', True) else 'OFF'}</b>\nUse <code>/groupbot on</code> or <code>/groupbot off</code>.")
    enabled = message.command[1].lower() == "on"
    await _set_cfg(message.chat.id, ai=enabled, ai_auto=enabled, mode="normal" if enabled else "quiet")
    await message.reply_text(f"🤖 Group AI {'enabled' if enabled else 'disabled'}.")


@app.on_message(filters.command("groupmode") & filters.group, group=32)
async def groupmode_cmd(_, message: Message):
    if not await _admin(message): return await message.reply_text("🔒 Admin only.")
    mode = message.command[1].lower() if len(message.command or []) > 1 else ""
    if mode not in {"quiet", "normal", "chatty"}:
        cfg = await _social_cfg(message.chat.id)
        return await message.reply_text(f"⚙️ Current mode: <b>{cfg.get('mode','normal')}</b>\nUse <code>/groupmode quiet|normal|chatty</code>.")
    await _set_cfg(message.chat.id, mode=mode, ai_auto=(mode != "quiet"), ai=(mode != "quiet"))
    await message.reply_text(f"⚙️ Group mode → <b>{mode}</b>")


@app.on_message(filters.command("checkins") & filters.group, group=32)
async def checkins_cmd(_, message: Message):
    if not await _admin(message): return await message.reply_text("🔒 Admin only.")
    arg = message.command[1].lower() if len(message.command or []) > 1 else ""
    if arg in {"on", "off"}:
        await _set_cfg(message.chat.id, checkins=(arg == "on"))
    cfg = await _social_cfg(message.chat.id)
    state = "ON" if cfg.get("checkins") else "OFF"
    await message.reply_text(f"📅 Daily check-ins: <b>{state}</b>\nUse <code>/checkins on</code> or <code>/checkins off</code>.")


@app.on_message(filters.command("checkin") & filters.group, group=32)
async def checkin_cmd(_, message: Message):
    cfg = await _social_cfg(message.chat.id)
    if not cfg.get("checkins", False):
        return await message.reply_text("📅 Check-ins are disabled here. Admin can use <code>/checkins on</code>.")
    today = time.strftime("%Y-%m-%d", time.gmtime())
    doc = await ACTION.find_one({"chat_id": message.chat.id, "user_id": message.from_user.id, "type": "checkin"})
    if doc and doc.get("day") == today:
        return await message.reply_text("✅ You already checked in today. See you tomorrow 🫶")
    reward = random.randint(50, 150)
    await _wallet(message.chat.id, message.from_user.id)
    await mongodb.aqua_economy.update_one({"chat_id": message.chat.id, "user_id": message.from_user.id}, {"$inc": {"balance": reward}})
    await ACTION.update_one({"chat_id": message.chat.id, "user_id": message.from_user.id, "type": "checkin"}, {"$set": {"day": today, "updated_at": time.time()}}, upsert=True)
    await message.reply_text(f"📅 {_mention(message.from_user)} checked in!\n🎁 Reward: <b>{_money(reward)}</b>")


@app.on_message(filters.command("reactions") & filters.group, group=32)
async def reactions_cmd(_, message: Message):
    if not await _admin(message): return await message.reply_text("🔒 Admin only.")
    arg = message.command[1].lower() if len(message.command or []) > 1 else ""
    if arg in {"on", "off"}:
        await _set_cfg(message.chat.id, reactions=(arg == "on"))
    cfg = await _social_cfg(message.chat.id)
    state = "ON" if cfg.get("reactions", True) else "OFF"
    await message.reply_text(f"✨ AI/group reactions: <b>{state}</b>\nUse <code>/reactions on</code> or <code>/reactions off</code>.")


# ---------- Action game ----------
# Player state lives in one doc per (chat, user) that is NOT the check-in doc.
def _sf(chat_id, uid):
    return {"chat_id": int(chat_id), "user_id": int(uid), "type": {"$ne": "checkin"}}


_STATE_DEFAULTS = {"dead_until": 0, "protected_until": 0, "kills": 0, "deaths": 0}


async def _state(chat_id, uid):
    d = await ACTION.find_one(_sf(chat_id, uid))
    return d or {"chat_id": chat_id, "user_id": uid, **_STATE_DEFAULTS}


async def _ensure_state(chat_id, uid):
    await ACTION.update_one(_sf(chat_id, uid), {"$setOnInsert": dict(_STATE_DEFAULTS)}, upsert=True)


async def protect_user(chat_id: int, actor_id: int, target_id: int, duration: int | None = None):
    duration = duration or config.SHIELD_DURATION
    await _ensure_state(chat_id, target_id)
    await ACTION.update_one(_sf(chat_id, target_id), {"$set": {"protected_until": time.time() + duration}})


def _wait(sec: float) -> str:
    sec = max(1, int(sec))
    if sec >= 3600:
        return f"{sec // 3600}h {(sec % 3600) // 60}m"
    if sec >= 60:
        return f"{sec // 60}m {sec % 60}s"
    return f"{sec}s"


async def _claim(chat_id, uid, key: str, cooldown: int, daily: int):
    """Atomically use one action slot. Returns (ok, message). Enforces cooldown + daily cap."""
    now, today = time.time(), time.strftime("%Y-%m-%d", time.gmtime())
    await _ensure_state(chat_id, uid)
    doc = await ACTION.find_one(_sf(chat_id, uid)) or {}
    lim = (doc.get("limits") or {}).get(key) or {}
    last = float(lim.get("last", 0))
    count = int(lim.get("count", 0)) if lim.get("day") == today else 0
    if lim and now - last < cooldown:
        return False, f"⏳ /{key} is on cooldown — try again in <b>{_wait(cooldown - (now - last))}</b>."
    if count >= daily:
        return False, f"🚫 Daily /{key} limit reached (<b>{daily}</b> per day). It resets at 00:00 UTC."
    cond = {"limits." + key + ".last": lim["last"]} if lim else {"limits." + key: {"$exists": False}}
    res = await ACTION.update_one({**_sf(chat_id, uid), **cond}, {"$set": {"limits." + key: {"last": now, "day": today, "count": count + 1}}})
    if res.matched_count != 1:
        return False, "⏳ Easy there — one action at a time."
    return True, ""


async def _blocked_if_ko(message: Message):
    """Knocked-out players can't use the action commands. Returns True (and replies) if blocked."""
    st = await _state(message.chat.id, message.from_user.id)
    left = float(st.get("dead_until", 0)) - time.time()
    if left > 0:
        await message.reply_text(f"💀 You're knocked out for another <b>{_wait(left)}</b>. Ask someone to <code>/revive</code> you.")
        return True
    return False


@app.on_message(filters.command("rob") & filters.group, group=33)
async def rob_cmd(_, message: Message):
    target = await _target(message)
    if not target or target.id == message.from_user.id or target.is_bot:
        return await message.reply_text("💰 Reply to a user or use <code>/rob @username</code>.")
    if await _blocked_if_ko(message):
        return
    now = time.time()
    victim = await _state(message.chat.id, target.id)
    if victim.get("protected_until", 0) > now:
        return await message.reply_text("🛡️ That user is protected right now.")
    if victim.get("robbed_until", 0) > now:
        return await message.reply_text(f"🚫 They were just robbed. Give them <b>{_wait(victim['robbed_until'] - now)}</b> to recover.")
    vd = await _wallet(message.chat.id, target.id)
    if int(vd.get("balance", 0)) < config.ROB_MIN_VICTIM_BALANCE:
        return await message.reply_text(f"😅 Not worth it — they have less than {_money(config.ROB_MIN_VICTIM_BALANCE)}.")
    ok, msg = await _claim(message.chat.id, message.from_user.id, "rob", config.ROB_COOLDOWN, config.ROB_DAILY_LIMIT)
    if not ok:
        return await message.reply_text(msg)
    await _wallet(message.chat.id, message.from_user.id)
    if random.random() > 0.60:
        actor = await _wallet(message.chat.id, message.from_user.id)
        penalty = min(int(actor.get("balance", 0)), random.randint(10, 50))
        if penalty and not await _debit(message.chat.id, message.from_user.id, penalty):
            penalty = 0
        return await message.reply_text(f"🚨 {_mention(message.from_user)} got caught! Lost {_money(penalty)}.")
    # Never take more than a quarter of the victim's balance.
    cap = max(1, int(vd.get("balance", 0)) // 4)
    amount = min(cap, random.randint(50, 250))
    if not await _debit(message.chat.id, target.id, amount):
        return await message.reply_text("😅 They spent it before you could grab it.")
    await _credit(message.chat.id, message.from_user.id, amount)
    await _ensure_state(message.chat.id, target.id)
    await ACTION.update_one(_sf(message.chat.id, target.id), {"$set": {"robbed_until": now + config.ROB_VICTIM_IMMUNITY}})
    await message.reply_text(f"🥷 {_mention(message.from_user)} robbed {_mention(target)} for <b>{_money(amount)}</b>!")


async def _kill_action(message: Message):
    target = await _target(message)
    if not target or target.id == message.from_user.id or target.is_bot:
        return await message.reply_text("🔪 Reply to a user or use <code>/kill @username</code>.")
    if await _blocked_if_ko(message):
        return
    ts = await _state(message.chat.id, target.id)
    if ts.get("protected_until", 0) > time.time():
        return await message.reply_text("🛡️ Target is protected!")
    if ts.get("dead_until", 0) > time.time():
        return await message.reply_text("💀 They're already out of the round.")
    ok, msg = await _claim(message.chat.id, message.from_user.id, "kill", config.KILL_COOLDOWN, config.KILL_DAILY_LIMIT)
    if not ok:
        return await message.reply_text(msg)
    if random.random() >= 0.65:
        return await message.reply_text(f"🔪 {_mention(message.from_user)} attacked {_mention(target)}… but missed! 😭")
    mins = max(1, config.KNOCKOUT_DURATION // 60)
    await _ensure_state(message.chat.id, target.id)
    await ACTION.update_one(_sf(message.chat.id, target.id), {"$set": {"dead_until": time.time() + config.KNOCKOUT_DURATION}, "$inc": {"deaths": 1}})
    await ACTION.update_one(_sf(message.chat.id, message.from_user.id), {"$inc": {"kills": 1}})
    await message.reply_text(f"☠️ {_mention(message.from_user)} eliminated {_mention(target)} for {mins} minutes.\nUse <code>/revive</code> to bring someone back.")


@app.on_message(filters.command("kill") & filters.group, group=33)
async def kill_cmd(_, message: Message):
    await _kill_action(message)


async def _protect_action(message: Message):
    target = await _target(message) or message.from_user  # no target = shield yourself
    if target.is_bot:
        return await message.reply_text("🤖 Bots don't need a shield.")
    if await _blocked_if_ko(message):
        return
    cost, mins = config.SHIELD_COST, max(1, config.SHIELD_DURATION // 60)
    ts = await _state(message.chat.id, target.id)
    if ts.get("protected_until", 0) > time.time():
        return await message.reply_text(f"🛡️ {_mention(target)} is already shielded ({_wait(ts['protected_until'] - time.time())} left).")
    payer = await _wallet(message.chat.id, message.from_user.id)
    if int(payer.get("balance", 0)) < cost:
        return await message.reply_text(f"💸 A shield costs {_money(cost)} — you have {_money(payer.get('balance', 0))}.")
    ok, msg = await _claim(message.chat.id, message.from_user.id, "shield", config.SHIELD_COOLDOWN, config.SHIELD_DAILY_LIMIT)
    if not ok:
        return await message.reply_text(msg)
    if not await _debit(message.chat.id, message.from_user.id, cost):
        return await message.reply_text(f"💸 A shield costs {_money(cost)}.")
    await protect_user(message.chat.id, message.from_user.id, target.id)
    who = "themselves" if target.id == message.from_user.id else _mention(target)
    await message.reply_text(f"🛡️ {_mention(message.from_user)} shielded {who} for {mins} minutes. Cost: {_money(cost)}")


@app.on_message(filters.command(["shield", "protection"]) & filters.group, group=33)
async def shield_cmd(_, message: Message):
    await _protect_action(message)


@app.on_message(filters.command("revive") & filters.group, group=33)
async def revive_cmd(_, message: Message):
    target = await _target(message) or message.from_user
    ts = await _state(message.chat.id, target.id)
    if ts.get("dead_until", 0) <= time.time():
        return await message.reply_text("✨ That user is already alive.")
    cost = config.REVIVE_COST
    if not await _debit(message.chat.id, message.from_user.id, cost):
        return await message.reply_text(f"💸 Revive costs {_money(cost)}.")
    await ACTION.update_one(_sf(message.chat.id, target.id), {"$set": {"dead_until": 0, "protected_until": time.time() + 300}})
    await message.reply_text(f"💚 {_mention(target)} has been revived (5 min of protection)! Cost: {_money(cost)}")


@app.on_message(filters.command("topkill") & filters.group, group=33)
async def topkill_cmd(_, message: Message):
    rows, i = [], 1
    async for d in ACTION.find({"chat_id": message.chat.id, "type": {"$ne": "checkin"}, "kills": {"$gt": 0}}).sort("kills", -1).limit(10):
        try:
            u = await app.get_users(int(d["user_id"]))
        except Exception:
            continue
        rows.append(f"{i}. {_mention(u)} — ☠️ <b>{int(d.get('kills', 0))}</b>")
        i += 1
    await message.reply_text("☠️ <b>Top Killers — this group</b>\n\n" + "\n".join(rows) if rows else "☠️ No kills yet.")


# ---------- Romance ----------
@app.on_message(filters.command("propose") & filters.group, group=34)
async def propose_cmd(_, message: Message):
    target = await _target(message)
    if not target or target.id == message.from_user.id or target.is_bot:
        return await message.reply_text("💍 Reply to someone or use <code>/propose @username</code>.")
    existing = await REL.find_one({"chat_id": message.chat.id, "status": "married", "$or": [{"user1": message.from_user.id}, {"user2": message.from_user.id}, {"user1": target.id}, {"user2": target.id}]})
    if existing: return await message.reply_text("💍 One of you is already married in this group.")
    pid=uuid.uuid4().hex[:12]
    await REL.insert_one({"chat_id":message.chat.id,"proposal_id":pid,"user1":message.from_user.id,"user2":target.id,"status":"pending","created_at":time.time()})
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("💗 Accept",callback_data=f"PROP_Y:{pid}"),InlineKeyboardButton("💔 Reject",callback_data=f"PROP_N:{pid}")]])
    await message.reply_text(f"💍 {_mention(message.from_user)} proposed to {_mention(target)}!\n\nOnly the proposed person can decide.",reply_markup=kb)


@app.on_callback_query(filters.regex(r"^PROP_[YN]:"))
async def proposal_cb(_, cb: CallbackQuery):
    pid=cb.data.split(":",1)[1]
    d=await REL.find_one({"proposal_id":pid,"status":"pending"})
    if not d: return await cb.answer("Proposal expired.",show_alert=True)
    if int(cb.from_user.id)!=int(d["user2"]): return await cb.answer("Only the proposed person can decide.",show_alert=True)
    if cb.data.startswith("PROP_N"):
        await REL.update_one({"proposal_id":pid},{"$set":{"status":"rejected","updated_at":time.time()}})
        return await cb.message.edit_text("💔 Proposal rejected. Maybe next time 😭")
    await REL.update_one({"proposal_id":pid},{"$set":{"status":"married","married_at":time.time()}})
    await cb.message.edit_text("💍 <b>It's official! Married 💞</b>")
    await cb.answer("Congratulations! 💕")


@app.on_message(filters.command(["marriage", "married"]) & filters.group, group=34)
async def marriage_cmd(_, message: Message):
    uid=message.from_user.id
    d=await REL.find_one({"chat_id":message.chat.id,"status":"married","$or":[{"user1":uid},{"user2":uid}]})
    if not d: return await message.reply_text("💔 You're single in this group.")
    other=d["user2"] if int(d["user1"])==int(uid) else d["user1"]
    try: u=await app.get_users(other)
    except Exception: return await message.reply_text("💞 Married, but I couldn't resolve your partner right now.")
    await message.reply_text(f"💍 {_mention(message.from_user)} is married to {_mention(u)} in this group. 💕")


@app.on_message(filters.command("divorce") & filters.group, group=34)
async def divorce_cmd(_, message: Message):
    uid=message.from_user.id
    d=await REL.find_one({"chat_id":message.chat.id,"status":"married","$or":[{"user1":uid},{"user2":uid}]})
    if not d: return await message.reply_text("💔 You're not married here.")
    await REL.update_one({"proposal_id":d.get("proposal_id")},{"$set":{"status":"divorced","divorced_at":time.time()}})
    await message.reply_text("📜 Marriage dissolved. New chapter unlocked. 🥀")


@app.on_message(filters.command("shippering") & filters.group, group=34)
async def shippering_cmd(_, message: Message):
    a=message.from_user; b=await _target(message)
    if not b: return await message.reply_text("💕 Reply to someone with <code>/shippering</code>.")
    seed=f"{message.chat.id}:{min(a.id,b.id)}:{max(a.id,b.id)}"; rng=random.Random(seed)
    score=rng.randint(0,100)
    bar="❤️"*(score//10)+"🖤"*(10-score//10)
    await message.reply_text(f"💞 <b>Ship Check</b>\n{_mention(a)} × {_mention(b)}\n\n{bar}\n💗 Compatibility: <b>{score}%</b>")
