"""Telegram custom/premium emoji helpers.

The IDs below are supplied by the bot owner.  Keep them as integers because
Pyrogram's custom_emoji_id field is a Telegram 64-bit integer (not a string).
"""
import re
from pyrogram.enums import MessageEntityType
from pyrogram.types import MessageEntity

# Current Premium Custom Emoji mapping supplied by the owner.
# IDs are kept as integers because Telegram custom-emoji IDs are 64-bit.
DEFAULT_EMOJI = {
    # ── Help-category / UI emoji (also used as button icons) ──
    "🎶": 5470135030393090150,
    "👤": 5902335789798265487,
    "💎": 5262922516426420894,
    "🎲": 5280816565657300091,
    "🔨": 5400326607648867000,
    "📦": 5472335930549347896,
    "⚙️": 5341715473882955310,
    "⚙": 5341715473882955310,
    # ── Newest premium emoji ──
    "🔒": 5291873529464122510,
    "🤖": 5471932804918956080,
    "✨": 5348097378672975991,
    "🥀": 5208923808169222461,
    "✅": 5206607081334906820,
    "❌": 5210952531676504517,
    # ── Earlier premium emoji ──
    "🌍": 5287295223175604777,
    "🧠": 5280826864988873394,
    "😴": 5305715161087110779,
    "🪽": 5280774071250872500,
    "🌸": 5280569974404966639,
    "🤝": 5278454020111887994,
    "🦋": 5276412965753480690,
    "💕": 5276239041052828276,
    "🫧": 5278573677900752088,
    "🕊": 5274002879215067737,
    "🍒": 5271721134889395048,
    "🥰": 5289944036881230584,
    "❤": 5292122921035133343,
    "💍": 5267334530171169409,
    "🧸": 5206502842478638898,
    "🌐": 5447410659077661506,
    "🎧": 5271721134889395048,
    "🏠": 5199596741225111392,
    "📅": 5287606810168028257,
    "🤔": 5172398207988139299,
    "↝": 5256131095094652290,
    "↜": 5877536313623711363,
    "🏓": 5467537163589538076,
    "🕚": 5839380464116175529,
    "🏀": 5384088040677319401,
    "😫": 5406590207564726535,
    "🙂": 5942913498349571809,
    "🌈": 5359630594223394725,
    "🪄": 5255877597534905292,
    "🎁": 6032937473162614352,
    "🍷": 5330280024673101519,
    "❤️": 5285439518130857782,
    "💌": 5285184156555306745,
    "📫": 5287533898803211359,
    "🧪": 5256169350368353876,
    "📡": 5256134032852278918,
    "📞": 5285238101344544669,
    "✍️": 5258500400918587241,
    "⌨️": 5258361295517806281,
    "🥂": 5260567255145539253,
    "🫶": 5285338659413846416,
    "🧩": 5265120027853481187,
}

