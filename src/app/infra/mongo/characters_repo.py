# app/infra/mongo/characters_repo.py
from __future__ import annotations

from typing import Optional

from app.domain.models.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID
from app.domain.usecase.ports import CharactersRepo
from app.infra.db import get_db, next_id
from app.infra.mongo.mappers import dataclass_to_mongo, mongo_to_dataclass

COLL = lambda: get_db()["characters"]


class CharactersRepoMongo(CharactersRepo):
    async def get(self, character_id: str) -> Optional[Character]:
        doc = await COLL().find_one({"_id": character_id})
        return mongo_to_dataclass(Character, doc) if doc else None

    async def upsert(self, character: Character) -> bool:
        doc = dataclass_to_mongo(character)
        await COLL().replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return True

    async def delete(self, character_id: str) -> bool:
        res = await COLL().delete_one({"_id": character_id})
        return res.deleted_count == 1

    async def next_id(self) -> str:
        return str(await next_id(CharacterID))

    async def exists(self, character_id: str) -> bool:
        return await COLL().count_documents({"_id": character_id}, limit=1) > 0
