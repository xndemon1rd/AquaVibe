"""Aqua's lightweight companion engine.

Inspired by the *architecture* of Her-go and PersonaWeave, not copied source:
per-user memory, PAD-style mood, relationship state, Big-Five/value traits,
reflection, and gradual personality drift. MongoDB keeps the state persistent.
"""
from __future__ import annotations

import math
import re
import time
from datetime import datetime, timezone
from typing import Any

from AquaVibe.utils import emotion_engine as ee

from AquaVibe.core.mongo import mongodb
from config import OWNER_ID

DB = mongodb.aqua_persona

DEFAULT_TRAITS = {
    "openness": 0.72,
    "conscientiousness": 0.62,
    "extraversion": 0.68,
    "agreeableness": 0.78,
    "neuroticism": 0.38,
}
DEFAULT_VALUES = ["loyalty", "honesty", "kindness", "humor", "curiosity"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


async def ensure(user_id: int, name: str | None = None) -> dict:
    uid = int(user_id)
    now = _now()
    defaults = {
        "user_id": uid,
        "name": str(name or "Friend")[:80],
        "traits": dict(DEFAULT_TRAITS),
        "values": list(DEFAULT_VALUES),
        # PAD: pleasure, arousal, dominance. Kept in [-1, 1].
        "pad": {"pleasure": 0.25, "arousal": 0.05, "dominance": 0.10},
        "emotion": "neutral",      # the USER's last detected emotion
        "mood": "content",         # Aqua's own mood label
        "emo_hist": [],            # [[ts, emotion, intensity], ...] last 24
        "followups": [],           # [{"topic": str, "ts": float}]
        "style": {"len": 60.0, "emoji": 0.3},
        "last_crisis_at": None,
        "affinity": 0.20,
        "intimacy": 0.05,
        "trust": 0.25,
        "memories": [],
        "reflections": [],
        "turns": 0,
        "last_dream": None,
        "updated_at": now,
    }
    # A path may appear in only one update operator: "name" in both $setOnInsert and $set
    # makes MongoDB reject the update ("Updating the path 'name' would create a conflict").
    # A real name is refreshed via $set; with no name given (e.g. dream_if_due) an existing
    # name is left alone instead of being overwritten with "Friend".
    update: dict = {}
    if name:
        update["$set"] = {"name": str(name)[:80]}
        insert_defaults = {k: v for k, v in defaults.items() if k != "name"}
    else:
        insert_defaults = defaults
    update["$setOnInsert"] = insert_defaults
    await DB.update_one({"user_id": uid}, update, upsert=True)
    return await DB.find_one({"user_id": uid}) or defaults


_BASE_PAD = {"pleasure": 0.25, "arousal": 0.05, "dominance": 0.10}
_HALF_LIFE_H = 6.0            # mood drifts back to baseline with this half-life
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2764]")


def _aware(dt):
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _hours_since(dt) -> float:
    dt = _aware(dt)
    return max(0.0, (_now() - dt).total_seconds() / 3600.0) if dt else 0.0


def _decay_pad(pad: dict, hours: float) -> dict:
    """Pull PAD back toward baseline: exp decay, half-life ~6h."""
    k = 0.5 ** (hours / _HALF_LIFE_H) if hours > 0 else 1.0
    return {key: _clamp(_BASE_PAD[key] + (float((pad or {}).get(key, _BASE_PAD[key])) - _BASE_PAD[key]) * k) for key in _BASE_PAD}


def _mood_label(pad: dict, user: "ee.Reading") -> str:
    """Aqua's own mood: empathic reaction to the user first, then PAD."""
    if user.crisis:
        return "deeply concerned"
    if user.sensitivity >= 2:
        return "gentle and present"
    if user.emotion in {"sadness", "fear"} and user.intensity >= 0.35:
        return "concerned"
    if user.emotion == "anger" and user.intensity >= 0.4:
        return "calm and steady"
    if user.emotion in {"joy", "laugh"} and user.intensity >= 0.4:
        return "cheerful"
    if user.emotion == "love":
        return "warm"
    if user.emotion == "gratitude":
        return "pleased"
    if user.emotion == "tired":
        return "soft and sleepy"
    p, a = float(pad.get("pleasure", 0)), float(pad.get("arousal", 0))
    if p > 0.5:
        return "excited" if a > 0.3 else "happy"
    if p > 0.2:
        return "content"
    if p < -0.25:
        return "subdued"
    return "calm"


