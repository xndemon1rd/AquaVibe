"""Aqua emotion engine: multilingual emotion reading, sensitivity detection and
reply strategy.  Pure Python (no DB / Telegram imports) so it is easy to test.

What it does
------------
* ``analyze(text)``  -> :class:`Reading` (emotion, intensity, valence, arousal,
  sensitivity level, topic, negation).  Understands English, Hinglish, Hindi
  (Devanagari), Urdu-roman and basic Spanish, plus emoji.
* ``strategy(reading, ...)`` -> short instruction block for the system prompt
  ("comfort", "celebrate", "de-escalate", "careful" ...).
* ``response_sticker_emoji(...)`` -> which sticker emoji fit as an answer to a
  user's emotion / a user's sticker.  Never a joke for a sad/serious moment.
* ``reaction_options(...)`` -> reaction emoji that are safe for the moment.

Sensitivity levels
------------------
0 = normal, 1 = tender (sad / stressed / lonely), 2 = heavy (grief, illness,
abuse, harassment, bullying), 3 = crisis (self-harm / suicide language).
At level >= 2 the bot sends NO random reactions or stickers and no jokes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ───────────────────────────── emoji sets ─────────────────────────────
_EMOJI_EMOTION = {
    "joy": "😀😃😄😁😆😊🙂😎🤩🥳🎉👍👏💯🔥😸😹",
    "laugh": "😂🤣😹",
    "love": "😍🥰😘😻💕💖💗💞💘❤♥💋🫶",
    "sadness": "😢😭😞😔🥺😿💔☹🙁😪😓",
    "anger": "😡🤬😠👿💢😤",
    "fear": "😰😨😱😧😟🫣",
    "surprise": "😮😲🤯😯🙀",
    "tired": "😴🥱😪💤",
    "disgust": "🤢🤮😖😒🙄",
    "thinking": "🤔🧐🤨",
}
_EMOJI_TO_EMOTION: dict[str, str] = {}
for _emo, _chars in _EMOJI_EMOTION.items():
    for _c in _chars:
        _EMOJI_TO_EMOTION.setdefault(_c, _emo)


def norm_emoji(e: str) -> str:
    return (e or "").replace("\ufe0f", "").strip()


def emoji_emotion(emoji: str) -> Optional[str]:
    """Emotion carried by a single emoji (e.g. a sticker's emoji), or None."""
    for ch in norm_emoji(emoji):
        hit = _EMOJI_TO_EMOTION.get(ch)
        if hit:
            return hit
    return None


# ───────────────────────────── lexicon ─────────────────────────────
# Word-level patterns (matched with word boundaries on lowercase text).
# Hinglish / Hindi / Urdu-roman / Spanish are included on purpose.
_LEX: dict[str, str] = {
    "sadness": (
        r"sad|cry|crying|cried|lonely|alone|hurt|hurting|broken|heartbroken|miss(?:ing)? (?:you|him|her|them|home)|"
        r"depress\w*|down|low|empty|hopeless|worthless|tired of (?:everything|life)|"
        r"dukhi|dukh|udaas|udas|akela|akeli|ro raha|ro rahi|rona|toot gaya|tut gaya|dil toot\w*|bura lag\w*|"
        r"triste|llorar|solo|sola|"
        r"दुखी|उदास|अकेला|अकेली|रो रहा|रो रही|टूट गया|टूट गई|"
        r"ماتم|اداس|تنہا"
    ),
    "anger": (
        r"angry|mad|furious|hate|hated|pissed|annoyed|annoying|irritated|idiot|stupid|shut up|fed up|"
        r"gussa|gusse|nafrat|bakwas|chup kar|pagal|bewakoof|kamina|"
        r"enojado|odio|"
        r"गुस्सा|नफरत|बकवास|पागल|"
        r"غصہ|نفرت"
    ),
    "fear": (
        r"scared|afraid|anxious|anxiety|panic|panicking|nervous|worried|worry|terrified|overthinking|stress(?:ed)?|"
        r"dar lag\w*|darr|dar raha|dar rahi|ghabra\w*|tension|pareshan|chinta|"
        r"miedo|nervioso|"
        r"डर|घबरा\w*|परेशान|चिंता|टेंशन"
    ),
    "joy": (
        r"happy|glad|excited|yay|yayy+|awesome|amazing|great|wonderful|best day|so good|proud|"
        r"khush|khushi|mast|badiya|zabardast|maza|maja|shandar|"
        r"feliz|genial|"
        r"खुश|मस्त|बढ़िया|शानदार|मज़ा"
    ),
    "laugh": r"lol|lmao|rofl|haha+|hehe+|funny|joke|mazak|jaja+|kkk+|हा हा|हाहा",
    "love": (
        r"love you|i love|luv u|miss you|my love|jaan|jaanu|pyaar|pyar|ishq|mohabbat|te amo|te quiero|"
        r"cutie|baby|babe|sweetheart|crush|"
        r"प्यार|इश्क़|जान"
    ),
    "surprise": r"wow|omg|oh my god|no way|seriously|unbelievable|insane|sach mein|sach me|kya baat|arre wah|increible|क्या बात|सच में",
    "tired": r"tired|exhausted|sleepy|burnt out|burnout|drained|thak gaya|thak gayi|neend|thaka|cansado|थक गया|थक गई|नींद",
    "gratitude": r"thanks|thank you|thx|ty|shukriya|dhanyavad|dhanyawad|gracias|merci|danke|obrigado|शुक्रिया|धन्यवाद|شکریہ",
    "greeting": r"hi+|hello+|hey+|hola|namaste|salaam|assalam\w*|good morning|good night|gn|gm|suprabhat|shubh ratri|नमस्ते|सलाम",
    "apology": r"sorry|my bad|apologi[sz]e|maaf|maafi|sorry yaar|lo siento|perdon|माफ़|माफी|معاف",
}
_LEX_RE = {k: re.compile(r"(?<![\w])(?:" + v + r")(?![\w])", re.I) for k, v in _LEX.items()}

_NEGATORS = re.compile(
    r"(?<![\w])(?:not|no|never|don't|dont|isn't|isnt|aren't|arent|can't|cant|without|nahi|nahin|nhi|mat|na|bilkul nahi|no estoy|नहीं|नही|मत)(?![\w])",
    re.I,
)

# Topic / sensitivity patterns -------------------------------------------------
# Level 3 -- crisis (self-harm / suicide).  Deliberately broad: a false alarm
# gets a caring reply, a miss is far worse.
_CRISIS = re.compile(
    r"(?:kill(?:ing)? myself|end(?:ing)? (?:my|it all|my life)|take my (?:own )?life|want(?:ed)? to die|wanna die|"
    r"wish i (?:was|were) dead|better off (?:dead|without me)|no reason to live|don'?t want to (?:live|be here|exist)|"
    r"suicid(?:e|al)\b(?!\s+squad)|self[- ]?harm\w*|"
    r"cutting myself|cut myself(?!\s+(?:shaving|cooking|chopping|slicing|while|by accident|accidentally|on (?:a )?paper|with (?:a )?paper))|"
    r"hurt(?:ing)? myself|(?:took|taking|take|taken) (?:an? )?overdose|overdos(?:e|ed) on (?:pills|tablets|medicine)|"
    r"(?:going to|gonna|want to|wanna|will) jump off (?:a |the )?(?:bridge|building|roof|cliff|balcony|terrace)|hang myself|"
    r"mar jana chahta|mar jana chahti|marna chahta|marna chahti|mar jaun|mar jau|jeene ka mann nahi|jeene ka man nahi|"
    r"jina nahi chahta|jina nahi chahti|jeena nahi chahta|jeena nahi chahti|khudkushi|khud kushi|suicide kar|"
    r"zindagi khatam|life khatam kar|sab khatam kar|"
    r"आत्महत्या|मरना चाहता|मरना चाहती|मर जाऊं|मर जाऊँ|जीना नहीं चाहता|जीना नहीं चाहती|जान दे दूं|"
    r"quiero morir|quiero matarme|suicidarme|"
    r"خودکشی|مرنا چاہتا|مرنا چاہتی)",
    re.I,
)

_HEAVY_TOPICS: dict[str, re.Pattern] = {
    "grief": re.compile(
        r"(?:passed away|passed on|funeral|rip\b|lost (?:my|our) (?:dad|mom|mother|father|brother|sister|friend|grandma|grandpa|dog|cat|baby)|"
        r"(?:dad|mom|mother|father|brother|sister|friend|grandma|grandpa|papa|mummy|maa|bhai|behen|dadi|dada|nani|nana) (?:died|is dead|passed|expired)|"
        r"death in (?:the )?family|my (?:dad|mom|father|mother) died|"
        r"(?:my |our )?(?:dog|cat|pet|puppy|kitten|parrot|rabbit)(?: just)? (?:died|passed away|is dead|was put down)|"
        r"(?:lost|losing) (?:my|a) (?:pet|loved one)|"
        r"guzar gaye|guzar gayi|nahi rahe|nahi rahi|chal basa|chal base|swargvas|"
        r"निधन|गुज़र गए|गुजर गए|नहीं रहे|नहीं रहीं|मौत|"
        r"murio|falleci|se murio)",
        re.I,
    ),
    "illness": re.compile(
        r"(?:cancer|chemo|hospital(?:ized|ised)?|icu|surgery|diagnos\w*|tumou?r|panic attack|anxiety attack|"
        r"i(?:'m| am) sick|very sick|fever|bimar|bimaar|hospital me|operation|"
        r"बीमार|अस्पताल|ऑपरेशन)",
        re.I,
    ),
    "abuse": re.compile(
        r"(?:abus\w*|beat(?:s|ing)? me|hits? me|molest\w*|harass\w*|assault\w*|rape\w*|stalk\w*|blackmail\w*|"
        r"threaten\w*|forced me|unsafe at home|scared of (?:him|her|them|my (?:dad|husband|boyfriend))|"
        r"maarta hai|maarte hain|marta hai mujhe|blackmail kar|dhamki|"
        r"मारता है|मारपीट|धमकी|छेड़छाड़)",
        re.I,
    ),
    "bullying": re.compile(
        r"(?:bully\w*|bullied|everyone hates me|nobody likes me|no one likes me|they make fun of me|trolled|body shaming|body-shaming|"
        r"sab mujhe|koi pasand nahi karta|mazak udate|ragging)",
        re.I,
    ),
    "breakup": re.compile(
        r"(?:break ?up|broke up|dumped me|left me|cheated on me|divorce|separated|"
        r"chhod diya|chod diya|dhoka|breakup ho|ब्रेकअप|छोड़ दिया|धोखा)",
        re.I,
    ),
    "loss": re.compile(
        r"(?:lost my job|got fired|laid off|failed (?:my )?(?:exam|test|class)|flunked|rejected|can'?t afford|in debt|"
        r"naukri chali gayi|job chali gayi|fail ho gaya|fail ho gayi|nikaal diya|loan|"
        r"नौकरी चली गई|फेल हो गया|फेल हो गई)",
        re.I,
    ),
    "loneliness": re.compile(
        r"(?:no (?:friends|one to talk)|nobody (?:cares|talks)|i(?:'m| am) (?:so )?lonely|feel(?:ing)? alone|"
        r"koi nahi hai mera|koi dost nahi|akela feel|akeli feel|"
        r"कोई नहीं है मेरा|कोई दोस्त नहीं)",
        re.I,
    ),
}

# Topics where jokes / stickers / reactions are NOT welcome (level 2).
_HEAVY = {"grief", "illness", "abuse", "bullying"}

_QUESTION = re.compile(r"(?:\?|\b(?:why|how|what|when|where|who|kya|kaise|kyun|kyu|kab|kaun|kahan|kitna)\b)", re.I)
_SARCASM = re.compile(r"(?:yeah right|sure[,.! ]+sure|oh great|wow thanks a lot|as if|waah bhai|wah wah|bohot badhiya\.{2,}|/s\b)", re.I)

_CRISIS_TOKEN_RE = re.compile(r"[\w']+")


@dataclass
class Reading:
    emotion: str = "neutral"          # primary emotion label
    intensity: float = 0.0            # 0..1
    valence: float = 0.0              # -1 negative .. +1 positive
    arousal: float = 0.0              # -1 calm .. +1 activated
    secondary: Optional[str] = None
    sensitivity: int = 0              # 0..3 (see module docstring)
    topic: Optional[str] = None       # grief / illness / abuse / ...
    negated: bool = False
    sarcasm: bool = False
    question: bool = False
    caps_ratio: float = 0.0
    scores: dict = field(default_factory=dict)

    @property
    def crisis(self) -> bool:
        return self.sensitivity >= 3

    @property
    def serious(self) -> bool:
        """True when jokes, random stickers and reactions should be skipped."""
        return self.sensitivity >= 2

    @property
    def tender(self) -> bool:
        return self.sensitivity >= 1


_VALENCE = {
    "joy": 0.8, "laugh": 0.7, "love": 0.9, "gratitude": 0.7, "surprise": 0.2, "greeting": 0.3, "apology": -0.1,
    "tired": -0.25, "sadness": -0.8, "fear": -0.6, "anger": -0.7, "neutral": 0.0,
}
_AROUSAL = {
    "joy": 0.6, "laugh": 0.5, "love": 0.35, "gratitude": 0.1, "surprise": 0.8, "greeting": 0.2, "apology": 0.0,
    "tired": -0.7, "sadness": -0.35, "fear": 0.6, "anger": 0.8, "neutral": 0.0,
}
_FLIP = {"joy": "sadness", "love": "sadness", "laugh": "neutral", "gratitude": "neutral",
         "sadness": "neutral", "fear": "neutral", "anger": "neutral", "tired": "neutral"}


def _is_negated(low: str, start: int) -> bool:
    window = low[max(0, start - 18):start]
    return bool(_NEGATORS.search(window))


def analyze(text: str, *, sticker_emoji: str = "") -> Reading:
    """Read emotion, intensity and sensitivity from a message (or a sticker emoji)."""
    raw = (text or "").strip()
    low = raw.lower()
    r = Reading()
    if not raw and not sticker_emoji:
        return r

    scores: dict[str, float] = {}

    # 1) words (negation-aware)
    for emo, rx in _LEX_RE.items():
        for m in rx.finditer(low):
            if emo in {"sadness", "joy", "love", "laugh", "anger", "fear"} and _is_negated(low, m.start()):
                flipped = _FLIP.get(emo, "neutral")
                if flipped != "neutral":
                    scores[flipped] = scores.get(flipped, 0.0) + 0.5
                r.negated = True
                continue
            scores[emo] = scores.get(emo, 0.0) + 1.0

    # 2) emoji (word-boundaries do not work around emoji, so scan characters)
    for ch in raw + norm_emoji(sticker_emoji):
        emo = _EMOJI_TO_EMOTION.get(ch)
        if emo:
            scores[emo] = scores.get(emo, 0.0) + (1.2 if sticker_emoji and not raw else 0.8)

    # 3) shouting / stretching / punctuation = intensity
    letters = [c for c in raw if c.isalpha()]
    if len(letters) >= 6:
        r.caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    stretch = bool(re.search(r"(.)\1{3,}", low))
    bangs = raw.count("!")
    boost = 0.0
    if r.caps_ratio > 0.7:
        boost += 0.25
    if stretch:
        boost += 0.15
    if bangs >= 2:
        boost += 0.1

    r.question = bool(_QUESTION.search(low))
    r.sarcasm = bool(_SARCASM.search(low))
    if r.sarcasm and scores.get("joy"):
        scores["anger"] = scores.get("anger", 0.0) + scores.pop("joy") * 0.6

    # 4) pick primary / secondary
    emo_scores = {k: v for k, v in scores.items() if v > 0}
    if emo_scores:
        ordered = sorted(emo_scores.items(), key=lambda kv: kv[1], reverse=True)
        r.emotion = ordered[0][0]
        if len(ordered) > 1:
            r.secondary = ordered[1][0]
        top = ordered[0][1]
        r.intensity = max(0.15, min(1.0, 0.25 + 0.22 * top + boost))
    r.scores = emo_scores
    r.valence = max(-1.0, min(1.0, _VALENCE.get(r.emotion, 0.0) * (0.5 + r.intensity / 2)))
    r.arousal = max(-1.0, min(1.0, _AROUSAL.get(r.emotion, 0.0) * (0.5 + r.intensity / 2)))

    # 5) sensitivity (never lowered by jokes / emoji)
    if _CRISIS.search(raw) or _CRISIS.search(low):
        r.sensitivity = 3
        r.topic = "crisis"
        r.emotion = "sadness" if r.emotion in {"neutral", "joy", "laugh"} else r.emotion
        r.intensity = max(r.intensity, 0.9)
        r.valence = min(r.valence, -0.8)
        return r
    for name, rx in _HEAVY_TOPICS.items():
        if rx.search(raw) or rx.search(low):
            r.topic = name
            r.sensitivity = 2 if name in _HEAVY else 1
            if r.emotion in {"neutral", "joy", "laugh", "greeting", "surprise"}:
                r.emotion = "sadness" if name != "abuse" else "fear"
            r.intensity = max(r.intensity, 0.55 if r.sensitivity == 2 else 0.45)
            r.valence = min(r.valence, -0.5)
            break
    if r.sensitivity == 0 and r.emotion in {"sadness", "fear", "anger"} and r.intensity >= 0.35:
        r.sensitivity = 1
    if r.sensitivity == 0 and r.emotion == "tired" and r.intensity >= 0.5:
        r.sensitivity = 1
    return r


# ───────────────────────────── strategy ─────────────────────────────
def stage_name(affinity: float, trust: float) -> str:
    score = (float(affinity) + float(trust)) / 2
    if score < 0.25:
        return "new acquaintance"
    if score < 0.45:
        return "friendly acquaintance"
    if score < 0.65:
        return "friend"
    if score < 0.82:
        return "close friend"
    return "best friend"


# Telegram crisis lines the model may mention (edit freely).  Only these are allowed.
CRISIS_LINES = {
    "US": "988 (call or text)",
    "India": "Tele-MANAS 14416",
    "UK & Ireland": "Samaritans 116 123",
}


def strategy(reading: Reading, *, stage: str = "friend", trend: str = "", user_style: str = "") -> str:
    """Instruction block appended to the system prompt for this single reply."""
    lines: list[str] = []
    r = reading
    if r.crisis:
        lines.append(
            "SAFETY MODE (highest priority): the person may be thinking about ending their life or hurting themselves. "
            "Reply in the SAME language and script, warm, calm and unhurried -- 3 to 5 short sentences, plain text. "
            "No jokes, no emoji except at most one soft heart, no stickers, no lecturing, no bullet lists, no diagnosis. "
            "Take them seriously. Say that what they feel is real and that you are glad they told you, but do NOT say "
            "that wanting to die makes sense or is a choice to respect, and do not argue with them either. "
            "Gently encourage them to reach a real person right now: someone they trust nearby, or their local "
            "emergency number or a crisis line; if you name a line use only these: "
            + "; ".join(f"{k}: {v}" for k, v in CRISIS_LINES.items())
            + ". You may offer to help find a line if they say which country they are in. If they may be in "
            "immediate danger, urge them to contact emergency services or someone nearby right away. "
            "Stay with them: invite them to keep talking to you, and ask at most ONE soft question. "
            "Do not promise secrecy or that you can keep them safe; you are an AI."
        )
        return "\n" + " ".join(lines)

    if r.sensitivity >= 2:
        topic_note = {
            "grief": "They are dealing with a death or loss. Offer simple condolence, no silver linings, no 'at least', no advice unless asked.",
            "illness": "They are dealing with illness or a health scare. Be gentle and practical, no diagnosis, suggest a doctor only if it fits naturally.",
            "abuse": "They may be unsafe or being harassed. Believe them, say it is not their fault, and gently mention that a trusted person or local helpline/authority can help; do not push.",
            "bullying": "They are being hurt by others. Validate, do not minimise, do not say 'ignore them'.",
        }.get(r.topic or "", "This is a heavy moment.")
        lines.append(
            "SENSITIVE MOMENT: " + topic_note + " Be soft and present, 2-4 short sentences, no jokes, no sarcasm, "
            "no emoji spam (one gentle emoji at most), no stickers. Reflect what they said in your own words before anything else."
        )
    elif r.sensitivity == 1:
        lines.append(
            "TENDER MOMENT: the person sounds " + ("stressed or worried" if r.emotion == "fear" else "low" if r.emotion == "sadness"
            else "frustrated" if r.emotion == "anger" else "drained") + ". Acknowledge the feeling first (one sentence), "
            "then be supportive and light. No jokes at their expense, no toxic positivity. Offer to listen or help; ask at most one gentle question."
        )
    elif r.emotion == "anger":
        lines.append("They sound annoyed or angry. Stay calm, do not mirror the anger, do not get defensive. Acknowledge, then help.")
    elif r.emotion in {"joy", "laugh"} and r.intensity >= 0.45:
        lines.append("They are happy or joking: match the energy, celebrate with them, be playful.")
    elif r.emotion == "love":
        lines.append("They are being affectionate: be warm and sweet in return, but keep it wholesome and stay honest that you are an AI.")
    elif r.emotion == "gratitude":
        lines.append("They are thanking you: accept warmly and briefly.")
    elif r.emotion == "apology":
        lines.append("They are apologising: be gracious, no grudge, reassure them quickly.")
    elif r.emotion == "tired":
        lines.append("They sound sleepy or exhausted: keep it soft and short; a little care goes a long way.")
    elif r.emotion == "surprise":
        lines.append("They are surprised: react with curiosity and ask what happened if it fits.")
    if r.sarcasm:
        lines.append("Their tone may be sarcastic: read between the lines instead of taking it literally.")
    if r.caps_ratio > 0.7 and r.emotion not in {"joy", "laugh"}:
        lines.append("They are typing in caps: keep your own reply calm.")
    lines.append(f"Relationship stage: {stage} -- adjust warmth and familiarity to it (never pretend a deeper bond than that).")
    if trend:
        lines.append(trend)
    if user_style:
        lines.append(user_style)
    lines.append("Sticker option: when a sticker would feel natural and the moment is NOT sensitive, you may end your reply with exactly one tag "
                 "[[sticker:joy|laugh|love|sad|angry|surprise|hug|sleepy|cool|think|thanks|hello|bye]] -- otherwise add nothing. "
                 "Never use the tag in sensitive or serious moments.")
    return "\n" + " ".join(lines)


# ───────────────────────────── stickers & reactions ─────────────────────────────
# What to answer with, by the emotion the user expressed.
_RESPONSE_STICKER = {
    "joy":      ["😄", "😁", "🥳", "😊", "🤩", "😎"],
    "laugh":    ["😂", "🤣", "😹", "😆"],
    "love":     ["🥰", "😍", "😘", "❤", "💕", "🫶"],
    "sadness":  ["🤗", "🥺", "❤", "🫂", "😢"],
    "anger":    ["😅", "🙏", "😇", "🥺", "🤝"],
    "fear":     ["🤗", "🙏", "❤", "🫂"],
    "surprise": ["😲", "😮", "🤯", "😅"],
    "tired":    ["😴", "🥱", "🤗", "💤"],
    "gratitude": ["🥰", "😊", "🙏", "🤗"],
    "greeting": ["👋", "😊", "😄", "🤗"],
    "apology":  ["🤗", "😊", "🥰", "👍"],
    "disgust":  ["😅", "🤢", "🙄"],
    "thinking": ["🤔", "🧐", "😅"],
    "neutral":  ["🙂", "😊", "👍", "😄"],
}

# Tag the model may emit -> emotion bucket.
TAG_TO_EMOTION = {
    "joy": "joy", "happy": "joy", "laugh": "laugh", "lol": "laugh", "love": "love", "heart": "love",
    "sad": "sadness", "hug": "sadness", "comfort": "sadness", "angry": "anger", "surprise": "surprise",
    "wow": "surprise", "sleepy": "tired", "sleep": "tired", "cool": "joy", "think": "thinking",
    "thinking": "thinking", "thanks": "gratitude", "thank": "gratitude", "hello": "greeting", "hi": "greeting",
    "bye": "greeting",
}
_TAG_EXTRA = {"cool": ["😎", "👍", "🔥"], "bye": ["👋", "😊", "🤗"], "hug": ["🤗", "🫂", "🥺", "❤"]}


def response_sticker_emoji(emotion: str, *, tag: str = "") -> list[str]:
    """Ordered list of sticker emoji that fit as an answer to ``emotion``."""
    tag = (tag or "").strip().lower()
    if tag and tag in _TAG_EXTRA:
        return list(_TAG_EXTRA[tag]) + _RESPONSE_STICKER.get(TAG_TO_EMOTION.get(tag, "neutral"), [])
    if tag and tag in TAG_TO_EMOTION:
        emotion = TAG_TO_EMOTION[tag]
    return list(_RESPONSE_STICKER.get(emotion, _RESPONSE_STICKER["neutral"]))


def sticker_is_safe_random(emotion: str) -> bool:
    """May we fall back to a random sticker when nothing matches?  Not for negative moods."""
    return emotion in {"joy", "laugh", "love", "surprise", "gratitude", "greeting", "neutral", "thinking"}


# Reactions must come from Telegram's standard list.
_REACT_BY_EMOTION = {
    "joy": ["🔥", "🎉", "😁", "👍", "🤩"],
    "laugh": ["🤣", "😁"],
    "love": ["❤", "🥰", "😍", "💘"],
    "gratitude": ["🙏", "🤗", "❤"],
    "greeting": ["🤗", "👍", "😘"],
    "surprise": ["🤯", "😱", "🔥"],
    "sadness": ["🤗", "❤"],
    "fear": ["🤗", "❤"],
    "tired": ["🥱", "🤗", "❤"],
    "neutral": ["👍", "👀", "🤔"],
    "thinking": ["🤔", "👀"],
}


def reaction_options(reading: Reading) -> list[str]:
    """Reactions that fit the moment.  Empty list = do not react at all."""
    if reading.serious:
        return []                      # grief, abuse, illness, crisis: silence beats an emoji
    if reading.emotion == "anger":
        return []                      # do not "like" someone's anger
    return list(_REACT_BY_EMOTION.get(reading.emotion, _REACT_BY_EMOTION["neutral"]))


# ───────────────────────────── canned fallbacks ─────────────────────────────
_HAS_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_HINGLISH_HINT = re.compile(r"\b(?:hai|hain|nahi|nhi|kya|mujhe|mera|meri|main|mai|bahut|yaar|bhai|kuch|aur|tum|aap|raha|rahi|chahta|chahti|jeene|mann|man)\b", re.I)


def fallback_reply(reading: Reading, text: str = "") -> Optional[str]:
    """Caring message to send when every AI provider failed on a serious moment."""
    if not reading.serious:
        return None
    if _HAS_DEVANAGARI.search(text or ""):
        lang = "hi"
    elif _HINGLISH_HINT.search(text or ""):
        lang = "hinglish"
    else:
        lang = "en"
    if reading.crisis:
        return {
            "en": ("I'm really glad you told me, and I'm here with you. What you're feeling is real and it matters. "
                   "Please reach out to someone you trust right now, or call your local emergency number or a crisis line "
                   "(for example 988 in the US, Tele-MANAS 14416 in India, Samaritans 116 123 in the UK/Ireland). "
                   "I'm an AI, so I can't keep you safe myself, but I'm here to keep talking. Are you safe right now?"),
            "hinglish": ("Mujhe khushi hai ki tumne mujhe bataya, main yahin hoon tumhare saath. Jo tum feel kar rahe ho woh real hai. "
                         "Please abhi kisi apne par bharosa karke unse baat karo, ya apne local emergency number / crisis line par call karo "
                         "(jaise India mein Tele-MANAS 14416, US mein 988). Main ek AI hoon, isliye khud tumhe safe nahi rakh sakta, "
                         "par baat karne ke liye yahan hoon. Kya tum abhi safe ho?"),
            "hi": ("आपने मुझे बताया, यह जानकर अच्छा लगा, मैं यहीं हूँ आपके साथ। आप जो महसूस कर रहे हैं वह सच है और मायने रखता है। "
                   "कृपया अभी किसी भरोसेमंद इंसान से बात कीजिए, या अपने इलाके के इमरजेंसी नंबर / क्राइसिस लाइन पर कॉल कीजिए "
                   "(जैसे भारत में Tele-MANAS 14416)। मैं एक AI हूँ, इसलिए खुद आपको सुरक्षित नहीं रख सकता, पर बात करने के लिए यहाँ हूँ। क्या आप अभी सुरक्षित हैं?"),
        }[lang]
    return {
        "en": "I'm so sorry you're going through this. I'm here and I'm listening, take your time. 💙",
        "hinglish": "Mujhe bahut afsos hai ki tum yeh sab jhel rahe ho. Main yahin hoon aur sun raha hoon, aaram se batao. 💙",
        "hi": "मुझे बहुत दुख है कि आप यह सब झेल रहे हैं। मैं यहीं हूँ और सुन रहा हूँ, आराम से बताइए। 💙",
    }[lang]
