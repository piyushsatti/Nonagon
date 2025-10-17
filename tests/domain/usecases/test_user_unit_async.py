from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.domain.models.EntityIDModel import UserID
from app.domain.models.UserModel import User
from app.domain.usecase.unit.user_unit import update_user_last_active_async


class _FakeAsyncUsersRepo:
    def __init__(self, user: User | None):
        self._user = user
        self._saved = None
    async def exists(self, guild_id, user_id):
        return self._user is not None
    async def get(self, guild_id, user_id):
        return self._user
    async def upsert(self, guild_id, user: User):
        self._saved = user


@pytest.mark.asyncio
async def test_update_last_active_async_updates_timestamp():
    uid = UserID(1)
    u = User(user_id=uid, guild_id=777)
    repo = _FakeAsyncUsersRepo(u)
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    out = await update_user_last_active_async(repo, 777, uid, now)
    assert out.last_active_at == now
    assert repo._saved.last_active_at == now
