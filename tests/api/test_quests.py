from __future__ import annotations

import os
from typing import Dict, Tuple

from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost/test")

from app.api.main import app
from app.api.routers import quests as quests_router
from app.domain.models.EntityIDModel import QuestID, UserID
from app.domain.models.QuestModel import Quest
from app.domain.models.UserModel import User


class _FakeQuestsRepo:
    def __init__(self) -> None:
        self._store: Dict[Tuple[int, str], Quest] = {}
        self._counter = 1

    async def next_id(self, guild_id: int) -> str:
        value = f"QUES{self._counter:04d}"
        self._counter += 1
        return value

    async def upsert(self, guild_id: int, quest: Quest) -> bool:
        key = (guild_id, str(quest.quest_id))
        quest.guild_id = guild_id
        self._store[key] = quest
        return True

    async def get(self, guild_id: int, quest_id: str) -> Quest | None:
        return self._store.get((guild_id, quest_id))

    async def delete(self, guild_id: int, quest_id: str) -> bool:
        key = (guild_id, quest_id)
        if key in self._store:
            del self._store[key]
            return True
        return False


class _FakeUsersRepo:
    def __init__(self) -> None:
        self._store: Dict[Tuple[int, str], User] = {}

    async def get(self, guild_id: int, user_id: str) -> User | None:
        return self._store.get((guild_id, user_id))

    async def upsert(self, guild_id: int, user: User) -> bool:
        self._store[(guild_id, str(user.user_id))] = user
        return True


class _FakeCharactersRepo:
    async def get(self, guild_id: int, character_id: str):  # pragma: no cover - unused
        return None


def test_create_quest_uses_existing_id_and_persists(monkeypatch) -> None:
    fake_quests = _FakeQuestsRepo()
    fake_users = _FakeUsersRepo()
    fake_characters = _FakeCharactersRepo()

    monkeypatch.setattr(quests_router, "quests_repo", fake_quests)
    monkeypatch.setattr(quests_router, "users_repo", fake_users)
    monkeypatch.setattr(quests_router, "characters_repo", fake_characters)

    referee = User(user_id=UserID(1), guild_id=123)
    referee.enable_referee()
    fake_users._store[(123, str(referee.user_id))] = referee

    client = TestClient(app)

    response = client.post(
        "/v1/guilds/123/quests",
        params={"channel_id": "789", "message_id": "456"},
        json={
            "quest_id": "QUES0042",
            "referee_id": str(referee.user_id),
            "raw": "Quest draft",
            "title": "Epic Trial",
            "duration_hours": 2,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quest_id"] == "QUES0042"
    assert body["channel_id"] == "789"
    assert body["message_id"] == "456"
    stored = fake_quests._store[(123, "QUES0042")]
    assert stored.title == "Epic Trial"
    assert stored.duration.total_seconds() == 2 * 3600


def test_create_quest_requires_channel_and_raw(monkeypatch) -> None:
    fake_quests = _FakeQuestsRepo()
    fake_users = _FakeUsersRepo()
    fake_characters = _FakeCharactersRepo()

    monkeypatch.setattr(quests_router, "quests_repo", fake_quests)
    monkeypatch.setattr(quests_router, "users_repo", fake_users)
    monkeypatch.setattr(quests_router, "characters_repo", fake_characters)

    referee = User(user_id=UserID(1), guild_id=123)
    referee.enable_referee()
    fake_users._store[(123, str(referee.user_id))] = referee

    client = TestClient(app)

    response = client.post(
        "/v1/guilds/123/quests",
        params={"channel_id": "789"},
        json={
            "referee_id": str(referee.user_id),
            "title": "Epic Trial",
            "duration_hours": 2,
        },
    )

    assert response.status_code == 400
    assert "channel_id" in response.json()["detail"]
