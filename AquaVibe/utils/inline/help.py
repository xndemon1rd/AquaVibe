# Authored By Dev © 2025
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from AquaVibe.core.runtime import app
from AquaVibe.utils.command_catalog import COMMAND_PAGE_COUNT, command_page
from AquaVibe.utils.styled_buttons import StyledInlineKeyboardButton
InlineKeyboardButton = StyledInlineKeyboardButton


TOTAL_SECTIONS = 30


def generate_help_buttons(_, start: int, end: int, current_page: int):
    """Create a grid of three buttons per row for the given range."""
    buttons, per_row = [], 3
    for idx, i in enumerate(range(start, end + 1)):
        if idx % per_row == 0:
            buttons.append([])
        buttons[-1].append(
            InlineKeyboardButton(
                text=_[f"H_B_{i}"],
                callback_data=f"help_callback hb{i}_p{current_page}"
            )
        )
    return buttons


def first_page(_):
    buttons = generate_help_buttons(_, 1, 15, current_page=1)
    buttons.append([InlineKeyboardButton(text="📚 Aʟʟ Cᴏᴍᴍᴀɴᴅs", callback_data="help_all_1")])
    buttons.append(
        [
            InlineKeyboardButton(text="๏ ᴍᴇɴᴜ ๏", callback_data="back_to_main"),
            InlineKeyboardButton(text="๏ ɴᴇxᴛ ๏", callback_data="help_next_2")
        ]
    )
    return InlineKeyboardMarkup(buttons)


def second_page(_):
    buttons = generate_help_buttons(_, 16, TOTAL_SECTIONS, current_page=2)
    buttons.append([InlineKeyboardButton(text="📚 Aʟʟ Cᴏᴍᴍᴀɴᴅs", callback_data="help_all_1")])
    buttons.append(
        [
            InlineKeyboardButton(text="๏ ʙᴀᴄᴋ ๏", callback_data="help_prev_1"),
            InlineKeyboardButton(text="๏ ᴍᴇɴᴜ ๏", callback_data="back_to_main")
        ]
    )
    return InlineKeyboardMarkup(buttons)


def action_sub_menu(_, current_page: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_[ "H_B_S_1" ],
                    callback_data="action_prom_1"
                ),
                InlineKeyboardButton(
                    text=_[ "H_B_S_2" ],
                    callback_data="action_pun_1"
                )
            ],
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"],
                    callback_data=f"help_back_{current_page}"
                )
            ]
        ]
    )


def help_back_markup(_, current_page: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"],
                    callback_data=f"help_back_{current_page}"
                ),
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close"
                ),
            ]
        ]
    )


def all_commands_markup(_, page: int = 1):
    """Build a paginated, callback-backed list of every bot command."""
    page = max(1, min(int(page), COMMAND_PAGE_COUNT))
    commands = command_page(page)
    buttons = []
    for i in range(0, len(commands), 2):
        row = [InlineKeyboardButton(text=f"/{cmd}", callback_data=f"noop_cmd:{cmd}") for cmd in commands[i:i+2]]
        buttons.append(row)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="๏ ʙᴀᴄᴋ ๏", callback_data=f"commands_all_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{COMMAND_PAGE_COUNT}", callback_data="commands_page_info"))
    if page < COMMAND_PAGE_COUNT:
        nav.append(InlineKeyboardButton(text="๏ ɴᴇxᴛ ๏", callback_data=f"commands_all_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([
        InlineKeyboardButton(text="๏ ʜᴇʟᴘ ๏", callback_data="open_help"),
        InlineKeyboardButton(text="๏ ᴍᴇɴᴜ ๏", callback_data="back_to_main"),
    ])
    return InlineKeyboardMarkup(buttons)


def private_help_panel(_):
    return [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?start=help"
            ),
        ],
    ]
