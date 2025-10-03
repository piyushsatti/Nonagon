from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator, cast

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.bot.ingestion import (
    DiscordMessageKey,
    QuestRecord,
    document_to_record,
    record_to_document,
)

Document = dict[str, Any]
MongoCollection = AsyncIOMotorCollection
MongoDatabase = AsyncIOMotorDatabase


class QuestRecordsRepository:
    def __init__(self, db: MongoDatabase) -> None:
        self._collection: Any = db["quests"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("quest_id", unique=True, name="uq_quest_id")
        await self._collection.create_index(
            [("discord_channel_id", ASCENDING), ("discord_message_id", ASCENDING)],
            unique=True,
            name="uq_discord_message",
        )
        await self._collection.create_index("starts_at_utc", name="ix_starts_at_utc")

    async def upsert(self, record: QuestRecord) -> QuestRecord:
        doc = record_to_document(record)
        created_at = doc.pop("created_at", datetime.now(timezone.utc))
        filter_doc = {
            "discord_channel_id": doc["discord_channel_id"],
            "discord_message_id": doc["discord_message_id"],
        }
        update_doc = {
            "$set": doc,
            "$setOnInsert": {"created_at": created_at},
        }
        await self._collection.update_one(filter_doc, update_doc, upsert=True)
        refreshed = await self._collection.find_one({"quest_id": doc["quest_id"]})
        assert refreshed is not None
        return document_to_record(cast(Document, refreshed))

    async def get_by_discord_message(
        self, key: DiscordMessageKey
    ) -> QuestRecord | None:
        doc = await self._collection.find_one(key.as_filter())
        if not doc:
            return None
        return document_to_record(cast(Document, doc))

    async def mark_cancelled(self, key: DiscordMessageKey) -> bool:
        now = datetime.now(timezone.utc)
        result = await self._collection.update_one(
            key.as_filter(),
            {"$set": {"status": "CANCELLED", "updated_at": now}},
        )
        return result.modified_count > 0

    async def get_by_discord_key(self, key: DiscordMessageKey) -> QuestRecord | None:
        return await self.get_by_discord_message(key)

    async def get_by_quest_id(self, quest_id: str) -> QuestRecord | None:
        doc = await self._collection.find_one({"quest_id": quest_id})
        if not doc:
            return None
        return document_to_record(cast(Document, doc))

    async def iter_unresolved_links(self) -> AsyncIterator[QuestRecord]:
        cursor = self._collection.find({"linked_quests.quest_id": None})
        async for doc in cursor:
            yield document_to_record(cast(Document, doc))

    async def update_linked_quest_id(
        self,
        subject_quest_id: str,
        link_index: int,
        linked_quest_id: str,
    ) -> None:
        await self._collection.update_one(
            {"quest_id": subject_quest_id},
            {
                "$set": {
                    f"linked_quests.{link_index}.quest_id": linked_quest_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
