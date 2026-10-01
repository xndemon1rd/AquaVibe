"""AquaVibe Whisper -- private inline messages.

Usage (type in ANY chat's message box, nothing is posted until you tap a result)::

    @bot whisper @user your message
    @bot @user your message
    @bot your message @user
    @bot whisper @user1 @user2 your message        (up to 5 recipients)
    @bot whisper 123456789 your message            (by numeric user id)
    @bot @user +2h !burn your message              (options, see below)

Options (placed right after the recipients)::

    +10m  +2h  +1d   how long the whisper lives (1 minute .. 7 days, default 24h)
    !burn            every recipient can read it only once

Privacy model
-------------
* The chat only ever shows "Whisper for @user" -- never the text, and the text
  is never logged.
* Drafts (every keystroke fires an inline query) live in memory only.  A whisper
  is written to MongoDB only once it is actually sent (chosen inline result) or
  first opened, and only *encrypted* (Fernet).  If the ``cryptography`` package
  is missing, whispers stay memory-only instead of being stored as plaintext.
* Recipients are bound to their numeric Telegram id when the username can be
  resolved, so a later username change/re-use cannot hijack a whisper.
* Only the sender and the addressed users can open it; strangers get a polite
  refusal and the sender sees how many tried.
* Short whispers (<= 190 chars) show as a private popup.  Longer ones open in
  the bot's private chat as a protected (no forward / no save) message that
  deletes itself after a minute.
* Everything expires (Mongo TTL index + in-app check); the sender can delete a
  whisper at any time.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import re
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Optional

from pyrogram import filters
from pyrogram.enums import ParseMode
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
from AquaVibe.core.runtime import LOGGER, app

try:  # vetted crypto only; never hand-rolled
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - depends on the deployment
    Fernet = None  # type: ignore[assignment]

    class InvalidToken(Exception):  # type: ignore[no-redef]
        pass

_log = LOGGER("AquaVibe.whisper")

# ── Limits ─────────────────────────────────────────────────────────────────────
MAX_TEXT = 1000                 # characters per whisper
MAX_TARGETS = 5
DEFAULT_TTL = 24 * 3600
MIN_TTL = 60
MAX_TTL = 7 * 24 * 3600
POPUP_LIMIT = 190               # Telegram popups hold 200 chars; keep headroom
PM_DELETE_AFTER = 60            # seconds before a PM copy deletes itself
PENDING_MAX = 20000             # global cap of in-memory drafts/whispers
PENDING_PER_USER = 100
RESOLVE_PER_MIN = 8             # username lookups per sender per minute

DEEPLINK_PREFIX = "wh_"
RID_PREFIX = "wh|"
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")

_USER_RE = re.compile(r"^@([A-Za-z][A-Za-z0-9_]{4,31})$")
_ID_RE = re.compile(r"^\d{5,15}$")
_DUR_RE = re.compile(r"^\+(\d{1,4})([mhd])$", re.I)

USAGE = (
    "🔒 <b>Private whisper</b>\n"
    "Type in any chat:\n"
    "<code>@{bot} whisper @user your message</code>\n"
    "<code>@{bot} your message @user</code>\n\n"
    "Options: <code>+30m</code> <code>+2h</code> <code>+1d</code> (expiry), "
    "<code>!burn</code> (each person reads it once). Up to 5 recipients."
)


# ═══════════════════════════════════════════════════════════════════════════════
# Parsing (pure functions -- unit tested)
# ═══════════════════════════════════════════════════════════════════════════════
class Parsed:
    __slots__ = ("targets", "text", "ttl", "burn", "error")

    def __init__(self):
        self.targets: list[dict] = []   # {"id": int|None, "username": str|None}
        self.text: str = ""
        self.ttl: int = DEFAULT_TTL
        self.burn: bool = False
        self.error: Optional[str] = None


def _target_from(token: str, allow_id: bool) -> Optional[dict]:
    m = _USER_RE.match(token)
    if m:
        return {"id": None, "username": m.group(1).lower()}
    if allow_id and _ID_RE.match(token):
        return {"id": int(token), "username": None}
    return None


def _same_target(a: dict, b: dict) -> bool:
    return (a["id"] is not None and a["id"] == b["id"]) or (
        a["username"] is not None and a["username"] == b["username"]
    )


def parse_query(raw: str) -> Optional[Parsed]:
    """Return a Parsed whisper, or None when the query is not a whisper at all."""
    q = (raw or "").strip()
    if not q:
        return None
    tokens = q.split()
    keyword = tokens[0].lower() == "whisper"
    if keyword:
        tokens = tokens[1:]
    if not tokens:
        p = Parsed()
        p.error = "usage"
        return p

    p = Parsed()
    # 1) leading recipients
    i = 0
    while i < len(tokens) and len(p.targets) < MAX_TARGETS + 1:
        t = _target_from(tokens[i], allow_id=keyword)
        if not t:
            break
        if not any(_same_target(t, x) for x in p.targets):
            p.targets.append(t)
        i += 1
    rest = tokens[i:]

    # 2) trailing recipient ("hi @user") when nothing led the query
    if not p.targets and rest:
        t = _target_from(rest[-1], allow_id=keyword)
        if t:
            p.targets.append(t)
            rest = rest[:-1]

    if not p.targets:
        # Without the keyword this is just some other inline query.
        if not keyword:
            return None
        p.error = "no_target"
        return p
    if len(p.targets) > MAX_TARGETS:
        p.error = "too_many"
        p.targets = p.targets[:MAX_TARGETS]
        return p

    # 3) options directly after the recipients
    while rest:
        tok = rest[0]
        d = _DUR_RE.match(tok)
        if d:
            unit = {"m": 60, "h": 3600, "d": 86400}[d.group(2).lower()]
            p.ttl = max(MIN_TTL, min(MAX_TTL, int(d.group(1)) * unit))
            rest = rest[1:]
        elif tok.lower() in ("!burn", "!once"):
            p.burn = True
            rest = rest[1:]
        else:
            break

    p.text = " ".join(rest).strip()
    if not p.text:
        p.error = "no_text"
    elif len(p.text) > MAX_TEXT:
        p.error = "too_long"
    return p


def fmt_duration(seconds: int) -> str:
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    return f"{max(1, seconds // 60)}m"


# ═══════════════════════════════════════════════════════════════════════════════
# Encryption at rest
# ═══════════════════════════════════════════════════════════════════════════════
_FERNET = None
_FERNET_READY = False


def _fernet():
    """Fernet bound to a key derived from WHISPER_SECRET (or the bot token)."""
    global _FERNET, _FERNET_READY
    if _FERNET_READY:
        return _FERNET
    _FERNET_READY = True
    if Fernet is None:
        _log.warning(
            "`cryptography` is not installed: whispers stay in memory only and are LOST on restart. "
            "Fix: pip install -r requirements.txt (or pip install cryptography)."
        )
        return None
    secret = (getattr(config, "WHISPER_SECRET", "") or "").strip() or str(config.BOT_TOKEN)
    digest = hashlib.sha256(b"aquavibe-whisper-v2|" + secret.encode("utf-8")).digest()
    _FERNET = Fernet(base64.urlsafe_b64encode(digest))
    return _FERNET


def seal(token: str, text: str) -> Optional[str]:
    f = _fernet()
    if f is None:
        return None
    payload = json.dumps({"t": token, "x": text}, ensure_ascii=False).encode("utf-8")
    return f.encrypt(payload).decode("ascii")


def unseal(token: str, blob: str) -> Optional[str]:
    f = _fernet()
    if f is None or not blob:
        return None
    try:
        data = json.loads(f.decrypt(blob.encode("ascii")).decode("utf-8"))
    except (InvalidToken, ValueError):
        return None
    # The token is inside the ciphertext: a blob copied onto another record is rejected.
    if data.get("t") != token:
        return None
    return data.get("x")


# ═══════════════════════════════════════════════════════════════════════════════
# Storage: in-memory pending cache + encrypted Mongo persistence
# ═══════════════════════════════════════════════════════════════════════════════
WH = mongodb.aqua_whispers_v2
_PENDING: "OrderedDict[str, dict]" = OrderedDict()   # token -> doc (plaintext, memory only)
_PER_USER: dict[int, list[str]] = {}
_PERSISTED: set[str] = set()
_INDEX_READY = False


def _now() -> float:
    return time.time()


def _new_doc(sender_id: int, parsed: Parsed, targets: list[dict]) -> dict:
    now = _now()
    return {
        "token": uuid.uuid4().hex,
        "sender_id": int(sender_id),
        "targets": targets,
        "text": parsed.text,
        "burn": bool(parsed.burn),
        "ttl": int(parsed.ttl),
        "created_at": now,
        "expires_at": now + parsed.ttl,
        "opened_by": [],
        "snoops": 0,
    }


def _remember(doc: dict) -> None:
    tok, uid = doc["token"], doc["sender_id"]
    _PENDING[tok] = doc
    mine = _PER_USER.setdefault(uid, [])
    mine.append(tok)
    while len(mine) > PENDING_PER_USER:
        _PENDING.pop(mine.pop(0), None)
    while len(_PENDING) > PENDING_MAX:
        old_tok, old = _PENDING.popitem(last=False)
        lst = _PER_USER.get(old["sender_id"])
        if lst and old_tok in lst:
            lst.remove(old_tok)


def _forget(token: str) -> None:
    doc = _PENDING.pop(token, None)
    _PERSISTED.discard(token)
    if doc:
        lst = _PER_USER.get(doc["sender_id"])
        if lst and token in lst:
            lst.remove(token)


def _purge_expired_pending() -> None:
    now = _now()
    for tok in [t for t, d in _PENDING.items() if d["expires_at"] < now]:
        _forget(tok)


async def _ensure_index() -> None:
    global _INDEX_READY
    if _INDEX_READY:
        return
    _INDEX_READY = True
    try:
        await WH.create_index("expire_dt", expireAfterSeconds=0)
        await WH.create_index("token", unique=True)
    except Exception as exc:
        _log.warning("Whisper index setup failed: %s", type(exc).__name__)


def _to_record(doc: dict) -> Optional[dict]:
    """Database form of a doc: encrypted text, no plaintext. None if we cannot encrypt."""
    blob = seal(doc["token"], doc["text"])
    if blob is None:
        return None
    rec = {k: v for k, v in doc.items() if k != "text"}
    rec["blob"] = blob
    rec["expire_dt"] = datetime.fromtimestamp(doc["expires_at"], tz=timezone.utc)
    return rec


async def persist(doc: dict) -> bool:
    """Write (upsert) a whisper, encrypted. Returns False when it stays memory-only."""
    rec = _to_record(doc)
    if rec is None:
        return False
    try:
        await _ensure_index()
        await WH.update_one({"token": doc["token"]}, {"$set": rec}, upsert=True)
        _PERSISTED.add(doc["token"])
        return True
    except Exception as exc:
        _log.warning("Whisper save failed: %s", type(exc).__name__)
        return False


async def load(token: str) -> Optional[dict]:
    """Fetch a whisper (memory first, then the database). Expired ones are removed."""
    if not _TOKEN_RE.match(token or ""):
        return None
    doc = _PENDING.get(token)
    if doc is None:
        try:
            rec = await WH.find_one({"token": token})
        except Exception as exc:
            _log.warning("Whisper load failed: %s", type(exc).__name__)
            return None
        if not rec:
            return None
        text = unseal(token, rec.get("blob", ""))
        if text is None:
            return None
        doc = {k: v for k, v in rec.items() if k not in ("_id", "blob", "expire_dt")}
        doc["text"] = text
    if float(doc.get("expires_at", 0)) < _now():
        await destroy(token)
        return None
    return doc


async def destroy(token: str) -> None:
    _forget(token)
    try:
        await WH.delete_one({"token": token})
    except Exception as exc:
        _log.warning("Whisper delete failed: %s", type(exc).__name__)


async def save_state(doc: dict) -> None:
    """Persist mutable state (opened_by / snoops) without re-sending the text."""
    tok = doc["token"]
    if tok in _PERSISTED:
        try:
            await WH.update_one(
                {"token": tok},
                {"$set": {"opened_by": doc["opened_by"], "snoops": doc["snoops"]}},
            )
        except Exception as exc:
            _log.warning("Whisper state save failed: %s", type(exc).__name__)
    else:
        await persist(doc)  # first real interaction: store it (encrypted)


# ═══════════════════════════════════════════════════════════════════════════════
# Recipients
# ═══════════════════════════════════════════════════════════════════════════════
_RESOLVED: dict[str, tuple[float, tuple[str, Optional[Any]]]] = {}
_RESOLVE_LOG: dict[int, list[float]] = {}
_RESOLVE_PAUSE_UNTIL = 0.0


def _resolve_allowed(sender_id: int) -> bool:
    now = _now()
    if now < _RESOLVE_PAUSE_UNTIL:
        return False
    log = [t for t in _RESOLVE_LOG.get(sender_id, []) if now - t < 60]
    _RESOLVE_LOG[sender_id] = log
    if len(log) >= RESOLVE_PER_MIN:
        return False
    log.append(now)
    return True


async def resolve_username(client, username: str, sender_id: int) -> tuple[str, Optional[Any]]:
    """('ok', user) | ('notfound', None) | ('bot', user) | ('unknown', None)."""
    global _RESOLVE_PAUSE_UNTIL
    hit = _RESOLVED.get(username)
    if hit and hit[0] > _now():
        return hit[1]
    if not _resolve_allowed(sender_id):
        return ("unknown", None)
    from pyrogram.errors import BadRequest, FloodWait

    try:
        user = await asyncio.wait_for(client.get_users(username), timeout=4)
    except FloodWait as fw:
        _RESOLVE_PAUSE_UNTIL = _now() + min(int(getattr(fw, "value", 30) or 30), 300)
        return ("unknown", None)
    except BadRequest:
        res: tuple[str, Optional[Any]] = ("notfound", None)
        _RESOLVED[username] = (_now() + 120, res)
        return res
    except Exception:
        return ("unknown", None)
    if isinstance(user, list):
        user = user[0] if user else None
    if user is None or not hasattr(user, "id"):
        res = ("notfound", None)
    elif getattr(user, "is_bot", False):
        res = ("bot", user)
    else:
        res = ("ok", user)
    _RESOLVED[username] = (_now() + 600, res)
    if len(_RESOLVED) > 5000:
        _RESOLVED.clear()
    return res


def is_recipient(doc: dict, user) -> bool:
    uid = int(user.id)
    uname = (getattr(user, "username", None) or "").lower()
    for t in doc["targets"]:
        if t.get("id") is not None and int(t["id"]) == uid:
            return True
        # Bound-by-id targets are never matched by username (anti username re-use).
        if t.get("id") is None and t.get("username") and uname and t["username"] == uname:
            return True
    return False


def target_label(t: dict) -> str:
    if t.get("username"):
        return "@" + html.escape(t["username"])
    return f"<code>{int(t['id'])}</code>"


# ═══════════════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════════════
def public_text(doc: dict, state: str = "sent") -> str:
    names = ", ".join(target_label(t) for t in doc["targets"])
    flags = [f"⏳ {fmt_duration(int(doc['ttl']))}"]
    if doc.get("burn"):
        flags.append("🔥 burn after reading")
    lines = [f"🔒 <b>Private whisper for {names}</b>"]
    if state == "deleted":
        return "🗑 <i>This whisper was deleted by its sender.</i>"
    if state == "expired":
        return "⌛ <i>This whisper has expired.</i>"
    if state == "burned":
        return "🔥 <i>This whisper was read by everyone it was meant for and has burned.</i>"
    opened = len(doc.get("opened_by", [])) - (1 if doc["sender_id"] in doc.get("opened_by", []) else 0)
    lines.append("<i>Only the sender and the addressed user can open it.</i>")
    lines.append(" · ".join(flags))
    if opened > 0:
        lines.append(f"👁 Opened by {opened}/{len(doc['targets'])}")
    return "\n".join(lines)


def public_markup(token: str, doc: Optional[dict] = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🔓 Open whisper", callback_data=f"WH:{token}"),
            InlineKeyboardButton("🗑", callback_data=f"WHD:{token}"),
        ]]
    )


def _hint(query_id_seed: str, title: str, description: str, body: str) -> InlineQueryResultArticle:
    rid = "whh|" + hashlib.md5(query_id_seed.encode("utf-8")).hexdigest()[:12]
    return InlineQueryResultArticle(
        id=rid,
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(body, parse_mode=ParseMode.HTML),
    )


def _bot_username() -> str:
    """Real username of the running bot (the BOT_USERNAME env var may be stale/default)."""
    return str(getattr(app, "username", None) or config.BOT_USERNAME).lstrip("@")


def _usage_body() -> str:
    return USAGE.format(bot=html.escape(_bot_username()))


# ═══════════════════════════════════════════════════════════════════════════════
# Inline query
# ═══════════════════════════════════════════════════════════════════════════════
_HINTS = {
    "usage": ("🔒 Whisper", "Add @username and your message"),
    "no_target": ("🔒 Who is it for?", "Add @username (or a numeric id) after 'whisper'"),
    "no_text": ("✍️ Type your message", "Your whisper text goes after the @username"),
    "too_many": (f"⚠️ Max {MAX_TARGETS} recipients", "Remove a few @usernames"),
    "too_long": (f"⚠️ Too long (max {MAX_TEXT})", "Shorten the message"),
}


async def build_results(client, query) -> Optional[list]:
    """Results for an inline query, or None when it is not a whisper query."""
    parsed = parse_query(query.query)
    if parsed is None:
        return None
    seed = query.query
    if parsed.error:
        title, desc = _HINTS[parsed.error]
        return [_hint(seed, title, desc, _usage_body())]

    sender_id = int(query.from_user.id)
    targets: list[dict] = []
    for t in parsed.targets:
        if t["username"]:
            status, user = await resolve_username(client, t["username"], sender_id)
            if status == "notfound":
                return [_hint(seed, f"❌ @{t['username']} not found",
                              "Check the username and try again", _usage_body())]
            if status == "bot":
                return [_hint(seed, f"🤖 @{t['username']} is a bot",
                              "Bots cannot open whispers", _usage_body())]
            if status == "ok":
                if int(user.id) == sender_id:
                    return [_hint(seed, "🙃 That's you", "Whisper to someone else", _usage_body())]
                t = {"id": int(user.id), "username": t["username"]}
        elif t["id"] == sender_id:
            return [_hint(seed, "🙃 That's you", "Whisper to someone else", _usage_body())]
        if not any(_same_target(t, x) for x in targets):
            targets.append(t)

    _purge_expired_pending()
    doc = _new_doc(sender_id, parsed, targets)
    _remember(doc)
    names = ", ".join(("@" + t["username"]) if t.get("username") else str(t["id"]) for t in targets)
    bits = [f"{len(parsed.text)} chars", f"⏳ {fmt_duration(parsed.ttl)}"]
    if parsed.burn:
        bits.append("🔥 burn")
    return [
        InlineQueryResultArticle(
            id=RID_PREFIX + doc["token"],
            title=f"🔒 Whisper → {names}",
            description=" · ".join(bits) + " · only they can read it",
            input_message_content=InputTextMessageContent(
                public_text(doc), parse_mode=ParseMode.HTML
            ),
            reply_markup=public_markup(doc["token"]),
        )
    ]


async def whisper_inline(client, query) -> bool:
    """Handle a whisper inline query. Returns True when it answered."""
    results = await build_results(client, query)
    if results is None:
        return False
    # Personal + no cache: every result carries a unique secret token.
    await query.answer(results, cache_time=0, is_personal=True)
    return True


async def handle_chosen(client, chosen) -> None:
    rid = getattr(chosen, "result_id", "") or ""
    if not rid.startswith(RID_PREFIX):
        return
    token = rid[len(RID_PREFIX):]
    doc = _PENDING.get(token)
    if doc is None or int(chosen.from_user.id) != doc["sender_id"]:
        return
    await persist(doc)


@app.on_chosen_inline_result(group=7)
async def whisper_chosen(client, chosen):
    """Runs only when inline feedback is enabled in BotFather (/setinlinefeedback)."""
    await handle_chosen(client, chosen)


# ═══════════════════════════════════════════════════════════════════════════════
# Open / revoke
# ═══════════════════════════════════════════════════════════════════════════════
def _deep_link(token: str) -> str:
    return f"https://t.me/{_bot_username()}?start={DEEPLINK_PREFIX}{token}"


async def _refresh_public(cb: CallbackQuery, doc: dict, state: str = "sent") -> None:
    """Update the shared chat message (status only -- never the text)."""
    if not getattr(cb, "inline_message_id", None):
        return
    markup = None if state in ("deleted", "expired", "burned") else public_markup(doc["token"])
    try:
        await cb.edit_message_text(public_text(doc, state), parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception:
        pass  # message not editable / unchanged: harmless


_LOCKS: dict[str, asyncio.Lock] = {}


def _lock(token: str) -> asyncio.Lock:
    lk = _LOCKS.get(token)
    if lk is None:
        if len(_LOCKS) > 5000:
            for k in [k for k, v in _LOCKS.items() if not v.locked()]:
                _LOCKS.pop(k, None)
        lk = _LOCKS[token] = asyncio.Lock()
    return lk


def _all_read(doc: dict) -> bool:
    read = {u for u in doc.get("opened_by", []) if u != doc["sender_id"]}
    return len(read) >= len(doc["targets"])


async def _consume(doc: dict, user_id: int) -> None:
    """Record a read; burn-after-reading whispers disappear once every recipient has read."""
    if user_id not in doc["opened_by"]:
        doc["opened_by"].append(user_id)
    if doc.get("burn") and _all_read(doc):
        await destroy(doc["token"])
    else:
        await save_state(doc)


async def handle_open(client, cb: CallbackQuery) -> None:
    token = cb.data.split(":", 1)[1] if cb.data and ":" in cb.data else ""
    if not _TOKEN_RE.match(token):
        return await cb.answer("⌛ This whisper has expired or no longer exists.", show_alert=True)
    async with _lock(token):
        await _open_locked(client, cb, token)


async def _open_locked(client, cb: CallbackQuery, token: str) -> None:
    doc = await load(token)
    if doc is None:
        return await cb.answer("⌛ This whisper has expired or no longer exists.", show_alert=True)

    user = cb.from_user
    uid = int(user.id)

    if uid == doc["sender_id"]:
        preview = doc["text"] if len(doc["text"]) <= 120 else doc["text"][:117] + "…"
        opened = len([u for u in doc.get("opened_by", []) if u != uid])
        extra = f"\n\n👁 {opened}/{len(doc['targets'])} opened"
        if doc.get("snoops"):
            extra += f" · 🚫 {doc['snoops']} blocked"
        return await cb.answer(("📤 You wrote:\n" + preview + extra)[:200], show_alert=True, cache_time=0)

    if not is_recipient(doc, user):
        doc["snoops"] = int(doc.get("snoops", 0)) + 1
        await save_state(doc)
        return await cb.answer("🔒 This whisper isn't for you.", show_alert=True, cache_time=0)

    # Bind username-only targets to the real id on first successful open.
    for t in doc["targets"]:
        if t.get("id") is None and t.get("username") and t["username"] == (user.username or "").lower():
            t["id"] = uid

    if doc.get("burn") and uid in doc["opened_by"]:
        return await cb.answer("🔥 You already read this burn-after-reading whisper.", show_alert=True, cache_time=0)

    if len(doc["text"]) <= POPUP_LIMIT:
        await cb.answer("💌 " + doc["text"], show_alert=True, cache_time=0)
        await _consume(doc, uid)
        await _refresh_public(cb, doc, "burned" if doc.get("burn") and _all_read(doc) else "sent")
        return

    # Long text: popups are capped by Telegram, so continue in the bot's private chat.
    await save_state(doc)
    await cb.answer(url=_deep_link(token), cache_time=0)


async def handle_delete(client, cb: CallbackQuery) -> None:
    token = cb.data.split(":", 1)[1] if cb.data and ":" in cb.data else ""
    if not _TOKEN_RE.match(token):
        return await cb.answer("This whisper is already gone.", show_alert=True)
    async with _lock(token):
        doc = await load(token)
        if doc is None:
            return await cb.answer("This whisper is already gone.", show_alert=True)
        if int(cb.from_user.id) != doc["sender_id"]:
            return await cb.answer("Only the sender can delete this whisper.", show_alert=True, cache_time=0)
        await destroy(token)
    await cb.answer("🗑 Whisper deleted.", cache_time=0)
    await _refresh_public(cb, doc, "deleted")


@app.on_callback_query(filters.regex(r"^WH:[0-9a-f]{32}$"))
async def whisper_open_cb(client, cb: CallbackQuery):
    await handle_open(client, cb)


@app.on_callback_query(filters.regex(r"^WHD:[0-9a-f]{32}$"))
async def whisper_delete_cb(client, cb: CallbackQuery):
    await handle_delete(client, cb)


# ═══════════════════════════════════════════════════════════════════════════════
# Private-chat delivery for long whispers (t.me/bot?start=wh_<token>)
# ═══════════════════════════════════════════════════════════════════════════════
async def _auto_delete(msg, seconds: int) -> None:
    await asyncio.sleep(seconds)
    try:
        await msg.delete()
    except Exception:
        pass


async def handle_start_link(client, message: Message) -> None:
    parts = (message.text or "").split(None, 1)
    param = parts[1].strip() if len(parts) > 1 else ""
    token = param[len(DEEPLINK_PREFIX):]
    if not _TOKEN_RE.match(token):
        return await message.reply_text("⌛ This whisper has expired or no longer exists.")
    async with _lock(token):
        doc = await load(token)
        if doc is None:
            return await message.reply_text("⌛ This whisper has expired or no longer exists.")
        user = message.from_user
        uid = int(user.id)
        is_sender = uid == doc["sender_id"]
        if not is_sender and not is_recipient(doc, user):
            doc["snoops"] = int(doc.get("snoops", 0)) + 1
            await save_state(doc)
            return await message.reply_text("🔒 This whisper isn't for you.")
        if not is_sender:
            for t in doc["targets"]:
                if t.get("id") is None and t.get("username") and t["username"] == (user.username or "").lower():
                    t["id"] = uid
            if doc.get("burn") and uid in doc["opened_by"]:
                return await message.reply_text("🔥 You already read this burn-after-reading whisper.")

        body = (
            f"💌 <b>Whisper</b>\n\n{html.escape(doc['text'])}\n\n"
            f"<i>🛡 Protected · deletes itself in {PM_DELETE_AFTER}s</i>"
        )
        sent = await client.send_message(
            message.chat.id, body, parse_mode=ParseMode.HTML, protect_content=True,
        )
        asyncio.ensure_future(_auto_delete(sent, PM_DELETE_AFTER))
        asyncio.ensure_future(_auto_delete(message, PM_DELETE_AFTER))  # the /start line too
        if not is_sender:
            await _consume(doc, uid)


@app.on_message(
    filters.command("start") & filters.private
    & filters.regex(r"^/start(?:@\w+)?\s+wh_[0-9a-f]{32}\s*$"),
    group=-5,
)
async def whisper_start_cb(client, message: Message):
    # Runs before the normal /start (which may show the first-time gender menu).
    try:
        await handle_start_link(client, message)
    except Exception as exc:
        _log.warning("Whisper deep-link failed: %s: %s", type(exc).__name__, exc)
    message.stop_propagation()
