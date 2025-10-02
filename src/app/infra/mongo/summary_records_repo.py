from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, cast

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.bot.ingestion.links import DiscordMessageKey
from app.bot.ingestion.summaries_pipeline import (
    AdventureSummaryRecord,
    document_to_record,
    record_to_document,
)

Document = dict[str, Any]
MongoCollection = AsyncIOMotorCollection[Any]
MongoDatabase = AsyncIOMotorDatabase[Any]


class SummaryRecordsRepository:
    def __init__(self, db: MongoDatabase) -> None:
        self._collection: MongoCollection = db["adventure_summaries"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            "summary_id", unique=True, name="uq_summary_id"
        )
        await self._collection.create_index(
            [
                ("discord_channel_id", ASCENDING),
                ("discord_message_id", ASCENDING),
            ],
            unique=True,
            name="uq_summary_message",
        )
        await self._collection.create_index("quest_id", name="ix_summary_quest_id")

    async def upsert(self, record: AdventureSummaryRecord) -> AdventureSummaryRecord:
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
        refreshed = await self._collection.find_one({"summary_id": doc["summary_id"]})
        assert refreshed is not None
        return document_to_record(cast(Mapping[str, Any], refreshed))

    async def get_by_discord_message(
        self, key: DiscordMessageKey
    ) -> AdventureSummaryRecord | None:
        doc = await self._collection.find_one(key.as_filter())
        if not doc:
            return None
        return document_to_record(cast(Mapping[str, Any], doc))

    async def get_by_summary_id(self, summary_id: str) -> AdventureSummaryRecord | None:
        doc = await self._collection.find_one({"summary_id": summary_id})
        if not doc:
            return None
        return document_to_record(cast(Mapping[str, Any], doc))

    async def mark_cancelled(self, key: DiscordMessageKey) -> bool:
        now = datetime.now(timezone.utc)
        result = await self._collection.update_one(
            key.as_filter(),
            {
                "$set": {
                    "status": "CANCELLED",
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0
