"""AquaVibe social layer: Gemini chat, group memory, economy and game lobbies."""
from __future__ import annotations
import html, random, re, time
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
import config
from AquaVibe.core.mongo import mongodb
from AquaVibe.core.runtime import app
from AquaVibe.utils.ai import ask

AI = mongodb.aqua_ai_memory
EC = mongodb.aqua_economy
CFG = mongodb.aqua_social_config

def _name(u): return (getattr(u, "first_name", None) or getattr(u, "username", None) or "User").strip()
def _mention(u): return f'<a href="tg://user?id={int(u.id)}">{html.escape(_name(u))}</a>'
def _owner(uid): return int(uid) == int(config.OWNER_ID)

async def _social_cfg(chat_id):
    return await CFG.find_one({"chat_id": int(chat_id)}) or {}


async def _enabled(chat_id, feature):
    if _owner(chat_id): return True
    d = await CFG.find_one({"chat_id": int(chat_id)}) or {}
    return d.get(feature, True)

async def _history(chat_id, user_id=None):
    d = await AI.find_one({"chat_id": int(chat_id)}) or {}
    turns = d.get("turns", [])[-max(4, config.AI_MEMORY_TURNS * 2):]
    return [{"role": "assistant" if x.get("role") == "assistant" else "user", "content": x.get("content", "")} for x in turns]

async def _save_turn(chat_id, user_id, role, text):
    await AI.update_one(
        {"chat_id": int(chat_id)},
        {"$push": {"turns": {"role": role, "content": text[:4000], "ts": time.time()}}, "$set": {"updated_at": time.time()}},
        upsert=True,
    )

async def _ai_prompt(chat_id, user_id, prompt):
    doc = await AI.find_one({"chat_id": int(chat_id)}) or {}
    history = await _history(chat_id, user_id)
    memories = doc.get("memories", [])[-20:]
    system = "You are AquaVibe AI, an advanced Telegram companion. Speak naturally like a helpful human chat partner. Automatically match the user's language, script, slang and tone (including Hinglish, Hindi, Marathi, Urdu, Bengali and English). Use emojis naturally when they fit; do not spam them. Be warm, witty and conversational, but do not falsely claim real-world actions or experiences. Keep group memory strictly scoped to this chat/group."
    if memories:
        system += " Known group memories (use only when relevant): " + " | ".join(str(x) for x in memories)
    history.insert(0, {"role": "user", "content": system})
    return await ask(prompt, history)

@app.on_message(filters.command(["ai", "chat"]) & ~filters.channel, group=20)
async def ai_group_command(_, m: Message):
    if not await _enabled(m.chat.id, "ai"): return
    parts = (m.text or "").split(None, 1)
    prompt = parts[1].strip() if len(parts) > 1 else ""
    if not prompt and m.reply_to_message:
        prompt = m.reply_to_message.text or m.reply_to_message.caption or ""
    if not prompt: return await m.reply_text("🤖 <b>Aqua AI</b>\nUse <code>/ai your message</code>.")
    status = await m.reply_text("🧠 <i>thinking…</i>")
    try:
        from AquaVibe.plugins.social.ai_chat_plus import ai_reply, _name as _who
        answer = await ai_reply(m.chat.id, _who(m.from_user), prompt, context=f"[uid:{int(m.from_user.id)}]")
        await status.edit_text(html.escape(answer[:4000]))
    except Exception as exc:
        msg = "⚠️ AI temporarily unavailable. Please try again."
        if m.from_user and _owner(m.from_user.id):
            msg += f"\n\n<b>Owner info:</b> <code>{html.escape(str(exc)[:600])}</code>\nRun /aistatus to test every provider."
        await status.edit_text(msg)

@app.on_message(filters.command("remember") & ~filters.channel, group=20)
async def remember_cmd(_, m: Message):
    text = (m.text or "").split(None, 1)
    value = text[1].strip() if len(text) > 1 else ""
    if not value: return await m.reply_text("🧠 Use <code>/remember something important</code>.")
    await AI.update_one({"chat_id": m.chat.id}, {"$addToSet": {"memories": value[:1000]}, "$set": {"updated_at": time.time()}}, upsert=True)
    await m.reply_text("🧠 Yaad rakh liya — <b>sirf is group</b> ke context mein.")

@app.on_message(filters.command("forget") & ~filters.channel, group=20)
async def forget_cmd(_, m: Message):
    text = (m.text or "").split(None, 1)
    value = text[1].strip() if len(text) > 1 else ""
    if value:
        await AI.update_one({"chat_id": m.chat.id}, {"$pull": {"memories": value}})
    else:
        await AI.update_one({"chat_id": m.chat.id}, {"$set": {"memories": [], "turns": [], "summary": ""}})
    await m.reply_text("🧹 Memory updated.")

