"""蒼響 Economy, Coins, Membership, VIP and Telegram Stars store."""
from datetime import datetime, timezone, timedelta
import re

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
    Message, PreCheckoutQuery,
)

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.database import (
    add_coins, claim_daily_reward, claim_weekly_reward,
    ensure_economy_user, get_banner, get_coins,
    get_economy, get_group_referral, get_referrer, is_member, is_vip,
    get_profile_hides, toggle_profile_hide, set_profile_photo, get_profile_photo,
    set_profile_banner, get_profile_banner, add_custom_banner, get_custom_banners,
    mark_payment_paid, payment_already_processed, record_group_referral,
    force_remove_coins, remove_coins, set_banner, set_membership, set_vip, set_referrer, set_user_banner,
    get_song_count,
)
from config import BANNED_USERS, OWNER_ID

DAILY_BASE = 100
WEEKLY_BASE = 300
REFERRAL_REWARD = 1000

COIN_PACKS = {
    "coins10k": (10_000, 50),
    "coins50k": (50_000, 200),
    "coins100k": (100_000, 500),
}
VIP_PACKS = {
    "vip1m": (30, 50),
    "vip3m": (90, 200),
    "vip6m": (180, 400),
    "vip1y": (365, 600),
}
MEMBERSHIP_PACKS = {
    "mem1m": (30, 2_000, 25),
    "mem3m": (90, 6_000, 50),
    "mem6m": (180, 10_000, 100),
    "mem1y": (365, 15_000, 200),
}

def _now():
    return datetime.now(timezone.utc)

def _extra_percent(data):
    if int(data.get("user_id", 0)) == int(OWNER_ID):
        return 5
    vip_until = data.get("vip_until")
    if vip_until and vip_until > _now():
        return 5
    mem_until = data.get("membership_until")
    if mem_until and mem_until > _now():
        return 1
    return 0

def _reward(base, percent):
    return int(base * (100 + percent) / 100)

def _menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Coins", callback_data="eco:coins"),
         InlineKeyboardButton("👑 VIP", callback_data="eco:vip")],
        [InlineKeyboardButton("💎 Membership", callback_data="eco:mem"),
         InlineKeyboardButton("🛍 Store", callback_data="eco:store")],
        [InlineKeyboardButton("🎨 My Profile", callback_data="eco:profile")],
        [InlineKeyboardButton("📜 History", callback_data="eco:history"), InlineKeyboardButton("📂 Playlists", callback_data="eco:playlists")],
    ])

def _back():
    return [InlineKeyboardButton("◀️ Back", callback_data="eco:home")]

def _store():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 10,000 — ⭐50", callback_data="eco:buy:coins10k"),
         InlineKeyboardButton("🪙 50,000 — ⭐200", callback_data="eco:buy:coins50k")],
        [InlineKeyboardButton("🪙 100,000 — ⭐500", callback_data="eco:buy:coins100k")],
        [InlineKeyboardButton("👑 VIP 1M — ⭐50", callback_data="eco:buy:vip1m"),
         InlineKeyboardButton("👑 VIP 3M — ⭐200", callback_data="eco:buy:vip3m")],
        [InlineKeyboardButton("👑 VIP 6M — ⭐400", callback_data="eco:buy:vip6m"),
         InlineKeyboardButton("👑 VIP 1Y — ⭐600", callback_data="eco:buy:vip1y")],
        [InlineKeyboardButton("💎 Mem 1M — 2,000🪙 / ⭐25", callback_data="eco:buy:mem1m")],
        [InlineKeyboardButton("💎 Mem 3M — 6,000🪙 / ⭐50", callback_data="eco:buy:mem3m")],
        [InlineKeyboardButton("💎 Mem 6M — 10,000🪙 / ⭐100", callback_data="eco:buy:mem6m")],
        [InlineKeyboardButton("💎 Mem 1Y — 15,000🪙 / ⭐200", callback_data="eco:buy:mem1y")],
        _back(),
    ])

async def _invoice(chat_id, payload, title, description, stars):
    # Telegram Stars digital-goods invoices use currency XTR and require no
    # external payment provider. A successful_payment update is required before
    # granting the purchased item.
    await app.send_invoice(
        chat_id=chat_id,
        title=title[:32],
        description=description[:255],
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=int(stars))],
    )