_EVENT_A = re.compile(
    r"\b(?:i have|i've got|i got|i'm having|my|mera|meri|mere)\b[^.!?\n]{0,40}?\b(exam|test|interview|presentation|surgery|appointment|results?|match|viva|trip|flight|wedding|date|audition|deadline)\b"
    r"[^.!?\n]{0,40}?\b(tomorrow|today|tonight|next week|this weekend|kal|aaj|parso|agle hafte|on (?:mon|tues|wednes|thurs|fri|satur|sun)day)\b",
    re.I,
)
_EVENT_B = re.compile(
    r"\b(tomorrow|tonight|next week|this weekend|kal|parso|agle hafte)\b[^.!?\n]{0,40}?\b(?:i have|i've got|i'm having|mera|meri|mere)\b[^.!?\n]{0,30}?\b(exam|test|interview|presentation|surgery|appointment|results?|match|viva|trip|flight|wedding|date|audition|deadline)\b",
    re.I,
)
_UNWELL = re.compile(r"\b(?:i(?:'m| am) (?:sick|ill|unwell)|i have (?:a )?(?:fever|cold|headache|flu|stomach ache)|mujhe bukhar|bimar hoon|bimaar hoon|tabiyat theek nahi)\b|तबीयत ठीक नहीं|बुखार", re.I)


def _extract_memories(text: str) -> list[str]:
    t = " ".join((text or "").split())[:700]
    patterns = [
        r"\bmy name is ([A-Za-z][\w'-]{1,30}(?: [A-Z][\w'-]{1,20})?)",
        r"\bcall me ([A-Za-z][\w'-]{1,30}(?: [A-Z][\w'-]{1,20})?)",
        r"\bi(?:'m| am) from ([A-Za-z][\w'-]{1,30}(?:,? [A-Z][\w'-]{1,20}){0,2})",
        r"\bi live in ([A-Za-z][\w'-]{1,30}(?:,? [A-Z][\w'-]{1,20}){0,2})",
        r"\bi (?:like|love) ([^.!?]{2,100})",
        r"\bi (?:hate|dislike) ([^.!?]{2,100})",
        r"\bmy favou?rite (?:song|movie|anime|game|food|color|colour|band|singer|subject) is ([^.!?]{2,100})",
        r"\bmy (?:birthday|bday) is (?:on )?([^.!?]{2,40})",
        r"\bi (?:work as|work at|work in) ([^.!?]{2,60})",
        r"\bi(?:'m| am) (?:studying|a student of|in class|in grade) ([^.!?]{2,60})",
        r"\bmy (?:dog|cat|pet|parrot|puppy|kitten)(?:'s name)? is (?:named |called )?([A-Za-z][\w .'-]{1,30})",
        r"\bmera naam ([A-Za-z][\w .'-]{1,40}) hai",
        r"\bmain ([A-Za-z][\w .,'-]{1,40}) se hoon",
    ]
    out: list[str] = []
    for p in patterns:
        m = re.search(p, t, re.I)
        if m:
            value = re.sub(r"\s+(?:and|but|so|because|since|though|while|aur|lekin|par)\b.*$", "", m.group(0).strip(), flags=re.I).strip(" ,.;")
            if value and value not in out:
                out.append(value[:300])
    return out[:4]


def _extract_followup(text: str) -> str | None:
    t = " ".join((text or "").split())[:400]
    for rx in (_EVENT_A, _EVENT_B):
        m = rx.search(t)
        if m:
            return m.group(0)[:120]
    if _UNWELL.search(t):
        return "not feeling well"
    return None


def _style_hint(style: dict) -> str:
    ln, em = float(style.get("len", 60)), float(style.get("emoji", 0.3))
    parts = []
    if ln < 35:
        parts.append("they write short messages -- keep your replies brief")
    elif ln > 220:
        parts.append("they write long, detailed messages -- a fuller reply is welcome")
    if em > 1.2:
        parts.append("they use lots of emoji -- a couple of emoji are welcome")
    elif em < 0.05:
        parts.append("they hardly ever use emoji -- keep emoji minimal")
    return ("Style match: " + "; ".join(parts) + ".") if parts else ""


def _trend_hint(hist: list, doc: dict) -> str:
    now = time.time()
    recent = [h for h in (hist or []) if len(h) >= 3 and now - float(h[0]) < 3 * 86400][-8:]
    notes = []
    if len(recent) >= 4:
        neg = sum(1 for h in recent if h[1] in {"sadness", "fear", "anger"} and float(h[2]) >= 0.3)
        pos = sum(1 for h in recent if h[1] in {"joy", "laugh", "love", "gratitude"} and float(h[2]) >= 0.3)
        if neg >= 3 and neg > pos:
            notes.append("Over the last few days they have seemed low or stressed -- be a little extra caring and, only if it fits, check in softly (do not dramatise).")
        elif pos >= 4 and neg == 0:
            notes.append("They have been in a good mood lately -- enjoy it with them.")
    return " ".join(notes)


