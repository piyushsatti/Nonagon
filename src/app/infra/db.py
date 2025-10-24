# app/infra/db.py
from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.infra.settings import DB_NAME, MONGODB_URI

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
	"""Return a cached AsyncIOMotorClient (lazy init)."""
	global _client
	if _client is None:
		_client = AsyncIOMotorClient(
			MONGODB_URI,
			appname="nonagon",
			serverSelectionTimeoutMS=5000,
			socketTimeoutMS=5000,
			connectTimeoutMS=5000,
			uuidRepresentation="standard",
		)
	return _client


def get_db() -> AsyncIOMotorDatabase:
	return get_client()[DB_NAME]


def get_guild_db(guild_id: int | str) -> AsyncIOMotorDatabase:
	"""Return the per-guild database named by the Discord guild id."""
	return get_client()[str(guild_id)]


async def ping() -> bool:
	try:
		# admin DB per official examples
		await get_client().admin.command("ping")
		return True
	except Exception as e:
		print(f"[Mongo Ping Failed] {e}")
		return False


async def close_client() -> None:
	"""Close the cached client (useful for app shutdown / tests)."""
	global _client
	if _client is not None:
		_client.close()
		_client = None
