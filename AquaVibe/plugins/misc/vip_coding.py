"""AquaVibe VIP/VIP Pro + safe AI coding agent.

Payments are manual: the bot shows the configured UPI/crypto destination and
owner approves the payment. No banking credentials are collected by the bot.
"""
from __future__ import annotations
import asyncio, os, uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from AquaVibe.core.runtime import app
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
from AquaVibe.utils.database import get_coding_plan, set_coding_plan, increment_coding_jobs, save_puter_link, get_puter_link
from AquaVibe.utils.coding_agent import submit_job, cleanup
from config import BANNED_USERS, OWNER_ID, VIP_PRICE_INR, VIP_PRO_PRICE_INR, VIP_DAYS, VIP_PRO_DAYS, VIP_UPI_ID, VIP_CRYPTO_ADDRESS, VIP_PAYMENT_NOTE
InlineKeyboardButton=ColoredInlineKeyboardButton


def vip_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("💎 BUY VIP",callback_data="avvip:buy:vip")],[InlineKeyboardButton("💎 MENU",callback_data="avvip:menu"),InlineKeyboardButton("➡️ NEXT",callback_data="avvip:pro")]])

def pro_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("👑 BUY PRO",callback_data="avvip:buy:pro")],[InlineKeyboardButton("💎 MENU",callback_data="avvip:menu"),InlineKeyboardButton("❌ CLOSE",callback_data="avvip:close")]])

def vip_text():
    return (f"🔱 <b>VIP</b> 🔱\n\n💰 <b>Price:</b> ₹{VIP_PRICE_INR} / Month 🔥\n\n"
            "┌─ <b>VIP Features</b> ─┐\n├ 🤖 AI Coding Access ✔️\n├ 📦 ZIP Create / Edit ✔️\n├ 🔍 Repository Analysis ✔️\n├ 📝 File Create / Edit ✔️\n├ 🛠️ Error Fixing ✔️\n├ ⚙️ Limited Concurrent Jobs ✔️\n└ 📋 Normal Queue ✔️\n\n"
            "💎 Upgrade to <b>VIP Pro</b> for heavy coding & priority processing.")

def pro_text():
    return (f"👑 <b>VIP Pro</b> 🪽\n\n💰 <b>Price:</b> ₹{VIP_PRO_PRICE_INR} / Month ❄️\n\n"
            "┌─ <b>Everything in VIP +</b> ─┐\n├ 🚀 Heavy Repository Editing ✔️\n├ 📦 Larger ZIP / Repositories ✔️\n├ ⚡ Priority Queue ✔️\n├ 🔢 Higher Job Limits ✔️\n├ 🩹 Self-Healing / Error Fixing ✔️\n└ ⏱️ Longer Execution Timeout ✔️\n\n"
            "👑 <b>VIP Pro</b> — Built for heavy coding, large repositories & long jobs.")

@app.on_message(filters.command("vip") & ~BANNED_USERS)
async def vip(_, message: Message):
    plan=await get_coding_plan(message.from_user.id)
    suffix="\n\n✅ Your plan: <b>VIP</b>" if plan.get("plan")=="vip" else ("\n\n👑 Your plan: <b>VIP Pro</b>" if plan.get("plan")=="vip_pro" else "")
    return await message.reply_text(vip_text()+suffix,reply_markup=vip_keyboard())

@app.on_callback_query(filters.regex(r"^avvip:(menu|pro|close)$"))
async def vip_callbacks(_, q: CallbackQuery):
    action=q.data.split(":",1)[1]
    if action=="menu": return await q.message.edit_text(vip_text(),reply_markup=vip_keyboard())
    if action=="pro": return await q.message.edit_text(pro_text(),reply_markup=pro_keyboard())
    if action=="close": return await q.message.delete()

