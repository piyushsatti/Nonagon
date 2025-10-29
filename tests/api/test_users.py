from __future__ import annotations

from typing import Dict, Tuple

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers import users as users_router
from app.domain.models.UserModel import User


class _FakeUsersRepo:
    def __init__(self) -> None:
        self._store: Dict[Tuple[int, str], User] = {}
        self._counter = 1

    async def next_id(self, guild_id: int) -> str:
        value = f"USER{self._counter:04d}"
        self._counter += 1
        return value

    async def upsert(self, guild_id: int, user: User) -> bool:
        key = (guild_id, str(user.user_id))
        self._store[key] = user
        return True

    async def get(self, guild_id: int, user_id: str) -> User | None:
        return self._store.get((guild_id, user_id))

    async def get_by_discord_id(self, guild_id: int, discord_id: str) -> User | None:
        for (gid, _), user in self._store.items():
            if gid == guild_id and user.discord_id == discord_id:
                return user
        return None

    async def delete(self, guild_id: int, user_id: str) -> bool:
        key = (guild_id, user_id)
        if key in self._store:
            del self._store[key]
            return True
        return False


def test_users_crud_scoped_by_guild(monkeypatch) -> None:
    fake_repo = _FakeUsersRepo()
    monkeypatch.setattr(users_router, "users_repo", fake_repo)

    client = TestClient(app)

    create = client.post(
        "/v1/guilds/123/users",
        json={"discord_id": "alpha", "roles": ["MEMBER"]},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["guild_id"] == 123
    user_id = body["user_id"]

    read = client.get(f"/v1/guilds/123/users/{user_id}")
    assert read.status_code == 200
    assert read.json()["discord_id"] == "alpha"

    # Cross-guild lookup should 404
    miss = client.get(f"/v1/guilds/456/users/{user_id}")
    assert miss.status_code == 404

    # Same discord id in another guild is a separate record
    create_other = client.post(
        "/v1/guilds/456/users",
        json={"discord_id": "alpha", "roles": ["MEMBER"]},
    )
    assert create_other.status_code == 201
    assert create_other.json()["guild_id"] == 456

    delete = client.delete(f"/v1/guilds/123/users/{user_id}")
    assert delete.status_code == 204
    missing_after_delete = client.get(f"/v1/guilds/123/users/{user_id}")
    assert missing_after_delete.status_code == 404
