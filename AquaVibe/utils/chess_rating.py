"""Group ELO for chess, shared by the in-chat game and the optional Mini App."""
from __future__ import annotations

from typing import Optional

from AquaVibe.core.mongo import mongodb

CH = mongodb.aqua_chess
K_FACTOR = 32
DEFAULT_RATING = 1200


def expected(ra: float, rb: float) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


async def get_rating(chat_id: int, uid: int) -> dict:
    d = await CH.find_one({"type": "rating", "chat_id": int(chat_id), "user_id": int(uid)})
    return d or {"rating": DEFAULT_RATING, "wins": 0, "losses": 0, "draws": 0, "games": 0}


async def apply_result(chat_id: int, white: int, black: int, winner: Optional[int]) -> Optional[dict]:
    """Update both ratings. winner=None means draw. Returns the rating changes."""
    if not chat_id:
        return None  # unrated (e.g. inline games have no group)
    rw, rb = await get_rating(chat_id, white), await get_rating(chat_id, black)
    ra, rb_ = int(rw.get("rating", DEFAULT_RATING)), int(rb.get("rating", DEFAULT_RATING))
    sw = 0.5 if winner is None else (1.0 if int(winner) == int(white) else 0.0)
    ew = expected(ra, rb_)
    new_w = round(ra + K_FACTOR * (sw - ew))
    new_b = round(rb_ + K_FACTOR * ((1 - sw) - (1 - ew)))

    async def _save(uid, new, old_doc, score):
        inc = {"games": 1, "wins": 1 if score == 1 else 0, "losses": 1 if score == 0 else 0, "draws": 1 if score == 0.5 else 0}
        await CH.update_one(
            {"type": "rating", "chat_id": int(chat_id), "user_id": int(uid)},
            {"$set": {"rating": int(new)}, "$inc": inc},
            upsert=True,
        )

    await _save(white, new_w, rw, sw)
    await _save(black, new_b, rb, 1 - sw)
    return {"white": (ra, new_w), "black": (rb_, new_b)}
