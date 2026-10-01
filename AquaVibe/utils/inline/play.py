# Authored By Dev © 2025
from pyrogram.types import InlineKeyboardButton
from AquaVibe.utils.colored_buttons import ColoredInlineKeyboardButton
InlineKeyboardButton = ColoredInlineKeyboardButton


def track_markup(_, videoid, user_id, channel, fplay):
    return [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            )
        ],
    ]


def stream_markup(_, chat_id):
    # Full player keyboard matching the AquaVibe Now Playing card design.
    return [
        [
            InlineKeyboardButton(text="⏮", callback_data=f"stream_admin Replay|{chat_id}", color="blue"),
            InlineKeyboardButton(text="⏸", callback_data=f"stream_admin Pause|{chat_id}", color="green"),
            InlineKeyboardButton(text="⏭", callback_data=f"stream_admin Skip|{chat_id}", color="blue"),
        ],
        [
            InlineKeyboardButton(text="🔀 Shuffle", callback_data=f"stream_admin Shuffle|{chat_id}", color="green"),
            InlineKeyboardButton(text="🔁 Loop", callback_data=f"stream_admin Loop|{chat_id}", color="green"),
        ],
        [
            InlineKeyboardButton(text="📋 Queue", callback_data=f"stream_admin Queue|{chat_id}", color="blue"),
            InlineKeyboardButton(text="🔊 Volume", callback_data=f"stream_admin VolumeMenu|{chat_id}", color="blue"),
        ],
        [
            InlineKeyboardButton(text="📹 Vplay", callback_data=f"stream_admin Vplay|{chat_id}", color="green"),
            InlineKeyboardButton(text="📝 Lyrics", callback_data=f"stream_admin Lyrics|{chat_id}", color="blue"),
            InlineKeyboardButton(text="🧾 Help", callback_data=f"stream_admin PHelp|{chat_id}", color="blue"),
        ],
    ]


def volume_menu_markup(_, chat_id):
    # Temporary sub-keyboard shown in place of the player controls while the
    # user picks a volume level; "⬅ Back" restores stream_markup().
    return [
        [
            InlineKeyboardButton(text="20%", callback_data=f"stream_admin SetVolume|{chat_id}_20", color="green"),
            InlineKeyboardButton(text="40%", callback_data=f"stream_admin SetVolume|{chat_id}_40", color="green"),
            InlineKeyboardButton(text="60%", callback_data=f"stream_admin SetVolume|{chat_id}_60", color="green"),
        ],
        [
            InlineKeyboardButton(text="80%", callback_data=f"stream_admin SetVolume|{chat_id}_80", color="green"),
            InlineKeyboardButton(text="100%", callback_data=f"stream_admin SetVolume|{chat_id}_100", color="green"),
            InlineKeyboardButton(text="🔇 Mute", callback_data=f"stream_admin SetVolume|{chat_id}_0", color="red"),
        ],
        [InlineKeyboardButton(text="⬅ Back", callback_data=f"stream_admin VolumeBack|{chat_id}", color="blue")],
    ]


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"SayaPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}"
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"SayaPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            ),
        ],
    ]

    return buttons

def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    return [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            )
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            )
        ],
    ]


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay, mode="a"):
    short_query = query[:20]
    return [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{short_query}|{user_id}|{channel}|{fplay}|{mode}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {short_query}|{user_id}",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{short_query}|{user_id}|{channel}|{fplay}|{mode}",
            ),
        ],
    ]


def aqua_search_markup(token, user_id, page, total, video, channel, fplay, results):
    start=page*3
    items=results[start:start+3]
    rows=[]
    for offset,item in enumerate(items):
        idx=start+offset
        title=str(item.get("title") or "Unknown")[:38]
        artist=str(item.get("artist") or "")[:22]
        label=f"{idx+1} • {title}" + (f" — {artist}" if artist else "")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"AqPick {token}|{idx}|{user_id}|{'v' if video else 'a'}|{channel}|{fplay}")])
    nav=[]
    if page>0:
        nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"AqPage {token}|{page-1}|{user_id}"))
    if start+3<total:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"AqPage {token}|{page+1}|{user_id}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="✕ Close", callback_data=f"forceclose {token}|{user_id}")])
    return rows
