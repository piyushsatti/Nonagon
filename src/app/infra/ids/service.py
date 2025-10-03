from __future__ import annotations

from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

MongoDocument = dict[str, object]
MongoCollection = AsyncIOMotorCollection[MongoDocument]
MongoDatabase = AsyncIOMotorDatabase[MongoDocument]


class IdService(Protocol):
    async def next_quest_id(self) -> str: ...

    async def ensure_user_id(self, discord_id: str) -> str: ...
    async def next_summary_id(self) -> str: ...


class MongoIdService:
    def __init__(self, db: MongoDatabase) -> None:
        self._counters: MongoCollection = db["counters"]
        self._user_ids: MongoCollection = db["user_ids"]

    async def next_quest_id(self) -> str:
        seq = await self._next_sequence("QUEST")
        return f"QUES{seq:04d}"

    async def next_summary_id(self) -> str:
        seq = await self._next_sequence("SUMM")
        return f"SUMM{seq:04d}"

    async def ensure_user_id(self, discord_id: str) -> str:
        existing = await self._user_ids.find_one({"discord_id": discord_id})
        if existing and "user_id" in existing:
            return str(existing["user_id"])

        user_id = f"USER{await self._next_sequence('USER'):04d}"
        try:
            await self._user_ids.insert_one(
                {"discord_id": discord_id, "user_id": user_id}
            )
        except DuplicateKeyError:
            doc = await self._user_ids.find_one({"discord_id": discord_id})
            if doc and "user_id" in doc:
                return str(doc["user_id"])
            raise
        return user_id

    async def ensure_indexes(self) -> None:
        await self._user_ids.create_index(
            "discord_id", unique=True, name="uq_user_ids_discord"
        )

    async def _next_sequence(self, prefix: str) -> int:
        doc = await self._counters.find_one_and_update(
            {"_id": prefix},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        assert doc is not None
        seq_value = doc.get("seq", 0)
        if not isinstance(seq_value, int):
            raise TypeError(
                f"Counter for {prefix} returned non-int value: {seq_value!r}"
            )
        return seq_value
