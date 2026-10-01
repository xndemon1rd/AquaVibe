"""AquaVibe Telegram playback card text."""
from html import escape

def now_playing_text(title: str, artist: str = "Artist Name", position: str = "#1", requested_by: str = "@username", elapsed: str = "01:24", duration: str = "03:48", volume: str = "80%") -> str:
    title = escape(str(title)[:80])
    artist = escape(str(artist)[:80])
    position = escape(str(position)[:30])
    requested_by = escape(str(requested_by)[:80])
    elapsed = escape(str(elapsed)[:20])
    duration = escape(str(duration)[:20])
    volume = escape(str(volume)[:20])
    return (
        "🎧 <b>AQUA VIBE • NOW PLAYING</b>\n\n"
        "<blockquote>"
        "╭───────────────╮\n"
        f"│  🎵 <b>{title}</b>\n"
        f"│  👤 {artist}\n"
        "│\n"
        "│  ━━━━━━━━━━━\n"
        f"│  ▶️ {elapsed} ━━━━━ {duration}\n"
        "╰───────────────╯\n\n"
        f"🎚 <b>Volume:</b> {volume}\n"
        f"📍 <b>Position:</b> {position}\n"
        f"👥 <b>Requested by:</b> {requested_by}"
        "</blockquote>\n\n"
        "<b>AquaVibe • Music that flows.</b>"
    )