async def _apply_stars_purchase(user_id, payload, stars, charge_id):
    if await payment_already_processed(charge_id):
        return "already"
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "trabelx":
        return "invalid"

    product = parts[1]
    plan = parts[2]
    data = await get_economy(user_id)

    if product == "coins" and plan in COIN_PACKS:
        coins, expected = COIN_PACKS[plan]
        if stars != expected:
            return "invalid"
        grant = coins
        await add_coins(user_id, grant, "stars_coins")
        await mark_payment_paid(payload, charge_id)
        return f"🪙 Added <b>{grant:,}</b> coins."

    if product == "vip" and plan in VIP_PACKS:
        days, expected = VIP_PACKS[plan]
        if stars != expected:
            return "invalid"
        current = data.get("vip_until")
        start = current if current and current > _now() else _now()
        await set_vip(user_id, start + timedelta(days=days))
        await mark_payment_paid(payload, charge_id)
        return f"👑 VIP activated for <b>{days} days</b>."

    if product == "mem" and plan in MEMBERSHIP_PACKS:
        days, coin_price, expected = MEMBERSHIP_PACKS[plan]
        if stars != expected:
            return "invalid"
        current = data.get("membership_until")
        start = current if current and current > _now() else _now()
        await set_membership(user_id, start + timedelta(days=days))
        await mark_payment_paid(payload, charge_id)
        return f"💎 Membership activated for <b>{days} days</b>."

    return "invalid"

@app.on_message(filters.command(["bal"]) & ~BANNED_USERS)
async def balance_command(_, message: Message):
    user_id = message.from_user.id
    await ensure_economy_user(user_id)
    data = await get_economy(user_id)
    await message.reply_text(
        f"🪙 <b>Total Balance</b>\n\n"
        f"💰 Coins: <b>{data.get('coins', 0):,}</b>\n"
        f"👑 VIP: <b>{'ACTIVE' if await is_vip(user_id) else 'OFF'}</b>\n"
        f"💎 Membership: <b>{'ACTIVE' if await is_member(user_id) else 'OFF'}</b>",
        reply_markup=_menu(),
    )

async def _resolve_target(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) >= 2:
        raw = message.command[1].strip()
        try:
            return await app.get_users(int(raw))
        except Exception:
            try:
                return await app.get_users(raw.lstrip("@"))
            except Exception:
                return None
    return message.from_user

def _duration_arg(message, default_days=30):
    if len(message.command) >= 3:
        raw = message.command[2].lower().strip()
    elif len(message.command) >= 2:
        raw = message.command[1].lower().strip()
    else:
        return default_days
    m = re.fullmatch(r"(\d+)([smhdw]?)", raw)
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2) or "d"
    mult = {"s": 1/86400, "m": 1/1440, "h": 1/24, "d": 1, "w": 7}[unit]
    days = value * mult
    return days if days > 0 else None

@app.on_message(filters.command(["vip"]) & ~BANNED_USERS)
async def vip_command(_, message: Message):
    if message.from_user.id == OWNER_ID and (message.reply_to_message or len(message.command) >= 2):
        target = await _resolve_target(message)
        if not target:
            return await message.reply_text("❌ Could not find that user. Use /vip USER DAYS or reply to a user with /vip DAYS.")
        days = _duration_arg(message)
        if days is None:
            return await message.reply_text("❌ Invalid duration. Example: /vip @username 30d")
        data = await get_economy(target.id)
        current = data.get("vip_until")
        start = current if current and current > _now() else _now()
        await set_vip(target.id, start + timedelta(days=days))
        return await message.reply_text(f"👑 VIP granted to {target.mention} for <b>{days:g} days</b>.")
    data = await get_economy(message.from_user.id)
    until = data.get("vip_until")
    active = await is_vip(message.from_user.id)
    text = "👑 <b>VIP Session</b>\n\n" + (f"Status: <b>ACTIVE</b>\nUntil: <code>{until}</code>\n\n" if active and until else "Status: <b>ACTIVE FOREVER</b>\n\n" if active and message.from_user.id == OWNER_ID else "Status: <b>NOT ACTIVE</b>\n\n")
    text += "+5% daily/weekly/referral rewards • VIP profile banner"
    return await message.reply_text(text, reply_markup=_store())