# ── Premium emoji batch supplied by the owner (overrides older entries) ──
NEW_PREMIUM_EMOJI = {
    "👥": 6275895488105419582,
    "👀": 5868461722037130568,
    "🧠": 5848450258224288102,
    "🙋": 6284928607487791587,
    "➡️": 543595599847910265,
    "🤝": 6035033893944430595,
    "♀": 5372845199275866752,
    "💁‍♀️": 608233074382288043,
    "💃": 5400291457636506966,
    "📝": 5850354569413923251,
    "✍️": 5197269100878907942,
    "📄": 5370604433233177619,
    "🧾": 5444856076954520455,
    "📁": 5409150592188690356,
    "🗂": 5431736674147114227,
    "📎": 5305265301917549162,
    "🔎": 5188311512791393083,
    "❓": 6267288627047305992,
    "↗️": 6154657967317717391,
    "💡": 5224596414415256150,
    "⚠️": 5771693192575456661,
    "🚨": 5850543608104489321,
    "🚫": 6275767489490063307,
    "🛑": 6084515769780013003,
    "🏴‍☠️": 6258110956245619517,
    "💀": 5850304387016037246,
    "🔪": 6082370021298801731,
    "🔫": 5375513791305895364,
    "🧨": 5469913852462242978,
    "🔒": 5296369303661067030,
    "🛡": 6026057596979385040,
    "🔨": 5456312597273923475,
    "🤖": 6255726532136800534,
    "💻": 6026191131807584614,
    "🌐": 6258184490380694944,
    "🛰": 5467403607286502523,
    "🔗": 5850451090213965945,
    "📹": 5375309569905938163,
    "📷": 5969576917316145104,
    "🎬": 5375464961822695044,
    "🎞": 5379703922745159290,
    "🎙": 6032575759606878027,
    "🎧": 6082387600599944892,
    "🔊": 5962882377561674075,
    "🔇": 5389099116460519930,
    "🛠": 5462921117423384478,
    "▶️": 5262724084642372071,
    "⏭": 5321335209818339164,
    "⏮": 5433606574058785698,
    "⏩": 6256047769920737796,
    "⎋": 5352759161945867747,
    "🔙": 6026034017608930629,
    "🔻": 6258228857392861509,
    "🎚": 5803053282834256734,
    "⏳": 5301050079279337616,
    "🎉": 5208541126583136130,
    "🎁": 5449800250032143374,
    "🎄": 5255706846815077966,
    "🥳": 6267036564006638970,
    "🏆": 6080349140401786835,
    "💰": 5769603377453339560,
    "💸": 5769409644363519615,
    "💳": 5472163152604975299,
    "🗺": 6026257901369168205,
    "🚪": 6266944849275000979,
    "🇺🇸": 6296495074675003932,
}
DEFAULT_EMOJI.update(NEW_PREMIUM_EMOJI)

# ── Heart / romance set supplied by the owner (2026-10-01) ──
# Replaces the older 💗 💞 💜 🤍 🖤 💋 IDs and adds 🩷 💚 💙 🌹.
HEART_PREMIUM_EMOJI = {
    "💗": 6231147976195051524,
    "💞": 6230808020943638410,
    "🩷": 602392432967313503,
    "💚": 608216840694399322,
    "💙": 585026579243991512,
    "💜": 602623621607929003,
    "🖤": 602390973966922975,
    "🤍": 623117557565489540,
    "🌹": 536393865687467396,
    "💋": 5433888551546662318,
}
DEFAULT_EMOJI.update(HEART_PREMIUM_EMOJI)

# ── Owner-supplied batch (2026-10-01, whisper update) – overrides older IDs ──
OWNER_PREMIUM_EMOJI_2 = {
    "🏆": 5301075711644153578,
    "💗": 5444982142834583372,
    "🔥": 5893185207355315979,
    "🐾": 5422369251690298040,
    "💔": 5278454020111887994,
    "🔐": 5197288647275071607,
    "🔧": 5258023599419171861,
    "💊": 5305715161087110779,
    "⭐": 6084382587139134196,
    "🔄": 5839200986022812209,
}
DEFAULT_EMOJI.update(OWNER_PREMIUM_EMOJI_2)

# ── Owner-supplied batch (2026-10-02, leaderboard emoji) ──
OWNER_PREMIUM_EMOJI_3 = {
    "💖": 5470080737711502911,
    "💠": 5420102041533963010,
    "🏅": 5440539497383087970,
}
DEFAULT_EMOJI.update(OWNER_PREMIUM_EMOJI_3)
# Also match the same emoji written without the U+FE0F variation selector.
for _k, _v in list(DEFAULT_EMOJI.items()):
    DEFAULT_EMOJI.setdefault(_k.replace("\ufe0f", ""), _v)

# Emoji that are turned into native premium *icons* on inline buttons
# (Bot API ``icon_custom_emoji_id``).  Extend this tuple to convert more.
# Every mapped emoji can become a native icon on an inline button.
BUTTON_ICON_EMOJI = tuple(DEFAULT_EMOJI)

