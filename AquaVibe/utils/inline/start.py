# Start menu keyboard helpers.
from pyrogram.types import InlineKeyboardButton

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
InlineKeyboardButton = ColoredInlineKeyboardButton


def start_panel(_, owner=False):
    """Premium private/group start keyboard matching the AquaVibe start UI.

    The Owner button is only included when ``owner`` is True (bot owner in private)."""
    rows = [
        [
            InlineKeyboardButton(
                text="✚ 𝖠𝖣𝖣 𝖬𝖤 ✚",
                url=f"https://t.me/{app.username}?startgroup=true",
                aqua_style="primary",
            ),
            InlineKeyboardButton(
                text="≡ 𝖧𝖤𝖫𝖯 ≡",
                callback_data="open_help",
                aqua_style="success",
            ),
        ],
        [
            InlineKeyboardButton(
                text="≡ 𝖴𝖯𝖣𝖠𝖳𝖤𝖲 ≡",
                url="https://t.me/AstrixVeyra",
                aqua_style="success",
            ),
            InlineKeyboardButton(
                text="≡ 𝖲𝖴𝖯𝖯𝖮𝖱𝖳 ≡",
                url="https://t.me/zpaveldurov",
                aqua_style="danger",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔐 𝖦𝖤𝖭𝖤𝖱𝖠𝖳𝖤",
                callback_data="session_gen_start",
                aqua_style="primary",
            ),
            InlineKeyboardButton(
                text="📊 𝖲𝖸𝖲𝖳𝖤𝖬",
                callback_data="open_system",
                aqua_style="success",
            ),
        ],
    ]
    if owner:
        rows.append([
            InlineKeyboardButton(
                text="≡ 𝖮𝖶𝖭𝖤𝖱 ≡",
                callback_data="open_owner",
                aqua_style="danger",
            )
        ])
    return rows


def private_panel(_, user_id=None):
    # Same premium layout for the private /start screen; owner button for the owner only.
    is_owner = user_id is not None and int(user_id) == int(config.OWNER_ID)
    return start_panel(_, owner=is_owner)