@app.on_message(filters.command(["membership"]) & ~BANNED_USERS)
async def membership_command(_, message: Message):
    if message.from_user.id == OWNER_ID and (message.reply_to_message or len(message.command) >= 2):
        target = await _resolve_target(message)
        if not target:
            return await message.reply_text("❌ Could not find that user. Use /membership USER DAYS or reply to a user with /membership DAYS.")
        days = _duration_arg(message)
        if days is None:
            return await message.reply_text("❌ Invalid duration. Example: /membership @username 30d")
        data = await get_economy(target.id)
        current = data.get("membership_until")
        start = current if current and current > _now() else _now()
        await set_membership(target.id, start + timedelta(days=days))
        return await message.reply_text(f"💎 Membership granted to {target.mention} for <b>{days:g} days</b>.")
    data = await get_economy(message.from_user.id)
    until = data.get("membership_until")
    active = bool(until and until > _now())
    text = "💎 <b>Membership Session</b>\n\n" + (f"Status: <b>ACTIVE</b>\nUntil: <code>{until}</code>\n\n" if active else "Status: <b>NOT ACTIVE</b>\n\n")
    text += "+1% daily/weekly/referral rewards • member profile banner"
    return await message.reply_text(text, reply_markup=_store())

@app.on_message(filters.command(["coins", "economy", "wallet", "shop", "store"]) & filters.private & ~BANNED_USERS)
async def economy_command(_, message: Message):
    user_id = message.from_user.id
    await ensure_economy_user(user_id)
    data = await get_economy(user_id)
    percent = _extra_percent(data)
    vip = "ON" if await is_vip(user_id) else "OFF"
    mem = "ON" if await is_member(user_id) else "OFF"
    await message.reply_text(
        f"🪙 <b>蒼響 Economy</b>\n\n"
        f"💰 Coins: <b>{data.get('coins', 0):,}</b>\n"
        f"👑 VIP: <b>{vip}</b>\n"
        f"💎 Membership: <b>{mem}</b>\n"
        f"✨ Reward bonus: <b>+{percent}%</b>\n\n"
        f"Daily: {DAILY_BASE} coins • Weekly: {WEEKLY_BASE} coins\n"
        f"Referral: {REFERRAL_REWARD} coins when the referred user adds the bot to a group.",
        reply_markup=_menu(),
    )

@app.on_message(filters.command(["daily"]) & filters.private & ~BANNED_USERS)
async def daily_command(_, message: Message):
    user_id = message.from_user.id
    data = await get_economy(user_id)
    amount = _reward(DAILY_BASE, _extra_percent(data))
    got = await claim_daily_reward(user_id, amount)
    await message.reply_text(
        f"🎁 Daily reward: <b>+{got or 0} coins</b>.\n"
        + ("Come back tomorrow for another reward." if got else "You already claimed today's reward.")
    )

@app.on_message(filters.command(["weekly"]) & filters.private & ~BANNED_USERS)
async def weekly_command(_, message: Message):
    user_id = message.from_user.id
    data = await get_economy(user_id)
    amount = _reward(WEEKLY_BASE, _extra_percent(data))
    got = await claim_weekly_reward(user_id, amount)
    await message.reply_text(
        f"🎁 Weekly reward: <b>+{got or 0} coins</b>.\n"
        + ("Come back next week for another reward." if got else "You already claimed this week's reward.")
    )

@app.on_message(filters.command(["refer"]) & filters.private & ~BANNED_USERS)
async def referral_command(_, message: Message):
    me = await app.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    await message.reply_text(
        f"🔗 <b>Your referral link</b>\n\n<code>{link}</code>\n\n"
        f"🎁 You receive <b>{REFERRAL_REWARD:,} coins</b> when a referred user starts the bot and then adds it to a group."
    )

@app.on_message(filters.command(["profile"]) & filters.private & ~BANNED_USERS)
async def profile_command(_, message: Message):
    await _send_profile(message.chat.id, message.from_user.id, user=message.from_user)


def _profile_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Change Photo", callback_data="prof:photo"),
         InlineKeyboardButton("🖼 Banners", callback_data="prof:banners")],
        [InlineKeyboardButton("🛍 Membership", callback_data="eco:mem"),
         InlineKeyboardButton("👑 VIP", callback_data="eco:vip")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="prof:refresh")],
    ])


