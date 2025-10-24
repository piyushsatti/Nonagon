# app/infra/mongo/characters_repo.py
from __future__ import annotations

from typing import Optional

from app.domain.models.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID
from app.domain.usecase.ports import CharactersRepo
from app.infra.db import get_guild_db
from app.infra.mongo.mappers import dataclass_to_mongo, mongo_to_dataclass

def COLL(guild_id: int | str):
	return get_guild_db(guild_id)["characters"]


class CharactersRepoMongo(CharactersRepo):
	async def get(self, guild_id: int, character_id: str) -> Optional[Character]:
		doc = await COLL(guild_id).find_one(
			{"guild_id": int(guild_id), "_id": character_id}
		)
		return mongo_to_dataclass(Character, doc) if doc else None

	async def upsert(self, guild_id: int, character: Character) -> bool:
		doc = dataclass_to_mongo(character)
		doc["_id"] = doc.get("_id") or doc.get("character_id")
		doc["guild_id"] = doc.get("guild_id") or int(guild_id)
		if doc["_id"] is None:
			raise ValueError("character_id must be set before persisting")
		await COLL(guild_id).replace_one(
			{"guild_id": doc["guild_id"], "_id": doc["_id"]}, doc, upsert=True
		)
		return True

	async def delete(self, guild_id: int, character_id: str) -> bool:
		res = await COLL(guild_id).delete_one(
			{"guild_id": int(guild_id), "_id": character_id}
		)
		return res.deleted_count == 1

	async def next_id(self, guild_id: int) -> str:
		while True:
			candidate = CharacterID.generate()
			exists = await COLL(guild_id).count_documents(
				{"guild_id": int(guild_id), "_id": str(candidate)}, limit=1
			)
			if not exists:
				return str(candidate)

	async def exists(self, guild_id: int, character_id: str) -> bool:
		return (
			await COLL(guild_id).count_documents(
				{"guild_id": int(guild_id), "_id": character_id}, limit=1
			)
			> 0
		)