@app.on_callback_query(filters.regex(r"^avvip:buy:(vip|pro)$"))
async def buy_callback(_, q: CallbackQuery):
    plan=q.data.rsplit(":",1)[1]
    price=VIP_PRICE_INR if plan=="vip" else VIP_PRO_PRICE_INR
    lines=[f"💳 <b>{'VIP Pro' if plan=='pro' else 'VIP'} — ₹{price}</b>","",VIP_PAYMENT_NOTE]
    if VIP_UPI_ID: lines.append(f"\nUPI: <code>{escape(VIP_UPI_ID)}</code>")
    if VIP_CRYPTO_ADDRESS: lines.append(f"\nCrypto: <code>{escape(VIP_CRYPTO_ADDRESS)}</code>")
    lines.append("\nAfter payment, send <code>/paid PLAN UTR</code> in this private chat. Owner approval is required.")
    await q.answer()
    await q.message.edit_text("\n".join(lines),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 MENU",callback_data="avvip:menu")]]))

@app.on_message(filters.command("addemail") & ~BANNED_USERS)
async def addemail(_, message: Message):
    if len(message.command)!=2 or "@" not in message.command[1]:
        return await message.reply_text("🔗 Use <code>/addemail your@puter.email</code>.\n\nThis links the email identity only; never send your Puter password or auth token.")
    email=message.command[1].strip().lower()
    await save_puter_link(message.from_user.id,email,"pending")
    bridge="\n\n🔐 Connect page: "+escape(__import__('config').PUTER_BRIDGE_URL) if __import__('config').PUTER_BRIDGE_URL else ""
    await message.reply_text(f"✅ Puter email saved: <code>{escape(email)}</code>\nStatus: <b>Pending connection</b>{bridge}\n\n⚠️ Never share your Puter password or auth token with the bot.")

@app.on_message(filters.command("paid") & ~BANNED_USERS)
async def paid(_, message: Message):
    if len(message.command)<3 or message.command[1].lower() not in {"vip","pro","vippro"}:
        return await message.reply_text("Use <code>/paid vip UTR</code> or <code>/paid pro UTR</code>.")
    plan="vip_pro" if message.command[1].lower() in {"pro","vippro"} else "vip"
    utr=" ".join(message.command[2:])[:120]
    await app.send_message(OWNER_ID,f"💳 <b>VIP Payment Pending</b>\n\nUser: <code>{message.from_user.id}</code>\nPlan: <b>{plan}</b>\nUTR/Reference: <code>{escape(utr)}</code>",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ APPROVE",callback_data=f"avpay:approve:{message.from_user.id}:{plan}"),InlineKeyboardButton("❌ REJECT",callback_data=f"avpay:reject:{message.from_user.id}")]]))
    await message.reply_text("📨 Payment proof sent to owner. Access will activate after approval.")

@app.on_callback_query(filters.regex(r"^avpay:(approve|reject):"))
async def payment_approval(_, q: CallbackQuery):
    if q.from_user.id!=OWNER_ID: return await q.answer("Owner only.",show_alert=True)
    parts=q.data.split(":"); action=parts[1]; uid=int(parts[2])
    if action=="reject":
        await q.message.edit_text(q.message.text+"\n\n❌ <b>Rejected</b>")
        try: await app.send_message(uid,"❌ Payment rejected. Please contact the owner if this was a mistake.")
        except Exception: pass
        return
    plan=parts[3]; until=await set_coding_plan(uid,plan,VIP_PRO_DAYS if plan=="vip_pro" else VIP_DAYS)
    await q.message.edit_text(q.message.text+f"\n\n✅ <b>Approved</b>\nUntil: <code>{until:%Y-%m-%d}</code>")
    try: await app.send_message(uid,f"🎉 <b>{'VIP Pro' if plan=='vip_pro' else 'VIP'} activated!</b>\nValid until <code>{until:%Y-%m-%d}</code>.\nUse <code>/ask</code> for coding jobs.")
    except Exception: pass

@app.on_message(filters.command("ask") & ~BANNED_USERS)
async def ask_code(_, message: Message):
    if not message.from_user: return
    plan=await get_coding_plan(message.from_user.id)
    if message.from_user.id!=OWNER_ID and plan.get("plan") not in {"vip","vip_pro"}:
        return await message.reply_text("🔒 <b>AI Coding</b> requires VIP or VIP Pro.\nUse <code>/vip</code> to view plans.")
    prompt=message.text.split(None,1)[1].strip() if message.text and " " in message.text else ""
    reply=message.reply_to_message
    zip_path=None
    if reply and reply.document and reply.document.file_name.lower().endswith(".zip"):
        cfg=__import__('config')
        max_zip=cfg.CODING_PRO_MAX_ZIP_MB if plan.get("plan")=="vip_pro" else cfg.CODING_MAX_ZIP_MB
        size=(reply.document.file_size or 0)/1024/1024
        if size>max_zip: return await message.reply_text(f"❌ ZIP is larger than your plan limit ({max_zip} MB).")
        work=Path(cfg.CODING_WORKSPACE_DIR); work.mkdir(exist_ok=True)
        zip_path=str(work/f"upload_{uuid.uuid4().hex}.zip")
        await reply.download(file_name=zip_path)
    if not prompt: prompt="Inspect this repository and make it production-ready."
    status=await message.reply_text("🧠 <b>Coding agent started…</b>\n🔍 Inspecting repository / task…")
    job=uuid.uuid4().hex[:12]
    try:
        await increment_coding_jobs(message.from_user.id)
        priority=0 if plan.get("plan")=="vip_pro" or message.from_user.id==OWNER_ID else 10
        out,summary=await submit_job(prompt,zip_path,job_id=job,priority=priority)
        await status.edit_text("🧪 Tests passed. Packaging ZIP…")
        await message.reply_document(out,caption=f"✅ <b>Coding job complete</b>\n\n{escape(summary[:1200])}\n\n🆔 <code>{job}</code>")
        await status.delete()
    except Exception as exc:
        await status.edit_text(f"❌ <b>Coding job failed</b>\n<code>{escape(str(exc)[:2500])}</code>")
    finally:
        if zip_path:
            try: Path(zip_path).unlink(missing_ok=True)
            except OSError: pass
        cleanup(job)
