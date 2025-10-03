from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.bot.ingestion.failures import IngestFailureRecord

MongoCollection = AsyncIOMotorCollection[Any]
MongoDatabase = AsyncIOMotorDatabase[Any]


class IngestFailureRepository:
    """Persists failed ingestion attempts while retaining raw Discord input."""

    def __init__(self, db: MongoDatabase) -> None:
        self._collection: MongoCollection = db["ingest_failures"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [
                ("kind", 1),
                ("channel_id", 1),
                ("message_id", 1),
            ],
            name="ix_kind_message",
        )

    async def record_failure(self, record: IngestFailureRecord) -> None:
        doc = record.to_document()
        filter_doc = {
            "kind": doc["kind"],
            "channel_id": doc["channel_id"],
            "message_id": doc["message_id"],
        }
        update_doc = {
            "$set": doc,
        }
        await self._collection.update_one(filter_doc, update_doc, upsert=True)
