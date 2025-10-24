from __future__ import annotations

import types

import pytest

from app.domain.models.EntityIDModel import UserID
from app.domain.models.UserModel import User
from app.infra.mongo import users_repo


class _FakeCollection:
	def __init__(self):
		self.last_replace_one = None
		self.last_find_one = None

	async def replace_one(self, filt, doc, upsert=False):
		self.last_replace_one = (filt, doc, upsert)
		return types.SimpleNamespace()

	async def find_one(self, filt):
		self.last_find_one = filt
		# Return a minimal BSON-like document when requested
		return {
			"guild_id": filt.get("guild_id"),
			"user_id": {"prefix": "USER", "value": "USER1"},
			"discord_id": filt.get("discord_id"),
			"roles": [],
			"dm_opt_in": True,
		}


@pytest.mark.asyncio
async def test_users_repo_upsert_scopes_by_guild(monkeypatch):
	repo = users_repo.UsersRepoMongo()
	fake = _FakeCollection()
	monkeypatch.setattr(users_repo, "COLL", lambda guild_id: fake)

	user = User(user_id=UserID(1), guild_id=123)
	await repo.upsert(123, user)

	filt, doc, upsert = fake.last_replace_one
	assert filt == {"guild_id": 123, "user_id.value": str(user.user_id)}
	assert doc["guild_id"] == 123
	assert upsert is True


@pytest.mark.asyncio
async def test_users_repo_get_by_discord_id_filters_guild(monkeypatch):
	repo = users_repo.UsersRepoMongo()
	fake = _FakeCollection()
	monkeypatch.setattr(users_repo, "COLL", lambda guild_id: fake)

	user = await repo.get_by_discord_id(456, "999")

	assert fake.last_find_one == {"guild_id": 456, "discord_id": "999"}
	assert isinstance(user, User)
	assert user.guild_id == 456
