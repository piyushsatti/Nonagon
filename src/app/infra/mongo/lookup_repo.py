from __future__ import annotations

from typing import Iterable, List, Optional

from pymongo import ReturnDocument

from app.domain.models.LookupModel import LookupEntry
from app.infra.db import get_guild_db
from app.infra.serialization import from_bson, to_bson


def COLL(guild_id: int | str):
    return get_guild_db(guild_id)["lookups"]


class LookupRepoMongo:
    async def upsert(self, entry: LookupEntry) -> LookupEntry:
        entry.validate_entry()
        doc = to_bson(entry)
        doc["guild_id"] = int(entry.guild_id)
        doc["name_normalized"] = LookupEntry.normalize_name(entry.name)
        result = await COLL(entry.guild_id).find_one_and_update(
            {"guild_id": doc["guild_id"], "name_normalized": doc["name_normalized"]},
            {"$set": doc},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return from_bson(LookupEntry, result)

    async def get_by_name(self, guild_id: int, name: str) -> Optional[LookupEntry]:
        doc = await COLL(guild_id).find_one(
            {
                "guild_id": int(guild_id),
                "name_normalized": LookupEntry.normalize_name(name),
            }
        )
        return from_bson(LookupEntry, doc) if doc else None

    async def list_all(self, guild_id: int) -> List[LookupEntry]:
        cursor = COLL(guild_id).find({"guild_id": int(guild_id)}, {"_id": 0})
        cursor = cursor.sort("name_normalized", 1)
        docs = await cursor.to_list(length=500)
        return [from_bson(LookupEntry, doc) for doc in docs]

    async def delete(self, guild_id: int, name: str) -> bool:
        res = await COLL(guild_id).delete_one(
            {
                "guild_id": int(guild_id),
                "name_normalized": LookupEntry.normalize_name(name),
            }
        )
        return res.deleted_count == 1

    async def find_best_match(self, guild_id: int, query: str) -> Optional[LookupEntry]:
        entries = await self.list_all(guild_id)
        return self._select_best(entries, query)

    @staticmethod
    def _select_best(entries: Iterable[LookupEntry], query: str) -> Optional[LookupEntry]:
        normalized = LookupEntry.normalize_name(query)
        best_score = -1
        best_entry: Optional[LookupEntry] = None
        for entry in entries:
            entry_name = LookupEntry.normalize_name(entry.name)
            score = _score_entry(entry_name, normalized)
            if score < 0:
                continue
            if score > best_score:
                best_score = score
                best_entry = entry
            elif score == best_score and best_entry is not None:
                if entry_name < LookupEntry.normalize_name(best_entry.name):
                    best_entry = entry
        return best_entry


def _score_entry(entry_name: str, query: str) -> int:
    if not query:
        return -1
    if entry_name == query:
        return 3
    if entry_name.startswith(query):
        return 2
    if query in entry_name:
        return 1
    return -1