# Group auto-replies (mention / reply), stickers and reactions live in ai_chat_plus.py.

# ---------- Economy ----------
from AquaVibe.utils.economy import money as _money, wallet as _wallet_shared


async def _wallet(chat_id, uid):
    return await _wallet_shared(chat_id, uid)


@app.on_message(filters.command(["balance", "bal", "daily", "give", "toprich", "rich"]) & filters.group, group=30)
async def economy_cmd(_, m: Message):
    if not await _enabled(m.chat.id, "economy"): return
    cmd = (m.command[0] if m.command else "").lower()
    if cmd in ("balance", "bal"):
        d = await _wallet(m.chat.id, m.from_user.id)
        return await m.reply_text(f"💰 {_mention(m.from_user)}\nBalance: <b>{_money(d.get('balance', 0))}</b>")
    if cmd == "daily":
        d = await _wallet(m.chat.id, m.from_user.id); now = time.time()
        if now - float(d.get("daily_at", 0)) < 86400: return await m.reply_text("⏳ Daily reward already claimed.")
        amount = random.randint(config.ECONOMY_DAILY_MIN, config.ECONOMY_DAILY_MAX)
        await EC.update_one({"chat_id": m.chat.id, "user_id": m.from_user.id}, {"$inc": {"balance": amount}, "$set": {"daily_at": now, "name": _name(m.from_user)}}, upsert=True)
        return await m.reply_text(f"🎁 Daily reward: <b>{_money(amount)}</b>")
    if cmd == "give":
        if not m.reply_to_message or not m.reply_to_message.from_user: return await m.reply_text("Reply to someone with <code>/give 250</code>.")
        try: amount = int(m.command[1])
        except Exception: return await m.reply_text("Use a positive amount.")
        if amount <= 0: return await m.reply_text("Use a positive amount.")
        target = m.reply_to_message.from_user; sender = await _wallet(m.chat.id, m.from_user.id)
        if int(sender.get("balance", 0)) < amount: return await m.reply_text(f"❌ Not enough {config.CURRENCY_SYMBOL}.")
        await _wallet(m.chat.id, target.id)
        await EC.update_one({"chat_id": m.chat.id, "user_id": m.from_user.id}, {"$inc": {"balance": -amount}})
        await EC.update_one({"chat_id": m.chat.id, "user_id": target.id}, {"$inc": {"balance": amount}, "$set": {"name": _name(target)}})
        return await m.reply_text(f"💸 {_mention(m.from_user)} sent <b>{_money(amount)}</b> to {_mention(target)}.")
    rows=[]; i=1
    async for d in EC.find({"chat_id": m.chat.id}).sort("balance", -1).limit(10):
        rows.append(f"{i}. <a href=\"tg://user?id={d['user_id']}\">{html.escape(d.get('name','User'))}</a> — <b>{_money(d.get('balance',0))}</b>"); i+=1
    await m.reply_text("🏆 <b>Richest in this group</b>\n\n" + "\n".join(rows) if rows else "No economy data yet.")

@app.on_message(filters.command("social") & filters.group, group=30)
async def social_admin(_, m: Message):
    if not _owner(m.from_user.id): return
    if len(m.command) < 3: return await m.reply_text("⚙️ <code>/social ai on|off</code>\n<code>/social memory on|off</code>\n<code>/social economy on|off</code>\n<code>/social games on|off</code>")
    feature, value = m.command[1].lower(), m.command[2].lower()
    if feature not in {"ai","memory","economy","games"} or value not in {"on","off"}: return await m.reply_text("Unknown setting.")
    await CFG.update_one({"chat_id": m.chat.id}, {"$set": {feature: value == "on"}}, upsert=True)
    await m.reply_text(f"✅ {feature}: {value}")

# ---------- Inline router ----------
async def inline_social_router(query, client=None):
    """Chess quick-challenge, UNO hand picker and whispers (inline mode).

    Each handler returns False when the query is not meant for it, so a whisper
    such as ``chess club tonight @sam`` still reaches the whisper handler.
    """
    low = query.query.strip().lower()
    if low.startswith("chess"):
        from AquaVibe.plugins.social.chess_chat import chess_inline
        if await chess_inline(query):
            return True
    if low.startswith("uno"):
        from AquaVibe.plugins.social.uno_chat import uno_inline
        if await uno_inline(query):
            return True
    from AquaVibe.plugins.social.whisper import whisper_inline
    return await whisper_inline(client or app, query)
