from __future__ import annotations

from typing import Optional

from app.domain.models.EntityIDModel import SummaryID
from app.domain.models.SummaryModel import QuestSummary
from app.domain.usecase.ports import SummariesRepo
from app.infra.db import get_guild_db
from app.infra.mongo.mappers import dataclass_to_mongo, mongo_to_dataclass


def _coll(guild_id: int | str):
	return get_guild_db(guild_id)["summaries"]


class SummariesRepoMongo(SummariesRepo):
	async def get(self, guild_id: int, summary_id: str) -> Optional[QuestSummary]:
		doc = await _coll(guild_id).find_one(
			{"guild_id": int(guild_id), "_id": summary_id}
		)
		return mongo_to_dataclass(QuestSummary, doc) if doc else None

	async def upsert(self, guild_id: int, summary: QuestSummary) -> bool:
		doc = dataclass_to_mongo(summary)
		doc["_id"] = doc.get("_id") or doc.get("summary_id")
		doc["guild_id"] = doc.get("guild_id") or int(guild_id)
		if doc["_id"] is None:
			raise ValueError("summary_id must be set before persisting")
		await _coll(guild_id).replace_one(
			{"guild_id": doc["guild_id"], "_id": doc["_id"]}, doc, upsert=True
		)
		return True

	async def delete(self, guild_id: int, summary_id: str) -> bool:
		res = await _coll(guild_id).delete_one(
			{"guild_id": int(guild_id), "_id": summary_id}
		)
		return res.deleted_count == 1

	async def next_id(self, guild_id: int) -> str:
		while True:
			candidate = SummaryID.generate()
			exists = await _coll(guild_id).count_documents(
				{"guild_id": int(guild_id), "_id": str(candidate)}, limit=1
			)
			if not exists:
				return str(candidate)

	async def exists(self, guild_id: int, summary_id: str) -> bool:
		return (
			await _coll(guild_id).count_documents(
				{"guild_id": int(guild_id), "_id": summary_id}, limit=1
			)
			> 0
		)
