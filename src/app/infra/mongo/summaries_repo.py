from __future__ import annotations

from typing import Optional

from app.domain.models.EntityIDModel import SummaryID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase.ports import SummariesRepo
from app.infra.db import get_db, next_id
from app.infra.mongo.mappers import dataclass_to_mongo, mongo_to_dataclass


def _coll():
    return get_db()["summaries"]


class SummariesRepoMongo(SummariesRepo):
    async def get(self, summary_id: str) -> Optional[QuestSummary]:
        doc = await _coll().find_one({"_id": summary_id})
        return mongo_to_dataclass(QuestSummary, doc) if doc else None

    async def upsert(self, summary: QuestSummary) -> bool:
        doc = dataclass_to_mongo(summary)
        await _coll().replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return True

    async def delete(self, summary_id: str) -> bool:
        res = await _coll().delete_one({"_id": summary_id})
        return res.deleted_count == 1

    async def next_id(self) -> str:
        return str(await next_id(SummaryID))

    async def exists(self, summary_id: str) -> bool:
        return await _coll().count_documents({"_id": summary_id}, limit=1) > 0
