"""Shared wallet helpers so every feature shows the same currency and moves money safely."""
from __future__ import annotations

import config
from AquaVibe.core.mongo import mongodb

EC = mongodb.aqua_economy


def money(n) -> str:
    return f"{config.CURRENCY_SYMBOL}{int(n):,}"


async def wallet(chat_id, uid, name: str | None = None) -> dict:
    """Return the wallet, creating it with the starting balance if needed."""
    flt = {"chat_id": int(chat_id), "user_id": int(uid)}
    d = await EC.find_one(flt)
    if not d:
        d = {**flt, "balance": config.ECONOMY_START_BALANCE, "daily_at": 0, "name": name or "User"}
        await EC.insert_one(dict(d))
    return d


async def credit(chat_id, uid, amount: int, name: str | None = None) -> None:
    await wallet(chat_id, uid, name)
    upd = {"$inc": {"balance": int(amount)}}
    if name:
        upd["$set"] = {"name": name}
    await EC.update_one({"chat_id": int(chat_id), "user_id": int(uid)}, upd)


async def debit(chat_id, uid, amount: int) -> bool:
    """Take money only if the balance covers it (atomic). Returns False when it can't."""
    amount = int(amount)
    if amount <= 0:
        return True
    res = await EC.update_one(
        {"chat_id": int(chat_id), "user_id": int(uid), "balance": {"$gte": amount}},
        {"$inc": {"balance": -amount}},
    )
    return res.modified_count == 1