# Backward-compatible aliases used by older modules.
PREMIUM_EMOJI = dict(DEFAULT_EMOJI)
PREMIUM_EMOJI_IDS = tuple(PREMIUM_EMOJI.values())

# No legacy butterfly IDs are retained.
BUTTERFLIES = ()


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def custom_emoji_entities(text: str, *, butterfly_cycle: bool = True, blockquote: bool = True):
    """Return Pyrogram custom-emoji entities for configured visible emoji."""
    entities = []
    if blockquote and text:
        entities.append(
            MessageEntity(
                type=MessageEntityType.BLOCKQUOTE,
                offset=0,
                length=_utf16_len(text),
            )
        )
    cursor = 0

    # Longest visible emoji first (e.g. ⚡️ includes a variation selector).
    tokens = sorted(DEFAULT_EMOJI, key=len, reverse=True)
    while cursor < len(text):
        matched = None
        emoji_id = None
        for token in tokens:
            if text.startswith(token, cursor):
                matched = token
                emoji_id = DEFAULT_EMOJI[token]
                break

        # Do not use a legacy/custom ID for butterflies.
        if matched:
            before = text[:cursor]
            entities.append(
                MessageEntity(
                    type=MessageEntityType.CUSTOM_EMOJI,
                    offset=_utf16_len(before),
                    length=_utf16_len(matched),
                    custom_emoji_id=int(emoji_id),
                )
            )
            cursor += len(matched)
            # Key has no variation selector but the text does (e.g. "🕊️"):
            # cover it too so no stray U+FE0F is left after the custom emoji.
            if not matched.endswith("\ufe0f") and text.startswith("\ufe0f", cursor):
                entities[-1].length += 1
                cursor += 1
        else:
            cursor += 1
    return entities



def text_link_entity(display_text: str, url: str, offset: int = 0):
    """A TEXT_LINK entity so ``display_text`` renders as a real, clickable
    link even when explicit entities are supplied elsewhere in the message
    (Pyrogram skips parse_mode -- and any markup inside the raw string --
    whenever ``entities``/``caption_entities`` are passed explicitly)."""
    return MessageEntity(
        type=MessageEntityType.TEXT_LINK,
        offset=offset,
        length=_utf16_len(display_text),
        url=url,
    )


_TAG_RE = re.compile(r"(<[^>]*>)")
_MAX_CUSTOM = 90  # Telegram allows ~100 entities per message


def html_custom_emoji(text: str) -> str:
    """Wrap mapped emoji in ``<emoji id=..>`` tags (HTML parse mode).

    Unlike explicit ``entities`` this keeps ``parse_mode`` working, so <b>/<a>
    etc. still render.  Emoji inside tags, <code>/<pre> or an existing
    <emoji> are left alone.
    """
    if not text:
        return text
    tokens = sorted(DEFAULT_EMOJI, key=len, reverse=True)
    out, skip, count = [], 0, 0
    for part in _TAG_RE.split(text):
        if part.startswith("<") and part.endswith(">"):
            low = part.lower()
            if re.match(r"</?(code|pre|emoji|tg-emoji)\b", low):
                skip += -1 if low.startswith("</") else 1
                skip = max(skip, 0)
            out.append(part)
            continue
        if skip or not part:
            out.append(part)
            continue
        i, buf = 0, []
        while i < len(part):
            hit = None
            if count < _MAX_CUSTOM:
                for tok in tokens:
                    if part.startswith(tok, i):
                        hit = tok
                        break
            if hit:
                j = i + len(hit)
                if not hit.endswith("\ufe0f") and part.startswith("\ufe0f", j):
                    j += 1
                buf.append(f'<emoji id="{DEFAULT_EMOJI[hit]}">{part[i:j]}</emoji>')
                count += 1
                i = j
            else:
                buf.append(part[i])
                i += 1
        out.append("".join(buf))
    return "".join(out)