async def _profile_media(user_id: int):
    """Resolve the selected profile photo/banner; generated defaults are used otherwise."""
    from pathlib import Path
    base = Path(__file__).resolve().parents[2] / "assets"
    photo = await get_profile_photo(user_id) or str(base / "profile_default.png")
    banner = await get_profile_banner(user_id)
    if not banner:
        if await is_member(user_id) or await is_vip(user_id):
            banner = await get_banner(1) or await get_banner(2)
    banner = banner or str(base / "banner_default.png")
    return photo, banner


async def _send_profile(chat_id, user_id, user=None):
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import tempfile, os

    await ensure_economy_user(user_id)
    if user is None:
        user = await app.get_users(user_id)
    data = await get_economy(user_id)
    hides = await get_profile_hides(user_id)
    song_count = await get_song_count(user_id)
    status = {"membership": await is_member(user_id), "vip": await is_vip(user_id)}
    photo_ref, banner_ref = await _profile_media(user_id)

    tmpdir = Path(tempfile.mkdtemp(prefix="trebel-profile-"))
    try:
        async def load_ref(ref, fallback):
            try:
                if isinstance(ref, str) and Path(ref).is_file():
                    return Image.open(ref).convert("RGB")
                path = await app.download_media(ref, file_name=str(tmpdir / "media"))
                return Image.open(path).convert("RGB") if path else Image.open(fallback).convert("RGB")
            except Exception:
                return Image.open(fallback).convert("RGB")

        base = Path(__file__).resolve().parents[2] / "assets"
        banner = await load_ref(banner_ref, base / "banner_default.png")
        avatar = await load_ref(photo_ref, base / "profile_default.png")
        W, H = 1200, 700
        banner = ImageOps.fit(banner, (W, H), method=Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", (W, H), (8, 12, 20, 100))
        banner = Image.alpha_composite(banner.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(banner)
        try:
            font_big = ImageFont.truetype(str(base / "default.ttf"), 54)
            font = ImageFont.truetype(str(base / "default.ttf"), 30)
            small = ImageFont.truetype(str(base / "default.ttf"), 25)
        except Exception:
            font_big = font = small = ImageFont.load_default()

        avatar = ImageOps.fit(avatar, (220, 220), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        mask = Image.new("L", (220, 220), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 220, 220), fill=255)
        banner.paste(avatar, (70, 70), mask)

        name = (user.first_name or "User").replace("\n", " ")[:32]
        username = f"@{user.username}" if user.username else "No username"
        draw.text((330, 80), name, font=font_big, fill="white")
        draw.text((330, 145), username, font=font, fill=(225, 232, 240))
        draw.text((70, 330), "TREBELX • PERSONAL PROFILE", font=small, fill=(230, 238, 246))
        draw.text((70, 385), f"🎵 Songs listened  •  {song_count:,}", font=font, fill="white")
        draw.text((70, 435), f"🆔 ID  •  {user_id}", font=font, fill="white")
        if not hides["coins"]:
            draw.text((70, 485), f"🪙 Coins  •  {data.get('coins', 0):,}", font=font, fill="white")
        else:
            draw.text((70, 485), "🪙 Coins  •  HIDDEN", font=font, fill=(205, 210, 220))
        if not hides["member"]:
            draw.text((70, 535), f"💎 Membership  •  {'ACTIVE' if status['membership'] else 'OFF'}", font=font, fill="white")
        if not hides["vip"]:
            draw.text((70, 585), f"👑 VIP  •  {'ACTIVE' if status['vip'] else 'OFF'}", font=font, fill="white")

        out = tmpdir / "profile.jpg"
        banner.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
        caption = "🌿 <b>蒼響 Personal Profile</b>\n\n"
        caption += f"👤 <b>Name:</b> {name}\n🔗 <b>Username:</b> {username}\n"
        caption += f"🎵 <b>Songs listened:</b> {song_count:,}\n🆔 <b>ID:</b> <code>{user_id}</code>\n"
        if not hides["coins"]: caption += f"🪙 <b>Coins:</b> {data.get('coins', 0):,}\n"
        if not hides["member"]: caption += f"💎 <b>Membership:</b> {'ACTIVE' if status['membership'] else 'OFF'}\n"
        if not hides["vip"]: caption += f"👑 <b>VIP:</b> {'ACTIVE' if status['vip'] else 'OFF'}\n"
        caption += "\nUse <code>/hide coins</code>, <code>/hide member</code> or <code>/hide vip</code> to toggle privacy."
        return await app.send_photo(chat_id, str(out), caption=caption, reply_markup=_profile_menu())
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.on_message(filters.command(["hide"]) & filters.private & ~BANNED_USERS)
async def hide_profile_field(_, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in {"coins", "member", "vip"}:
        return await message.reply_text("🌿 Use <code>/hide coins</code>, <code>/hide member</code> or <code>/hide vip</code>.")
    field = message.command[1].lower()
    hidden = await toggle_profile_hide(message.from_user.id, field)
    label = {"coins": "Coins", "member": "Membership", "vip": "VIP"}[field]
    state = "hidden" if hidden else "visible"
    await message.reply_text(f"🔒 <b>{label}</b> is now <b>{state}</b> on your profile.")


@app.on_message(filters.command(["setprofilephoto"]) & filters.private & ~BANNED_USERS)
async def set_profile_photo_command(_, message: Message):
    if not (await is_member(message.from_user.id) or await is_vip(message.from_user.id)):
        return await message.reply_text("💎 This profile feature is available to Membership and VIP users.")
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("🎨 Reply to a photo with <code>/setprofilephoto</code>.")
    await set_profile_photo(message.from_user.id, message.reply_to_message.photo.file_id)
    await message.reply_text("✨ Your profile photo was updated.")


async def _show_banner_picker(chat_id, user_id):
    is_member_user = await is_member(user_id)
    is_vip_user = await is_vip(user_id)
    rows = []
    if is_member_user or is_vip_user:
        for slot in (1, 2):
            if await get_banner(slot):
                rows.append([InlineKeyboardButton(f"🎨 Owner Banner {slot}", callback_data=f"prof:slot:{slot}")])
    if is_vip_user:
        custom = await get_custom_banners(user_id)
        for i, _ in enumerate(custom, 1):
            rows.append([InlineKeyboardButton(f"👑 My Private Banner {i}", callback_data=f"prof:custom:{i}")])
        rows.append([InlineKeyboardButton("➕ Add Private Banner", callback_data="prof:addcustom")])
    rows.append([InlineKeyboardButton("◀️ Profile", callback_data="prof:refresh")])
    return await app.send_message(chat_id, "🖼 <b>Profile Banners</b>\n\nMembership: choose from the 2 owner banners.\nVIP: owner banners + unlimited private banners.", reply_markup=InlineKeyboardMarkup(rows))


@app.on_callback_query(filters.regex(r"^prof:") & ~BANNED_USERS)
async def profile_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data.split(":")
    try: await query.answer()
    except Exception: pass
    if action[1] == "refresh":
        await query.message.delete()
        return await _send_profile(query.message.chat.id, user_id)
    if action[1] == "photo":
        return await query.message.reply_text("🎨 Reply to a photo with <code>/setprofilephoto</code>.")
    if action[1] == "banners":
        return await _show_banner_picker(query.message.chat.id, user_id)
    if action[1] == "slot" and len(action) == 3:
        if not (await is_member(user_id) or await is_vip(user_id)):
            return await query.answer("Membership required.", show_alert=True)
        slot = int(action[2])
        file_id = await get_banner(slot)
        if not file_id: return await query.answer("That banner is not available.", show_alert=True)
        await set_profile_banner(user_id, file_id)
        await query.message.reply_text(f"🎨 Owner Banner {slot} selected for your profile.")
        return
    if action[1] == "custom" and len(action) == 3:
        if not await is_vip(user_id): return await query.answer("VIP required.", show_alert=True)
        custom = await get_custom_banners(user_id)
        idx = int(action[2]) - 1
        if idx < 0 or idx >= len(custom): return await query.answer("Banner not found.", show_alert=True)
        await set_profile_banner(user_id, custom[idx])
        await query.message.reply_text("👑 Your private VIP banner is now active.")
        return
    if action[1] == "addcustom":
        if not await is_vip(user_id): return await query.answer("VIP required.", show_alert=True)
        return await query.message.reply_text("👑 Reply to a photo with <code>/setprofilebanner</code>. Every upload is saved as a private VIP banner; it is never added to the public owner banner list.")


@app.on_callback_query(filters.regex(r"^eco:") & ~BANNED_USERS)
async def economy_callback(_, query: CallbackQuery):
    user_id = query.from_user.id
    data = await get_economy(user_id)
    action = query.data.split(":")
    try:
        await query.answer()
    except Exception:
        pass

    if action[1] == "home":
        return await query.message.edit_text("🪙 <b>蒼響 Economy</b>\n\nChoose an option:", reply_markup=_menu())

    if action[1] == "history":
        from AquaVibe.utils.database import get_song_history
        rows = await get_song_history(user_id, 20)
        text = "📜 <b>Your Song History</b>\n\n" + ("\n".join(f"{i}. {r.get('title','—')[:80]}" for i,r in enumerate(rows,1)) if rows else "No songs played yet.")
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([_back()]))

    if action[1] == "playlists":
        from AquaVibe.utils.database import get_user_playlists
        pls = await get_user_playlists(user_id)
        text = "📂 <b>Your Playlists</b>\n\n" + ("\n".join(f"• <b>{p['name']}</b> — {len(p.get('tracks',[]))} tracks" for p in pls) if pls else "No playlists yet.\nUse <code>/playlist create My Playlist</code>.")
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([_back()]))

    if action[1] == "store":
        return await query.message.edit_text("🛍 <b>蒼響 Store</b>\n\nChoose a package:", reply_markup=_store())

    if action[1] == "coins":
        return await query.message.edit_text(
            f"🪙 <b>Coins</b>\n\nBalance: <b>{data.get('coins',0):,}</b>\n"
            f"Daily: +{_reward(DAILY_BASE, _extra_percent(data))}\n"
            f"Weekly: +{_reward(WEEKLY_BASE, _extra_percent(data))}.",
            reply_markup=_store(),
        )

    if action[1] == "vip":
        return await query.message.edit_text(
            "👑 <b>VIP</b>\n\n"
            "• +5% daily/weekly/referral rewards\n"
            "• Unlimited private profile banners\n\n"
            "1M ⭐50 • 3M ⭐200 • 6M ⭐400 • 1Y ⭐600",
            reply_markup=_store(),
        )

    if action[1] == "mem":
        return await query.message.edit_text(
            "💎 <b>Membership</b>\n\n"
            "• +1% daily/weekly/referral rewards\n"
            "• Choose from 2 owner profile banners\n\n"
            "1M 2,000🪙/⭐25 • 3M 6,000🪙/⭐50\n"
            "6M 10,000🪙/⭐100 • 1Y 15,000🪙/⭐200",
            reply_markup=_store(),
        )

    if action[1] == "profile":
        await query.message.delete()
        return await _send_profile(user_id, user_id)

    if action[1] == "buy" and len(action) == 3:
        plan = action[2]
        if plan in COIN_PACKS:
            coins, stars = COIN_PACKS[plan]
            payload = f"trabelx:coins:{plan}"
            await _invoice(user_id, payload, f"{coins:,} Coins", f"Purchase {coins:,} 蒼響 coins.", stars)
            return

        if plan in VIP_PACKS:
            days, stars = VIP_PACKS[plan]
            payload = f"trabelx:vip:{plan}"
            await _invoice(user_id, payload, f"VIP {days} Days", f"蒼響 VIP for {days} days.", stars)
            return

        if plan in MEMBERSHIP_PACKS:
            days, coin_price, stars = MEMBERSHIP_PACKS[plan]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🪙 Buy with {coin_price:,} coins", callback_data=f"eco:memcoin:{plan}")],
                [InlineKeyboardButton(f"⭐ Buy with {stars} Stars", callback_data=f"eco:memstars:{plan}")],
                _back(),
            ])
            return await query.message.edit_text(
                f"💎 <b>Membership {days} days</b>\n\n"
                f"Choose payment method. Your balance: <b>{data.get('coins', 0):,} coins</b>.",
                reply_markup=kb,
            )

    if action[1] == "memcoin" and len(action) == 3 and action[2] in MEMBERSHIP_PACKS:
        plan = action[2]
        days, coin_price, stars = MEMBERSHIP_PACKS[plan]
        if not await remove_coins(user_id, coin_price, "membership"):
            return await query.answer("Not enough coins.", show_alert=True)
        current = data.get("membership_until")
        start = current if current and current > _now() else _now()
        await set_membership(user_id, start + timedelta(days=days))
        return await query.message.edit_text(f"💎 Membership activated for <b>{days} days</b> using {coin_price:,} coins.")

    if action[1] == "memstars" and len(action) == 3 and action[2] in MEMBERSHIP_PACKS:
        days, coin_price, stars = MEMBERSHIP_PACKS[action[2]]
        return await _invoice(user_id, f"trabelx:mem:{action[2]}", f"Membership {days} Days", f"蒼響 Membership for {days} days.", stars)

