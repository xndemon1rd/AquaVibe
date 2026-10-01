"""Shared private-welcome caption (used by /start and the Help → Menu button)."""

from AquaVibe.core.premium_emoji import _utf16_len, custom_emoji_entities, text_link_entity


def welcome_caption(first_name: str | None, user_id: int | None = None, bot_name: str | None = None):
    """Returns (text, entities). When user_id is given, the greeted name is
    a real clickable mention linking to that user's Telegram profile."""
    name = first_name or "there"
    bot = bot_name or "AquaVibe"
    prefix = "✨ 𝖧𝖾𝗒, "
    text = (
        f"{prefix}{name} 🧸\n\n"
        "\"𝗬𝗼𝘂𝗿 𝗴𝗿𝗼𝘂𝗽'𝘀 𝗴𝘂𝗮𝗿𝗱𝗶𝗮𝗻\"\n\n"
        f"💊 𝖨 𝖺𝗆 {bot}, 𝗒𝗈𝗎𝗋 𝗏𝖾𝗋𝗌𝖺𝗍𝗂𝗅𝖾 𝗆𝖺𝗇𝖺𝗀𝖾𝗆𝖾𝗇𝗍 𝖻𝗈𝗍, 𝖽𝖾𝗌𝗂𝗀𝗇𝖾𝖽 𝗍𝗈 𝗁𝖾𝗅𝗉 𝗒𝗈𝗎 𝗍𝖺𝗄𝖾 𝖼𝗈𝗇𝗍𝗋𝗈𝗅 𝗈𝖿 𝗒𝗈𝗎𝗋 𝗀𝗋𝗈𝗎𝗉𝗌 𝗐𝗂𝗍𝗁 𝖾𝖺𝗌𝖾 𝗎𝗌𝗂𝗇𝗀 𝗆𝗒 𝗉𝗈𝗐𝖾𝗋𝖿𝗎𝗅 𝗆𝗈𝖽𝗎𝗅𝖾𝗌 𝖺𝗇𝖽 𝖼𝗈𝗆𝗆𝖺𝗇𝖽𝗌!\n\n"
        "💎 𝖶𝗁𝖺𝗍 𝖨 𝖢𝖺𝗇 𝖣𝗈:\n\n"
        "• 🔄 𝖲𝖾𝖺𝗆𝗅𝖾𝗌𝗌 𝗆𝖺𝗇𝖺𝗀𝖾𝗆𝖾𝗇𝗍 𝗈𝖿 𝗒𝗈𝗎𝗋 𝗀𝗋𝗈𝗎𝗉𝗌\n"
        "• 🔧 𝖯𝗈𝗐𝖾𝗋𝖿𝗎𝗅 𝗆𝗈𝖽𝖾𝗋𝖺𝗍𝗂𝗈𝗇 𝗍𝗈𝗈𝗅𝗌\n"
        "• 🎉 𝖥𝗎𝗇 𝖺𝗇𝖽 𝖾𝗇𝗀𝖺𝗀𝗂𝗇𝗀 𝖿𝖾𝖺𝗍𝗎𝗋𝖾𝗌\n\n"
        "⭐ Need Help?\n"
        "𝖢𝗅𝗂𝖼𝗄 𝗍𝗁𝖾 𝗁𝖾𝗅𝗉 𝖻𝗎𝗍𝗍𝗈𝗇 𝖻𝖾𝗅𝗈𝗐."
    )
    entities = custom_emoji_entities(text, blockquote=False)
    if user_id:
        entities.append(
            text_link_entity(name, f"tg://user?id={user_id}", offset=_utf16_len(prefix))
        )
    entities.sort(key=lambda e: (e.offset, -e.length))
    return text, entities
