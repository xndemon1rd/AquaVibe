# Authored By Dev © 2025
import random
from typing import Dict, List, Union

from AquaVibe.core.runtime import userbot
from AquaVibe.core.mongo import mongodb

authdb = mongodb.adminauth
authuserdb = mongodb.authuser
autoenddb = mongodb.autoend
assdb = mongodb.assistants
blacklist_chatdb = mongodb.blacklistChat
blockeddb = mongodb.blockedusers
chatsdb = mongodb.chats
channeldb = mongodb.cplaymode
countdb = mongodb.upcount
gbansdb = mongodb.gban
langdb = mongodb.language
onoffdb = mongodb.onoffper
playmodedb = mongodb.playmode
playtypedb = mongodb.playtypedb
skipdb = mongodb.skipmode
adminsdb = mongodb.admins
usersdb = mongodb.tgusersdb

# Economy / monetization collections
economydb = mongodb.trabelx_economy
grouprefdb = mongodb.trabelx_group_referrals
paymentdb = mongodb.trabelx_payments
bannerdb = mongodb.trabelx_banners
historydb = mongodb.trabelx_song_history
playlistdb = mongodb.trabelx_user_playlists


active = []
activevideo = []
assistantdict = {}
autoend = {}
count = {}
channelconnect = {}
langm = {}
loop = {}
maintenance = []
nonadmin = {}
pause = {}
playmode = {}
playtype = {}
skipmode = {}
mute = {}

async def get_assistant_number(chat_id: int) -> str:
    assistant = assistantdict.get(chat_id)
    return assistant


async def get_client(assistant: int):
    if int(assistant) == 1:
        return userbot.one
    elif int(assistant) == 2:
        return userbot.two
    elif int(assistant) == 3:
        return userbot.three
    elif int(assistant) == 4:
        return userbot.four
    elif int(assistant) == 5:
        return userbot.five


async def set_assistant_new(chat_id, number):
    number = int(number)
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": number}},
        upsert=True,
    )


async def set_assistant(chat_id):
    from AquaVibe.core.userbot import assistants

    if not assistants:
        raise RuntimeError(
            "No Telegram voice assistant is available. Configure ASSISTANTS_ENABLED=true "
            "and at least one valid STRING_SESSION, then restart the bot."
        )
    ran_assistant = random.choice(assistants)
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    userbot = await get_client(ran_assistant)
    return userbot


async def get_assistant(chat_id: int) -> str:
    from AquaVibe.core.userbot import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if not dbassistant:
            userbot = await set_assistant(chat_id)
            return userbot
        else:
            got_assis = dbassistant["assistant"]
            if got_assis in assistants:
                assistantdict[chat_id] = got_assis
                userbot = await get_client(got_assis)
                return userbot
            else:
                userbot = await set_assistant(chat_id)
                return userbot
    else:
        if assistant in assistants:
            userbot = await get_client(assistant)
            return userbot
        else:
            userbot = await set_assistant(chat_id)
            return userbot


async def set_calls_assistant(chat_id):
    from AquaVibe.core.userbot import assistants

    if not assistants:
        raise RuntimeError(
            "No Telegram voice assistant is available. Configure ASSISTANTS_ENABLED=true "
            "and at least one valid STRING_SESSION, then restart the bot."
        )
    ran_assistant = random.choice(assistants)
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    return ran_assistant


async def group_assistant(self, chat_id: int) -> int:
    """Return a started PyTgCalls assistant for this chat.

    ``self.one``..``self.five`` are PyTgCalls objects, not Pyrogram
    clients, so checking their ``is_connected`` attribute is incorrect and
    can make a healthy assistant look disconnected.  The Call.start()
    method only keeps a wrapper when its PyTgCalls client successfully
    starts, so wrapper presence is the authoritative playback check here.
    """
    clients = {
        1: self.one,
        2: self.two,
        3: self.three,
        4: self.four,
        5: self.five,
    }

    assigned = assistantdict.get(chat_id)
    if not assigned:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        assigned = dbassistant.get("assistant") if dbassistant else None

    try:
        assigned = int(assigned) if assigned is not None else None
    except (TypeError, ValueError):
        assigned = None

    # Prefer the chat's existing assignment when that PyTgCalls wrapper is
    # actually available. Do not use Pyrogram ``is_connected`` here: the
    # object returned by this function must be a PyTgCalls instance.
    selected = clients.get(assigned) if assigned else None
    if selected is not None:
        assistantdict[chat_id] = assigned
        return selected

    # A stale MongoDB assignment must not block playback. Pick any wrapper
    # that was successfully started by Call.start().
    for number, candidate in clients.items():
        if candidate is not None:
            assistantdict[chat_id] = number
            await assdb.update_one(
                {"chat_id": chat_id},
                {"$set": {"assistant": number}},
                upsert=True,
            )
            return candidate

    raise RuntimeError(
        "No PyTgCalls assistant is available. Check the assistant startup "
        "logs and make sure at least one valid STRING_SESSION is configured."
    )


