from __future__ import annotations

from app.domain.models.EntityIDModel import UserID
from app.domain.models.UserModel import User
from app.infra.db import get_guild_db
from app.infra.serialization import from_bson, to_bson


def COLL(guild_id: int | str):
	return get_guild_db(guild_id)["users"]


class UsersRepoMongo:
	async def upsert(self, guild_id: int, user: User) -> bool:
		doc = to_bson(user)
		doc["guild_id"] = doc.get("guild_id") or int(guild_id)
		filt = {
			"guild_id": doc["guild_id"],
			"user_id.value": doc["user_id"]["value"],
		}
		await COLL(guild_id).replace_one(filt, doc, upsert=True)
		return True

	async def get(self, guild_id: int, user_id: str) -> User | None:
		uid = UserID.parse(user_id)
		doc = await COLL(guild_id).find_one(
			{"guild_id": int(guild_id), "user_id.value": uid.value}
		)
		return from_bson(User, doc) if doc else None

	async def delete(self, guild_id: int, user_id: str) -> bool:
		uid = UserID.parse(user_id)
		res = await COLL(guild_id).delete_one(
			{"guild_id": int(guild_id), "user_id.value": uid.value}
		)
		return res.deleted_count == 1

	async def exists(self, guild_id: int, user_id: str) -> bool:
		uid = UserID.parse(user_id)
		count = await COLL(guild_id).count_documents(
			{"guild_id": int(guild_id), "user_id.value": uid.value}, limit=1
		)
		return count > 0

	async def next_id(self, guild_id: int) -> str:
		while True:
			candidate = UserID.generate()
			exists = await COLL(guild_id).count_documents(
				{"guild_id": int(guild_id), "user_id.value": candidate.value},
				limit=1,
			)
			if not exists:
				return str(candidate)

	async def get_by_discord_id(self, guild_id: int, discord_id: str) -> User | None:
		doc = await COLL(guild_id).find_one(
			{"guild_id": int(guild_id), "discord_id": discord_id}
		)
		return from_bson(User, doc) if doc else None
