"""Songs-played counter used by /ranking. Never raises: stats must not break playback."""
from datetime import datetime, timezone

from AquaVibe.core.mongo import mongodb

PLAYS = mongodb.aqua_song_plays


async def record_play(chat_id, user_id, name: str = "User", count: int = 1):
    try:
        if not user_id or int(count) < 1:
            return
        await PLAYS.update_one(
            {"chat_id": int(chat_id), "user_id": int(user_id)},
            {
                "$inc": {"plays": int(count)},
                "$set": {"name": str(name or "User")[:64], "last_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
    except Exception:
        return