@app.on_pre_checkout_query()
async def pre_checkout(_, query: PreCheckoutQuery):
    payload = query.invoice_payload
    parts = payload.split(":")
    valid = False
    expected = None
    if len(parts) == 3 and parts[0] == "trabelx":
        product, plan = parts[1], parts[2]
        if product == "coins" and plan in COIN_PACKS:
            expected = COIN_PACKS[plan][1]
        elif product == "vip" and plan in VIP_PACKS:
            expected = VIP_PACKS[plan][1]
        elif product == "mem" and plan in MEMBERSHIP_PACKS:
            expected = MEMBERSHIP_PACKS[plan][2]
        valid = expected == query.total_amount and query.currency == "XTR"
    await query.answer(ok=valid, error_message=None if valid else "This invoice is invalid or expired.")

@app.on_message(filters.private & ~BANNED_USERS)
async def successful_stars_payment(_, message: Message):
    payment = getattr(message, "successful_payment", None)
    if not payment:
        return
    if getattr(payment, "currency", None) != "XTR":
        return
    result = await _apply_stars_purchase(
        message.from_user.id,
        payment.invoice_payload,
        payment.total_amount,
        payment.telegram_payment_charge_id,
    )
    if result == "invalid":
        return await message.reply_text("⚠️ Payment received, but the invoice could not be verified. Contact the owner with your receipt.")
    await message.reply_text(f"✅ <b>Payment confirmed</b>\n\n{result}")