async def is_skipmode(chat_id: int) -> bool:
    mode = skipmode.get(chat_id)
    if not mode:
        user = await skipdb.find_one({"chat_id": chat_id})
        if not user:
            skipmode[chat_id] = True
            return True
        skipmode[chat_id] = False
        return False
    return mode


async def skip_on(chat_id: int):
    skipmode[chat_id] = True
    user = await skipdb.find_one({"chat_id": chat_id})
    if user:
        return await skipdb.delete_one({"chat_id": chat_id})


async def skip_off(chat_id: int):
    skipmode[chat_id] = False
    user = await skipdb.find_one({"chat_id": chat_id})
    if not user:
        return await skipdb.insert_one({"chat_id": chat_id})


async def get_upvote_count(chat_id: int) -> int:
    mode = count.get(chat_id)
    if not mode:
        mode = await countdb.find_one({"chat_id": chat_id})
        if not mode:
            return 5
        count[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_upvotes(chat_id: int, mode: int):
    count[chat_id] = mode
    await countdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def is_autoend() -> bool:
    chat_id = 1234
    user = await autoenddb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def autoend_on():
    chat_id = 1234
    await autoenddb.insert_one({"chat_id": chat_id})


async def autoend_off():
    chat_id = 1234
    await autoenddb.delete_one({"chat_id": chat_id})


async def get_loop(chat_id: int) -> int:
    lop = loop.get(chat_id)
    if not lop:
        return 0
    return lop


async def set_loop(chat_id: int, mode: int):
    loop[chat_id] = mode


async def get_cmode(chat_id: int) -> int:
    mode = channelconnect.get(chat_id)
    if not mode:
        mode = await channeldb.find_one({"chat_id": chat_id})
        if not mode:
            return None
        channelconnect[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_cmode(chat_id: int, mode: int):
    channelconnect[chat_id] = mode
    await channeldb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playtype(chat_id: int) -> str:
    mode = playtype.get(chat_id)
    if not mode:
        mode = await playtypedb.find_one({"chat_id": chat_id})
        if not mode:
            playtype[chat_id] = "Everyone"
            return "Everyone"
        playtype[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playtype(chat_id: int, mode: str):
    playtype[chat_id] = mode
    await playtypedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playmode(chat_id: int) -> str:
    mode = playmode.get(chat_id)
    if not mode:
        mode = await playmodedb.find_one({"chat_id": chat_id})
        if not mode:
            playmode[chat_id] = "Direct"
            return "Direct"
        playmode[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playmode(chat_id: int, mode: str):
    playmode[chat_id] = mode
    await playmodedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_lang(chat_id: int) -> str:
    mode = langm.get(chat_id)
    if not mode:
        lang = await langdb.find_one({"chat_id": chat_id})
        if not lang:
            langm[chat_id] = "en"
            return "en"
        langm[chat_id] = lang["lang"]
        return lang["lang"]
    return mode


async def set_lang(chat_id: int, lang: str):
    langm[chat_id] = lang
    await langdb.update_one({"chat_id": chat_id}, {"$set": {"lang": lang}}, upsert=True)


async def is_music_playing(chat_id: int) -> bool:
    mode = pause.get(chat_id)
    if not mode:
        return False
    return mode


async def music_on(chat_id: int):
    pause[chat_id] = True


async def music_off(chat_id: int):
    pause[chat_id] = False

async def is_muted(chat_id: int) -> bool:
    mode = mute.get(chat_id)
    if not mode:
        return False
    return mode


async def get_active_chats() -> list:
    return active


async def is_active_chat(chat_id: int) -> bool:
    if chat_id not in active:
        return False
    else:
        return True


async def add_active_chat(chat_id: int):
    if chat_id not in active:
        active.append(chat_id)


async def remove_active_chat(chat_id: int):
    if chat_id in active:
        active.remove(chat_id)


async def get_active_video_chats() -> list:
    return activevideo


async def is_active_video_chat(chat_id: int) -> bool:
    if chat_id not in activevideo:
        return False
    else:
        return True


async def add_active_video_chat(chat_id: int):
    if chat_id not in activevideo:
        activevideo.append(chat_id)


async def remove_active_video_chat(chat_id: int):
    if chat_id in activevideo:
        activevideo.remove(chat_id)


async def check_nonadmin_chat(chat_id: int) -> bool:
    user = await authdb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def is_nonadmin_chat(chat_id: int) -> bool:
    mode = nonadmin.get(chat_id)
    if not mode:
        user = await authdb.find_one({"chat_id": chat_id})
        if not user:
            nonadmin[chat_id] = False
            return False
        nonadmin[chat_id] = True
        return True
    return mode


async def add_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = True
    is_admin = await check_nonadmin_chat(chat_id)
    if is_admin:
        return
    return await authdb.insert_one({"chat_id": chat_id})


async def remove_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = False
    is_admin = await check_nonadmin_chat(chat_id)
    if not is_admin:
        return
    return await authdb.delete_one({"chat_id": chat_id})


async def is_on_off(on_off: int) -> bool:
    onoff = await onoffdb.find_one({"on_off": on_off})
    if not onoff:
        return False
    return True


async def add_on(on_off: int):
    is_on = await is_on_off(on_off)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": on_off})


async def add_off(on_off: int):
    is_off = await is_on_off(on_off)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": on_off})


async def is_maintenance():
    """Return True only when maintenance mode is actually enabled.

    MongoDB is the source of truth so a stale in-memory cache cannot block
    /play after maintenance has been disabled elsewhere.
    """
    get = await onoffdb.find_one({"on_off": 1})
    enabled = bool(get)
    maintenance.clear()
    maintenance.append(1 if enabled else 2)
    return enabled


async def maintenance_off():
    maintenance.clear()
    maintenance.append(2)
    is_off = await is_on_off(1)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": 1})


async def maintenance_on():
    maintenance.clear()
    maintenance.append(1)
    is_on = await is_on_off(1)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": 1})


async def is_served_user(user_id: int) -> bool:
    user = await usersdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def get_served_users() -> list:
    users_list = []
    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(user)
    return users_list


async def add_served_user(user_id: int):
    is_served = await is_served_user(user_id)
    if is_served:
        return
    return await usersdb.insert_one({"user_id": user_id})


async def get_served_chats() -> list:
    chats_list = []
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat)
    return chats_list


async def is_served_chat(chat_id: int) -> bool:
    chat = await chatsdb.find_one({"chat_id": chat_id})
    if not chat:
        return False
    return True


async def add_served_chat(chat_id: int):
    is_served = await is_served_chat(chat_id)
    if is_served:
        return
    return await chatsdb.insert_one({"chat_id": chat_id})

# New function to remove served chat
async def remove_served_chat(chat_id: int):
    if await is_served_chat(chat_id):
        await chatsdb.delete_one({"chat_id": chat_id})


async def blacklisted_chats() -> list:
    chats_list = []
    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat["chat_id"])
    return chats_list


async def blacklist_chat(chat_id: int) -> bool:
    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.insert_one({"chat_id": chat_id})
        return True
    return False


async def whitelist_chat(chat_id: int) -> bool:
    if await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.delete_one({"chat_id": chat_id})
        return True
    return False


async def _get_authusers(chat_id: int) -> Dict[str, int]:
    _notes = await authuserdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes.get("notes", {})


async def get_authuser_names(chat_id: int) -> List[str]:
    notes = await _get_authusers(chat_id)
    return list(notes.keys())


async def get_authuser(chat_id: int, name: str) -> Union[bool, dict]:
    name = name
    _notes = await _get_authusers(chat_id)
    if name in _notes:
        return _notes[name]
    else:
        return False


async def save_authuser(chat_id: int, name: str, note: dict):
    name = name
    _notes = await _get_authusers(chat_id)
    _notes[name] = note

    await authuserdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_authuser(chat_id: int, name: str) -> bool:
    notesd = await _get_authusers(chat_id)
    name = name
    if name in notesd:
        del notesd[name]
        await authuserdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def get_gbanned() -> list:
    results = []
    async for user in gbansdb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def is_gbanned_user(user_id: int) -> bool:
    user = await gbansdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if is_gbanned:
        return
    return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if not is_gbanned:
        return
    return await gbansdb.delete_one({"user_id": user_id})


async def get_admins() -> list:
    admins = await adminsdb.find_one({"admin": "admin"})
    if not admins:
        return []
    return admins["admins"]


async def add_admin(user_id: int) -> bool:
    admins = await get_admins()
    admins.append(user_id)
    await adminsdb.update_one(
        {"admin": "admin"}, {"$set": {"admins": admins}}, upsert=True
    )
    return True


async def remove_admin(user_id: int) -> bool:
    admins = await get_admins()
    admins.remove(user_id)
    await adminsdb.update_one(
        {"admin": "admin"}, {"$set": {"admins": admins}}, upsert=True
    )
    return True


async def get_banned_users() -> list:
    results = []
    async for user in blockeddb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def get_banned_count() -> int:
    users = blockeddb.find({"user_id": {"$gt": 0}})
    users = await users.to_list(length=100000)
    return len(users)


async def is_banned_user(user_id: int) -> bool:
    user = await blockeddb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if is_gbanned:
        return
    return await blockeddb.insert_one({"user_id": user_id})


async def remove_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if not is_gbanned:
        return
    return await blockeddb.delete_one({"user_id": user_id})


# ─────────────────────────────────────────────────────────────────────────────
# AquaVibe Economy / Membership / VIP
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime, timezone, timedelta
from config import OWNER_ID

async def ensure_economy_user(user_id: int):
    now = datetime.now(timezone.utc)
    uid = int(user_id)
    await economydb.update_one(
        {"user_id": uid},
        {"$setOnInsert": {
            "user_id": uid,
            "coins": 10_000_000 if uid == int(OWNER_ID) else 0,
            "daily_claim": None,
            "weekly_claim": None,
            "referred_by": None,
            "vip_until": None,
            "membership_until": None,
            "membership_banner": None,
            "profile_photo": None,
            "profile_banner": None,
            "custom_banners": [],
            "hide_coins": False,
            "hide_member": False,
            "hide_vip": False,
            "created_at": now,
        }},
        upsert=True,
    )
    # Owner always has VIP and at least the requested 10,000,000 coin balance.
    if uid == int(OWNER_ID):
        await economydb.update_one(
            {"user_id": uid, "coins": {"$lt": 10_000_000}},
            {"$set": {"coins": 10_000_000, "vip_forever": True, "updated_at": now}},
        )
        await economydb.update_one(
            {"user_id": uid},
            {"$set": {"vip_forever": True, "updated_at": now}},
        )

async def add_song_history(user_id: int, title: str, source: str = "", vidid: str = "", link: str = ""):
    if not user_id or not title:
        return
    await historydb.insert_one({
        "user_id": int(user_id), "title": str(title)[:300], "source": str(source)[:80],
        "vidid": str(vidid)[:200], "link": str(link)[:1000],
        "played_at": datetime.now(timezone.utc),
    })
    # Keep the database bounded per user.
    docs = await historydb.find({"user_id": int(user_id)}, {"_id": 1}).sort("played_at", -1).skip(50).to_list(length=100)
    if docs:
        await historydb.delete_many({"_id": {"$in": [d["_id"] for d in docs]}})

async def get_song_history(user_id: int, limit: int = 20) -> list:
    return await historydb.find({"user_id": int(user_id)}).sort("played_at", -1).limit(max(1, min(int(limit), 50))).to_list(length=max(1, min(int(limit), 50)))


async def get_song_count(user_id: int) -> int:
    """Return the total number of recorded plays for a user."""
    try:
        return int(await historydb.count_documents({"user_id": int(user_id)}))
    except Exception:
        rows = await get_song_history(user_id, 50)
        return len(rows)


async def set_profile_photo(user_id: int, file_id: str | None):
    await ensure_economy_user(user_id)
    await economydb.update_one({"user_id": int(user_id)}, {"$set": {"profile_photo": file_id, "updated_at": datetime.now(timezone.utc)}})


async def get_profile_photo(user_id: int):
    data = await get_economy(user_id)
    return data.get("profile_photo")


async def set_profile_banner(user_id: int, file_id: str | None):
    await ensure_economy_user(user_id)
    await economydb.update_one({"user_id": int(user_id)}, {"$set": {"profile_banner": file_id, "updated_at": datetime.now(timezone.utc)}})


async def get_profile_banner(user_id: int):
    data = await get_economy(user_id)
    return data.get("profile_banner")


async def add_custom_banner(user_id: int, file_id: str) -> int:
    await ensure_economy_user(user_id)
    await economydb.update_one(
        {"user_id": int(user_id)},
        {"$push": {"custom_banners": file_id}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return len(await get_custom_banners(user_id))


async def get_custom_banners(user_id: int) -> list[str]:
    data = await get_economy(user_id)
    return list(data.get("custom_banners") or [])


async def remove_custom_banner(user_id: int, file_id: str) -> bool:
    await ensure_economy_user(user_id)
    result = await economydb.update_one(
        {"user_id": int(user_id)},
        {"$pull": {"custom_banners": file_id}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return bool(result.modified_count)


async def get_profile_hides(user_id: int) -> dict:
    data = await get_economy(user_id)
    return {
        "coins": bool(data.get("hide_coins", False)),
        "member": bool(data.get("hide_member", False)),
        "vip": bool(data.get("hide_vip", False)),
    }


async def toggle_profile_hide(user_id: int, field: str) -> bool:
    if field not in {"coins", "member", "vip"}:
        raise ValueError("invalid profile hide field")
    await ensure_economy_user(user_id)
    key = f"hide_{field}"
    data = await get_economy(user_id)
    value = not bool(data.get(key, False))
    await economydb.update_one({"user_id": int(user_id)}, {"$set": {key: value, "updated_at": datetime.now(timezone.utc)}})
    return value

async def create_user_playlist(user_id: int, name: str) -> bool:
    name = str(name).strip()[:60]
    if not name:
        return False
    result = await playlistdb.update_one(
        {"user_id": int(user_id), "name_lower": name.lower()},
        {"$setOnInsert": {"user_id": int(user_id), "name": name, "name_lower": name.lower(), "tracks": [], "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return bool(result.upserted_id)

async def get_user_playlists(user_id: int) -> list:
    return await playlistdb.find({"user_id": int(user_id)}).sort("name_lower", 1).to_list(length=100)

async def get_user_playlist(user_id: int, name: str):
    return await playlistdb.find_one({"user_id": int(user_id), "name_lower": str(name).strip().lower()})

async def add_user_playlist_track(user_id: int, name: str, track: dict) -> bool:
    result = await playlistdb.update_one(
        {"user_id": int(user_id), "name_lower": str(name).strip().lower()},
        {"$push": {"tracks": track}},
    )
    return bool(result.modified_count)

async def remove_user_playlist_track(user_id: int, name: str, index: int) -> bool:
    pl = await get_user_playlist(user_id, name)
    if not pl or index < 1 or index > len(pl.get("tracks", [])):
        return False
    tracks = pl.get("tracks", [])
    tracks.pop(index - 1)
    await playlistdb.update_one({"_id": pl["_id"]}, {"$set": {"tracks": tracks, "updated_at": datetime.now(timezone.utc)}})
    return True

async def delete_user_playlist(user_id: int, name: str) -> bool:
    result = await playlistdb.delete_one({"user_id": int(user_id), "name_lower": str(name).strip().lower()})
    return bool(result.deleted_count)

async def get_economy(user_id: int) -> dict:
    await ensure_economy_user(user_id)
    return await economydb.find_one({"user_id": int(user_id)}) or {"user_id": int(user_id), "coins": 0}

async def get_coins(user_id: int) -> int:
    data = await get_economy(user_id)
    return int(data.get("coins", 0))

async def add_coins(user_id: int, amount: int, reason: str = "") -> int:
    await ensure_economy_user(user_id)
    await economydb.update_one(
        {"user_id": int(user_id)},
        {"$inc": {"coins": int(amount)}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return await get_coins(user_id)

async def remove_coins(user_id: int, amount: int, reason: str = "") -> bool:
    await ensure_economy_user(user_id)
    result = await economydb.update_one(
        {"user_id": int(user_id), "coins": {"$gte": int(amount)}},
        {"$inc": {"coins": -int(amount)}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0

async def force_remove_coins(user_id: int, amount: int, reason: str = "") -> int:
    """Debit a tracked reward even if the user already spent it."""
    await ensure_economy_user(user_id)
    await economydb.update_one(
        {"user_id": int(user_id)},
        {"$inc": {"coins": -int(amount)}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return await get_coins(user_id)

async def set_referrer(user_id: int, referrer_id: int) -> bool:
    await ensure_economy_user(user_id)
    if int(user_id) == int(referrer_id):
        return False
    result = await economydb.update_one(
        {"user_id": int(user_id), "referred_by": None},
        {"$set": {"referred_by": int(referrer_id), "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0

async def get_referrer(user_id: int):
    data = await get_economy(user_id)
    return data.get("referred_by")

async def claim_daily_reward(user_id: int, amount: int = 100):
    await ensure_economy_user(user_id)
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    result = await economydb.update_one(
        {"user_id": int(user_id), "daily_claim": {"$ne": today}},
        {"$set": {"daily_claim": today, "updated_at": now}},
    )
    if result.modified_count:
        return await add_coins(user_id, int(amount), "daily")
    return 0

async def claim_weekly_reward(user_id: int, amount: int = 300):
    await ensure_economy_user(user_id)
    now = datetime.now(timezone.utc)
    iso = now.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    result = await economydb.update_one(
        {"user_id": int(user_id), "weekly_claim": {"$ne": week}},
        {"$set": {"weekly_claim": week, "updated_at": now}},
    )
    if result.modified_count:
        return await add_coins(user_id, int(amount), "weekly")
    return 0

async def set_vip(user_id: int, until: datetime):
    await ensure_economy_user(user_id)
    await economydb.update_one({"user_id": int(user_id)}, {"$set": {"vip_until": until, "updated_at": datetime.now(timezone.utc)}})

async def set_membership(user_id: int, until: datetime):
    await ensure_economy_user(user_id)
    await economydb.update_one({"user_id": int(user_id)}, {"$set": {"membership_until": until, "updated_at": datetime.now(timezone.utc)}})

async def is_vip(user_id: int) -> bool:
    if int(user_id) == int(OWNER_ID):
        return True
    data = await get_economy(user_id)
    until = data.get("vip_until")
    return bool(until and until > datetime.now(timezone.utc))

async def is_member(user_id: int) -> bool:
    data = await get_economy(user_id)
    until = data.get("membership_until")
    return bool(until and until > datetime.now(timezone.utc))

async def get_banner(slot: int):
    item = await bannerdb.find_one({"slot": int(slot)})
    return item.get("file_id") if item else None

async def set_banner(slot: int, file_id: str):
    await bannerdb.update_one({"slot": int(slot)}, {"$set": {"slot": int(slot), "file_id": file_id}}, upsert=True)

async def set_user_banner(user_id: int, file_id):
    await ensure_economy_user(user_id)
    await economydb.update_one({"user_id": int(user_id)}, {"$set": {"membership_banner": file_id}})

async def get_user_banner(user_id: int):
    data = await get_economy(user_id)
    return data.get("membership_banner")

async def save_payment(user_id: int, payload: str, stars: int, status: str = "pending"):
    await paymentdb.insert_one({
        "user_id": int(user_id), "payload": payload, "stars": int(stars),
        "status": status, "created_at": datetime.now(timezone.utc)
    })

async def mark_payment_paid(payload: str, telegram_charge_id: str = ""):
    await paymentdb.update_many(
        {"payload": payload},
        {"$set": {"status": "paid", "telegram_charge_id": telegram_charge_id, "paid_at": datetime.now(timezone.utc)}},
    )

async def record_group_referral(chat_id: int, inviter_id: int, referred_user_id: int, reward: int = 1000) -> bool:
    exists = await grouprefdb.find_one({"chat_id": int(chat_id)})
    if exists:
        return False
    await grouprefdb.insert_one({
        "chat_id": int(chat_id), "inviter_id": int(inviter_id),
        "referred_user_id": int(referred_user_id), "reward": int(reward),
        "active": True, "created_at": datetime.now(timezone.utc)
    })
    return True

async def get_group_referral(chat_id: int):
    return await grouprefdb.find_one({"chat_id": int(chat_id)})

async def deactivate_group_referral(chat_id: int):
    ref = await grouprefdb.find_one({"chat_id": int(chat_id), "active": True})
    if not ref:
        return None
    await grouprefdb.update_one({"_id": ref["_id"]}, {"$set": {"active": False, "removed_at": datetime.now(timezone.utc)}})
    return ref

async def payment_already_processed(charge_id: str) -> bool:
    if not charge_id:
        return False
    return bool(await paymentdb.find_one({"telegram_charge_id": charge_id, "status": "paid"}))
