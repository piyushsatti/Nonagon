# app/infra/mongo/characters_repo.py
from __future__ import annotations

from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.domain.models.character.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID
from app.domain.usecase.ports import CharactersRepo
from app.infra.db import next_id
from app.infra.serialization import from_bson, to_bson


class CharactersRepoMongo(CharactersRepo):
    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self._collection: AsyncIOMotorCollection[Any] = db["characters"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [("owner_id.number", ASCENDING)],
            name="ix_characters_owner_id",
        )

    async def get(self, character_id: str) -> Optional[Character]:
        doc = await self._collection.find_one({"_id": character_id})
        return from_bson(Character, doc) if doc else None

    async def upsert(self, character: Character) -> bool:
        doc = to_bson(character)
        doc["_id"] = doc.get("character_id")
        await self._collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return True

    async def delete(self, character_id: str) -> bool:
        res = await self._collection.delete_one({"_id": character_id})
        return res.deleted_count == 1

    async def next_id(self) -> str:
        return str(await next_id(CharacterID))

    async def exists(self, character_id: str) -> bool:
        return (
            await self._collection.count_documents({"_id": character_id}, limit=1) > 0
        )
