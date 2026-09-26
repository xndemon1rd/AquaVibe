# Start menu keyboard helpers.
from pyrogram.types import InlineKeyboardButton

import config
from AquaVibe.core.runtime import app
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton


def start_panel(_):
    """Premium private/group start keyboard matching the AquaVibe start UI."""
    return [
        [InlineKeyboardButton(
            text="✚ 𝖠𝖣𝖣 𝖬𝖤 𝖳𝖮 𝖸𝖮𝖴𝖱 𝖢𝖧𝖠𝖳 ✚",
            url=f"https://t.me/{app.username}?startgroup=true",
            aqua_style="primary",
        )],
        [
            InlineKeyboardButton(
                text="≡ 𝖴𝖯𝖣𝖠𝖳𝖤𝖲 ≡",
                url="https://t.me/zxknox",
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
                text="≡ 𝖧𝖤𝖫𝖯 𝖠𝖭𝖣 𝖢𝖮𝖬𝖬𝖠𝖭𝖣 ≡",
                callback_data="open_help",
                aqua_style="success",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔐 𝖲𝖳𝖱𝖨𝖭𝖦 𝖲𝖤𝖲𝖲𝖨𝖮𝖭 𝖦𝖤𝖭𝖤𝖱𝖠𝖳𝖮𝖱",
                callback_data="session_gen_start",
                aqua_style="primary",
            )
        ],
        [
            InlineKeyboardButton(
                text="≡ 𝖮𝖶𝖭𝖤𝖱 ≡",
                callback_data="open_owner",
                aqua_style="danger",
            )
        ],
    ]


def private_panel(_, user_id=None):
    # Same premium layout for the private /start screen.
    return start_panel(_)