def _html_ok(client, kwargs) -> bool:
    mode = kwargs.get("parse_mode")
    if mode is None:
        mode = getattr(client, "parse_mode", None)
    name = str(getattr(mode, "name", mode) or "default").lower()
    return name in ("default", "html", "parsemode.html", "parsemode.default", "combined")


def install_html_emoji_hooks(client_cls=None):
    """Premium emoji in ALL normal bot text/captions, without breaking HTML.

    Wraps the Client send/edit methods (Message.reply_* call these).  Skipped
    when the caller passes explicit entities or a non-HTML parse mode.
    """
    try:
        from pyrogram import Client as _Client
    except Exception:
        return
    client_cls = client_cls or _Client
    if getattr(client_cls, "_aqua_html_emoji", False):
        return

    def wrap(name, field, pos):
        original = getattr(client_cls, name, None)
        if original is None or getattr(original, "_aqua_html_wrapped", False):
            return
        ent_key = "entities" if field == "text" else "caption_entities"

        async def wrapped(self, *args, **kwargs):
            try:
                if kwargs.get(ent_key) is None and _html_ok(self, kwargs):
                    if field in kwargs and isinstance(kwargs[field], str):
                        kwargs[field] = html_custom_emoji(kwargs[field])
                    elif len(args) > pos and isinstance(args[pos], str):
                        args = list(args)
                        args[pos] = html_custom_emoji(args[pos])
            except Exception:
                pass
            return await original(self, *args, **kwargs)

        wrapped._aqua_html_wrapped = True
        wrapped.__name__ = name
        setattr(client_cls, name, wrapped)

    # (method, keyword, positional index after chat_id/…)
    wrap("send_message", "text", 1)
    wrap("edit_message_text", "text", 2)
    for m in ("send_photo", "send_video", "send_animation", "send_document", "send_audio", "send_voice"):
        wrap(m, "caption", 99)
    wrap("edit_message_caption", "caption", 2)
    client_cls._aqua_html_emoji = True


def install_message_emoji_hooks():
    """Attach configured custom-emoji entities to normal bot output."""
    try:
        from pyrogram import Client
        from pyrogram.types import Message
    except Exception:
        return
    if getattr(Message, "_trebel_premium_hooks", False):
        return

    def _text_kwargs(args, kwargs):
        if kwargs.get("entities") is not None:
            return
        text = kwargs.get("text")
        if text is None and args and isinstance(args[0], str):
            text = args[0]
        if isinstance(text, str) and text:
            kwargs["entities"] = custom_emoji_entities(text, blockquote=False)

    def _caption_kwargs(args, kwargs):
        if kwargs.get("caption_entities") is not None:
            return
        caption = kwargs.get("caption")
        if isinstance(caption, str) and caption:
            kwargs["caption_entities"] = custom_emoji_entities(caption, blockquote=False)

    def wrap_text(cls, name):
        original = getattr(cls, name, None)
        if original is None or getattr(original, "_trebel_premium_wrapped", False):
            return

        async def wrapped(self, *args, **kwargs):
            _text_kwargs(args, kwargs)
            return await original(self, *args, **kwargs)

        wrapped._trebel_premium_wrapped = True
        setattr(cls, name, wrapped)

    def wrap_caption(cls, name):
        original = getattr(cls, name, None)
        if original is None or getattr(original, "_trebel_premium_wrapped", False):
            return

        async def wrapped(self, *args, **kwargs):
            _caption_kwargs(args, kwargs)
            return await original(self, *args, **kwargs)

        wrapped._trebel_premium_wrapped = True
        setattr(cls, name, wrapped)

    for cls in (Message, Client):
        for name in ("reply_text", "edit_text", "send_message", "edit_message_text"):
            wrap_text(cls, name)
        for name in ("reply", "edit", "send_photo", "send_video", "send_animation", "send_document"):
            wrap_caption(cls, name)

    Message._trebel_premium_hooks = True
