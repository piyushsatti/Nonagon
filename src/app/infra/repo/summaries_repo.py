from __future__ import annotations
from typing import Any, Dict
from dataclasses import asdict

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.domain.usecases.ports import SummariesRepo, NotFoundError
from app.domain.models.quest.SummaryModel import QuestSummary, SummaryKind

def _dehydrate(s: QuestSummary) -> Dict[str, Any]:
  d = asdict(s)
  d["kind"] = s.kind.value
  d["_id"] = s.summary_id
  return d

def _hydrate(d: Dict[str, Any]) -> QuestSummary:
  data = dict(d)
  data.pop("_id", None)
  data["kind"] = SummaryKind(data["kind"])
  return QuestSummary(**data)

class MongoSummariesRepo(SummariesRepo):
  def __init__(self, db: AsyncIOMotorDatabase):
    self.col: AsyncIOMotorCollection = db["summaries"]

  @classmethod
  async def create(cls, db: AsyncIOMotorDatabase) -> MongoSummariesRepo:
    self = cls(db)
    await self.col.create_index("summary_id", unique=True)
    return self

  async def get(self, summary_id: str) -> QuestSummary:
    doc = await self.col.find_one({"summary_id": summary_id})
    if not doc:
      raise NotFoundError(f"summary {summary_id} not found")
    return _hydrate(doc)

  async def upsert(self, summary: QuestSummary) -> None:
    payload = _dehydrate(summary)
    await self.col.update_one(
      {"summary_id": summary.summary_id},
      {"$set": payload},
      upsert=True,
    )