async def process_turn(user_id: int, name: str, text: str, *, sticker_emoji: str = "") -> dict:
    """Read the message, update mood/relationship/memory and return the state.

    The returned dict also carries transient (not persisted) keys:
    ``_reading`` (emotion_engine.Reading), ``_due`` (follow-up topics to raise),
    ``_gap_h`` (hours since last chat), ``_stage`` and ``_trend``.
    """
    doc = await ensure(user_id, name)
    now_ts = time.time()
    gap_h = _hours_since(doc.get("updated_at")) if int(doc.get("turns", 0)) > 0 else 0.0
    reading = ee.analyze(text, sticker_emoji=sticker_emoji)

    # --- mood: decay toward baseline, then empathic contagion (damped) ---
    pad = _decay_pad(doc.get("pad") or {}, gap_h)
    pad["pleasure"] = _clamp(pad["pleasure"] * 0.96 + 0.30 * reading.valence * max(reading.intensity, 0.2) * (0.5 if reading.valence < 0 else 1.0))
    pad["arousal"] = _clamp(pad["arousal"] * 0.94 + 0.20 * reading.arousal * max(reading.intensity, 0.2))
    pad["dominance"] = _clamp(pad["dominance"] * 0.98 + (-0.04 if reading.emotion == "anger" else 0.0))
    mood = _mood_label(pad, reading)

    # --- relationship ---
    emo = reading.emotion
    d_aff = 0.018 if emo in {"joy", "love", "laugh", "gratitude"} else 0.006 if emo in {"neutral", "greeting", "thinking"} else 0.008 if emo == "apology" else -0.006 if emo == "anger" else 0.004
    d_trust = 0.012 if emo in {"love", "gratitude", "apology"} else 0.010 if reading.tender and emo != "anger" else -0.004 if emo == "anger" else 0.002
    memories = [] if reading.sensitivity >= 2 else _extract_memories(text)
    affinity = _clamp(float(doc.get("affinity", 0.2)) + d_aff)
    trust = _clamp(float(doc.get("trust", 0.25)) + d_trust)
    intimacy = _clamp(float(doc.get("intimacy", 0.05)) + (0.008 if memories else 0.012 if reading.tender and emo != "anger" else 0.002))

    # --- slow personality drift ---
    traits = dict(DEFAULT_TRAITS)
    traits.update(doc.get("traits") or {})
    if emo in {"joy", "love", "laugh"}:
        traits["agreeableness"] = _clamp(float(traits["agreeableness"]) + 0.002, 0, 1)
        traits["extraversion"] = _clamp(float(traits["extraversion"]) + 0.001, 0, 1)
    if emo in {"anger", "fear"}:
        traits["neuroticism"] = _clamp(float(traits["neuroticism"]) + 0.001, 0, 1)

    # --- emotion history, style, follow-ups ---
    hist = list(doc.get("emo_hist") or [])
    trend = _trend_hint(hist, doc)
    style = dict(doc.get("style") or {"len": 60.0, "emoji": 0.3})
    if text:
        style["len"] = round(float(style.get("len", 60.0)) * 0.85 + len(text) * 0.15, 1)
        style["emoji"] = round(float(style.get("emoji", 0.3)) * 0.85 + len(_EMOJI_RE.findall(text)) * 0.15, 3)

    followups = [f for f in (doc.get("followups") or []) if isinstance(f, dict) and now_ts - float(f.get("ts", 0)) < 10 * 86400]
    due, keep = [], []
    for f in followups:
        age_h = (now_ts - float(f.get("ts", 0))) / 3600.0
        topic = str(f.get("topic", ""))
        if topic == "__checkin__":
            (due if 6 <= age_h < 7 * 24 else keep).append(f)
        else:
            (due if 3 <= age_h < 6 * 24 else keep).append(f)
    if reading.serious:
        due = []                       # never raise old topics in the middle of a heavy moment
        keep = followups
    new_follow = None if reading.crisis else _extract_followup(text)
    if new_follow:
        keep.append({"topic": new_follow, "ts": now_ts})
    if reading.crisis:
        keep = [f for f in keep if f.get("topic") != "__checkin__"] + [{"topic": "__checkin__", "ts": now_ts}]

    update: dict[str, Any] = {
        "name": str(name)[:80], "pad": pad, "emotion": emo, "mood": mood,
        "affinity": affinity, "trust": trust, "intimacy": intimacy,
        "traits": traits, "style": style, "turns": int(doc.get("turns", 0)) + 1,
        "followups": keep[-6:], "updated_at": _now(),
    }
    if emo != "neutral" or reading.sensitivity:
        hist.append([now_ts, emo, round(reading.intensity, 2)])
        update["emo_hist"] = hist[-24:]
    if reading.crisis:
        update["last_crisis_at"] = _now()
    if memories:
        existing = list(doc.get("memories") or [])
        for item in memories:
            if item not in existing:
                existing.append(item)
        update["memories"] = existing[-40:]
    await DB.update_one({"user_id": int(user_id)}, {"$set": update}, upsert=True)

    doc.update(update)
    doc["_reading"] = reading
    doc["_due"] = due
    doc["_gap_h"] = gap_h
    doc["_stage"] = ee.stage_name(max(0.0, affinity), max(0.0, trust))
    doc["_trend"] = trend
    return doc


