from __future__ import annotations

from typing import Any, Optional

from app.domain.models.EntityIDModel import CharacterID, SummaryID, UserID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase.ports import SummariesRepo
from app.infra.db import get_db, next_id
from app.infra.serialization import from_bson, to_bson


def _coll():
    return get_db()["summaries"]


class SummariesRepoMongo(SummariesRepo):
    async def get(self, summary_id: str) -> Optional[QuestSummary]:
        sid = SummaryID.parse(summary_id)
        doc = await _coll().find_one({"summary_id.number": sid.number})
        return from_bson(QuestSummary, doc) if doc else None

    async def upsert(self, summary: QuestSummary) -> bool:
        doc = to_bson(summary)
        filt = {"summary_id.number": doc["summary_id"]["number"]}
        await _coll().replace_one(filt, doc, upsert=True)
        return True

    async def delete(self, summary_id: str) -> bool:
        sid = SummaryID.parse(summary_id)
        res = await _coll().delete_one({"summary_id.number": sid.number})
        return res.deleted_count == 1

    async def next_id(self) -> str:
        return str(await next_id(SummaryID))

    async def exists(self, summary_id: str) -> bool:
        sid = SummaryID.parse(summary_id)
        count = await _coll().count_documents(
            {"summary_id.number": sid.number}, limit=1
        )
        return count > 0

    async def list(self, *, limit: int, offset: int) -> list[QuestSummary]:
        return await self._fetch_many({}, limit=limit, offset=offset)

    async def list_by_author(
        self, author_id: str, *, limit: int, offset: int
    ) -> list[QuestSummary]:
        aid = UserID.parse(author_id)
        query = {"author_id.number": aid.number}
        return await self._fetch_many(query, limit=limit, offset=offset)

    async def list_by_character(
        self, character_id: str, *, limit: int, offset: int
    ) -> list[QuestSummary]:
        cid = CharacterID.parse(character_id)
        query = {"characters.number": cid.number}
        return await self._fetch_many(query, limit=limit, offset=offset)

    async def list_by_player(
        self, player_id: str, *, limit: int, offset: int
    ) -> list[QuestSummary]:
        pid = UserID.parse(player_id)
        query = {"players.number": pid.number}
        return await self._fetch_many(query, limit=limit, offset=offset)

    async def _fetch_many(
        self, query: dict[str, Any], *, limit: int, offset: int
    ) -> list[QuestSummary]:
        if limit <= 0:
            return []
        cursor = _coll().find(query).sort("created_on", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [from_bson(QuestSummary, doc) for doc in docs]
