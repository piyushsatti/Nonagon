from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Iterable, Tuple

from app.domain.models.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID
from app.domain.models.QuestModel import Quest, QuestStatus
from app.domain.models.UserModel import User
from app.infra.serialization import to_bson
from pymongo import ASCENDING


_USER_INDEX_CACHE: set[str] = set()
_QUEST_INDEX_CACHE: set[str] = set()
_CHAR_INDEX_CACHE: set[str] = set()

_USER_INDEXES: Tuple[Tuple[Iterable[Tuple[str, int]], dict], ...] = (
    ((("guild_id", ASCENDING), ("user_id.number", ASCENDING)), {"unique": True, "name": "guild_user_number"}),
    ((("guild_id", ASCENDING), ("discord_id", ASCENDING)), {"unique": True, "sparse": True, "name": "guild_discord_id"}),
)

_QUEST_INDEXES: Tuple[Tuple[Iterable[Tuple[str, int]], dict], ...] = (
    ((("guild_id", ASCENDING), ("quest_id.number", ASCENDING)), {"unique": True, "name": "guild_quest_number"}),
    ((("guild_id", ASCENDING), ("channel_id", ASCENDING), ("message_id", ASCENDING)), {"unique": True, "name": "guild_channel_message"}),
)

_CHAR_INDEXES: Tuple[Tuple[Iterable[Tuple[str, int]], dict], ...] = (
    ((("guild_id", ASCENDING), ("character_id.number", ASCENDING)), {"unique": True, "name": "guild_character_number"}),
    ((("guild_id", ASCENDING), ("owner_id.number", ASCENDING)), {"name": "guild_character_owner"}),
)


def _ensure_indexes(cache: set[str], coll, guild_key: str, specs: Tuple[Tuple[Iterable[Tuple[str, int]], dict], ...]) -> None:
    if guild_key in cache:
        return
    for keys, kwargs in specs:
        coll.create_index(list(keys), **kwargs)
    cache.add(guild_key)


def _coerce_guild_id(raw_value, fallback: int) -> int:
    try:
        if raw_value is None:
            raise TypeError
        return int(raw_value)
    except (TypeError, ValueError):
        return int(fallback)


def users_collection(db_client, guild_id: int):
    """Return the per-guild users collection using a synchronous client.

    This is a thin adapter for code paths that already have a sync client
    (e.g., the bot flush loop) and want to avoid duplicating DB name logic.
    """
    db = db_client.get_database(str(guild_id))
    coll = db["users"]
    _ensure_indexes(_USER_INDEX_CACHE, coll, str(guild_id), _USER_INDEXES)
    return coll


def upsert_user_sync(db_client, guild_id: int, user: User) -> None:
    coll = users_collection(db_client, guild_id)
    doc = to_bson(user)
    doc["guild_id"] = _coerce_guild_id(doc.get("guild_id"), guild_id)
    coll.update_one(
        {"guild_id": doc["guild_id"], "user_id.number": user.user_id.number},
        {"$set": doc},
        upsert=True,
    )


def quests_collection(db_client, guild_id: int):
    db = db_client.get_database(str(guild_id))
    coll = db["quests"]
    _ensure_indexes(_QUEST_INDEX_CACHE, coll, str(guild_id), _QUEST_INDEXES)
    return coll


def characters_collection(db_client, guild_id: int):
    db = db_client.get_database(str(guild_id))
    coll = db["characters"]
    _ensure_indexes(_CHAR_INDEX_CACHE, coll, str(guild_id), _CHAR_INDEXES)
    return coll


def _quest_to_doc(quest: Quest) -> dict:
    doc = asdict(quest)
    doc["guild_id"] = _coerce_guild_id(doc.get("guild_id"), quest.guild_id)
    # Normalize enums and timedeltas
    if isinstance(quest.status, QuestStatus):
        doc["status"] = quest.status.value
    if isinstance(quest.duration, timedelta):
        doc["duration"] = quest.duration.total_seconds()
    # Ensure ID dict shapes
    if isinstance(doc.get("quest_id"), dict):
        pass
    else:
        doc["quest_id"] = {
            "prefix": quest.quest_id.prefix,
            "number": quest.quest_id.number,
        }
    if isinstance(doc.get("referee_id"), dict):
        pass
    else:
        doc["referee_id"] = {"prefix": "USER", "number": quest.referee_id.number}
    return doc


def upsert_quest_sync(db_client, guild_id: int, quest: Quest) -> None:
    coll = quests_collection(db_client, guild_id)
    doc = _quest_to_doc(quest)
    doc["guild_id"] = _coerce_guild_id(doc.get("guild_id"), guild_id)
    coll.update_one(
        {"guild_id": doc["guild_id"], "quest_id.number": quest.quest_id.number},
        {"$set": doc},
        upsert=True,
    )


def upsert_character_sync(db_client, guild_id: int, character: Character) -> None:
    coll = characters_collection(db_client, guild_id)
    doc = asdict(character)
    doc["guild_id"] = _coerce_guild_id(doc.get("guild_id"), guild_id)
    # Ensure character_id stored as dict with prefix/number
    try:
        cid = CharacterID.parse(character.character_id)
        doc["character_id"] = {"prefix": cid.prefix, "number": cid.number}
        filt = {"guild_id": doc["guild_id"], "character_id.number": cid.number}
    except Exception:
        # Fallback to string key
        filt = {"guild_id": doc["guild_id"], "character_id": character.character_id}
    coll.update_one(filt, {"$set": doc}, upsert=True)