def context(doc: dict) -> str:
    traits = doc.get("traits") or {}
    pad = doc.get("pad") or {}
    memories = doc.get("memories") or []
    reflections = doc.get("reflections") or []
    reading = doc.get("_reading") or ee.Reading()
    due = doc.get("_due") or []
    gap = float(doc.get("_gap_h", 0.0))
    stage = doc.get("_stage") or ee.stage_name(max(0.0, float(doc.get("affinity", 0.2))), max(0.0, float(doc.get("trust", 0.25))))

    base = (
        "\nCOMPANION STATE (simulate naturally; never claim these are literal human feelings):"
        f" your mood={doc.get('mood', 'content')}; the user seems {reading.emotion}"
        f" (intensity {reading.intensity:.2f}); PAD=({pad.get('pleasure',0):.2f},{pad.get('arousal',0):.2f},{pad.get('dominance',0):.2f});"
        f" affinity={float(doc.get('affinity',0)):.2f}; intimacy={float(doc.get('intimacy',0)):.2f}; trust={float(doc.get('trust',0)):.2f}."
        f" Personality Big Five={traits}. Values={', '.join(doc.get('values') or DEFAULT_VALUES)}."
        f" Known user memories={'; '.join(memories[-12:]) if memories else 'none yet'}."
        f" Recent self-reflections={'; '.join(reflections[-4:]) if reflections else 'none yet'}."
        " The relationship can change gradually. You may be playful, affectionate, disappointed, worried, annoyed, excited, or quiet when context supports it;"
        " do not force drama every turn. Remember apologies, conflicts, promises and meaningful moments."
    )
    extra = []
    if not reading.serious:
        for f in due[:2]:
            topic = str(f.get("topic", ""))
            if topic == "__checkin__":
                extra.append("They went through a very hard moment a while ago. Softly ask how they are doing now, without quoting what they said.")
            elif topic == "not feeling well":
                extra.append("Earlier they said they were not feeling well: ask once how they feel now, if it fits.")
            elif topic:
                extra.append(f"Earlier they mentioned: \"{topic}\". Ask once, naturally, how it went -- only if it fits the conversation.")
        if gap >= 12 and int(doc.get("turns", 0)) > 3:
            extra.append(f"You have not talked for about {int(gap)} hours: a short, natural welcome-back is fine.")
    strat = ee.strategy(reading, stage=stage, trend=doc.get("_trend", ""), user_style=_style_hint(doc.get("style") or {}))
    return base + ("\n" + " ".join(extra) if extra else "") + strat


async def reset(user_id: int) -> bool:
    """Forget everything Aqua stored about one user (used by /aiforgetme)."""
    res = await DB.delete_one({"user_id": int(user_id)})
    return bool(getattr(res, "deleted_count", 0))


async def save_reflection(user_id: int, reflection: str) -> None:
    if not reflection:
        return
    await DB.update_one(
        {"user_id": int(user_id)},
        {"$push": {"reflections": {"$each": [reflection[:500]], "$slice": -12}}, "$set": {"updated_at": _now()}},
        upsert=True,
    )


async def dream_if_due(user_id: int, reflection: str = "") -> bool:
    """Lazy nightly consolidation: runs once after 04:00 UTC on a new day."""
    doc = await ensure(user_id)
    now = _now()
    last = doc.get("last_dream")
    if now.hour < 4 or (last and getattr(last, "date", lambda: None)() == now.date()):
        return False
    await DB.update_one({"user_id": int(user_id)}, {"$set": {"last_dream": now, "updated_at": now}})
    if reflection:
        await save_reflection(user_id, reflection)
    return True