@app.on_message(filters.command(["setprofilebanner"]) & filters.private & ~BANNED_USERS)
async def set_vip_profile_banner(_, message: Message):
    if not await is_vip(message.from_user.id):
        return await message.reply_text("👑 This feature is available to VIP users.")
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("Reply to a photo with /setprofilebanner.")
    file_id = message.reply_to_message.photo.file_id
    number = await add_custom_banner(message.from_user.id, file_id)
    await set_profile_banner(message.from_user.id, file_id)
    await message.reply_text(f"👑 Private VIP banner #{number} saved and selected. It is not public.")

@app.on_chat_member_updated()
async def bot_membership_tracker(_, update):
    # Award the referral only when the bot is actually added to a group.
    chat = update.chat
    new_member = update.new_chat_member
    old_member = update.old_chat_member
    if not chat or not new_member:
        return
    if getattr(new_member, "user", None) is None or new_member.user.id != app.id:
        return

    new_status = str(getattr(new_member, "status", "")).lower()
    old_status = str(getattr(old_member, "status", "")).lower() if old_member else ""
    group_statuses = {"member", "administrator"}
    if new_status in group_statuses and old_status not in group_statuses:
        adder = getattr(update, "from_user", None)
        if not adder:
            return
        referred_by = await get_referrer(adder.id)
        if not referred_by:
            return
        if await record_group_referral(chat.id, referred_by, adder.id, _reward(REFERRAL_REWARD, _extra_percent(await get_economy(referred_by)))):
            data = await get_economy(referred_by)
            reward = _reward(REFERRAL_REWARD, _extra_percent(data))
            # The referral record stores the base reward. We add the actual
            # rewarded amount, so VIP/member bonus is also applied.
            await add_coins(referred_by, reward, "group_referral")
            try:
                await app.send_message(referred_by, f"🎉 Referral activated!\n\n+<b>{reward:,} coins</b> for the bot being added to a group.")
            except Exception:
                pass

    if new_status in {"left", "kicked"} and old_status in group_statuses:
        ref = await get_group_referral(chat.id)
        if ref and ref.get("active"):
            # Remove exactly the amount originally granted, not the current
            # bonus, so future reward changes cannot create an accounting mismatch.
            # The group record stores the exact amount that was awarded.
            await force_remove_coins(ref["inviter_id"], int(ref.get("reward", REFERRAL_REWARD)), "group_referral_removed")
