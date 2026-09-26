"""Telegram custom/premium emoji helpers.

The IDs below are supplied by the bot owner.  Keep them as integers because
Pyrogram's custom_emoji_id field is a Telegram 64-bit integer (not a string).
"""
from pyrogram.enums import MessageEntityType
from pyrogram.types import MessageEntity

# Current Premium Custom Emoji mapping supplied by the owner.
# IDs are kept as integers because Telegram custom-emoji IDs are 64-bit.
DEFAULT_EMOJI = {
    "❤️": 5285439518130857782,
    "🗓": 5287606810168028257,
    "💌": 5285184156555306745,
    "📫": 5287533898803211359,
    "🧪": 5256169350368353876,
    "📡": 5256134032852278918,
    "💖": 5255877597534905292,
    "💓": 5256227233642605352,
    "📞": 5285238101344544669,
    "✍️": 5258500400918587241,
    "🎯": 5256131095094652290,
    "⌨️": 5258361295517806281,
    "🥂": 5260567255145539253,
    "💋": 5289850733011693663,
    "🫶": 5285338659413846416,
    "💍": 5262922516426420894,
    "🧩": 5265120027853481187,
    "⚙️": 5267334530171169409,
    "🚹": 5292122921035133343,
    "⭐️": 5289944036881230584,
    "📼": 5271721134889395048,
    "☁️": 5274002879215067737,
    "🔑": 5278573677900752088,
    "🎲": 5280816565657300091,
    "🎭": 5276239041052828276,
    "🕯": 5276412965753480690,
    "🎶": 5276352986535194063,
    "🎈": 5278651867780377852,
    "💔": 5278454020111887994,
    "🚧": 5280569974404966639,
    "📦": 5305715161087110779,
    "📥": 5305715161087110779,
    "🍾": 5280774071250872500,
    "🃏": 5280939169793732849,
    "💝": 5280826864988873394,
    "🍭": 5287295223175604777,
    "🔓": 5291873529464122510,
}

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
        else:
            cursor += 1
    return entities



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
