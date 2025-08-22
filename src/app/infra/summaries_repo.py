# src/app/infra/summaries_repo.py
from __future__ import annotations
from typing import Any, Dict
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.usecases.ports import SummariesRepo, NotFoundError
from app.domain.models.SummaryModel import QuestSummary, SummaryKind

def _to_bson(s: QuestSummary) -> Dict[str, Any]:
    d = s.__dict__.copy()
    d["kind"] = s.kind.value
    d["_id"] = s.summary_id
    return d

def _from_bson(d: Dict[str, Any]) -> QuestSummary:
    d = dict(d)
    d["kind"] = SummaryKind(d["kind"])
    return QuestSummary(**{k: v for k, v in d.items() if k != "_id"})

class MongoSummariesRepo(SummariesRepo):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["summaries"]

    async def get(self, summary_id: str) -> QuestSummary:
        doc = await self.col.find_one({"summary_id": summary_id})
        if not doc:
            raise NotFoundError(f"summary {summary_id} not found")
        return _from_bson(doc)

    async def upsert(self, summary: QuestSummary) -> None:
        await self.col.update_one(
            {"summary_id": summary.summary_id},
            {"$set": _to_bson(summary)},
            upsert=True,
        )

    async def next_id(self) -> str:
        return uuid4().hex
