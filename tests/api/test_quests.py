from __future__ import annotations

import os
from typing import Dict, Tuple

from fastapi.testclient import TestClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost/test")

from app.api.main import app
from app.api.routers import quests as quests_router
from app.domain.models.EntityIDModel import CharacterID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, Quest
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
    def __init__(self) -> None:
        self._store: Dict[Tuple[int, str], object] = {}

    async def get(self, guild_id: int, character_id: str):
        return self._store.get((guild_id, character_id))


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


def _setup_signup_env(monkeypatch):
    fake_quests = _FakeQuestsRepo()
    fake_users = _FakeUsersRepo()
    fake_characters = _FakeCharactersRepo()

    monkeypatch.setattr(quests_router, "quests_repo", fake_quests)
    monkeypatch.setattr(quests_router, "users_repo", fake_users)
    monkeypatch.setattr(quests_router, "characters_repo", fake_characters)

    quest = Quest(
        quest_id=QuestID.parse("QUES0001"),
        guild_id=123,
        referee_id=UserID(99),
        channel_id="chan",
        message_id="msg",
        raw="Quest body",
        title="Quest Title",
        description=None,
    )
    fake_quests._store[(123, str(quest.quest_id))] = quest

    player = User(user_id=UserID(42), guild_id=123)
    player.enable_player()
    character_id = CharacterID.parse("CHAR0007")
    player.player.add_character(character_id)
    fake_users._store[(123, str(player.user_id))] = player
    fake_characters._store[(123, str(character_id))] = {"_id": "CHAR7"}

    return fake_quests, fake_users, fake_characters, quest, player, character_id


def test_add_signup_persists_request(monkeypatch) -> None:
    fake_quests, _, _, quest, player, character_id = _setup_signup_env(monkeypatch)
    client = TestClient(app)

    response = client.post(
        f"/v1/guilds/{quest.guild_id}/quests/{quest.quest_id}/signups",
        json={
            "user_id": str(player.user_id),
            "character_id": str(character_id),
        },
    )

    assert response.status_code == 200
    stored = fake_quests._store[(quest.guild_id, str(quest.quest_id))]
    assert len(stored.signups) == 1
    signup = stored.signups[0]
    assert signup.user_id == player.user_id
    assert signup.character_id == character_id


def test_add_signup_duplicate_returns_friendly_message(monkeypatch) -> None:
    fake_quests, _, _, quest, player, character_id = _setup_signup_env(monkeypatch)
    quest.signups.append(
        PlayerSignUp(user_id=player.user_id, character_id=character_id)
    )

    client = TestClient(app)

    response = client.post(
        f"/v1/guilds/{quest.guild_id}/quests/{quest.quest_id}/signups",
        json={
            "user_id": str(player.user_id),
            "character_id": str(character_id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You already requested to join this quest."


def test_nudge_updates_timestamp_and_enforces_cooldown(monkeypatch) -> None:
    fake_quests, fake_users, _, quest, _, _ = _setup_signup_env(monkeypatch)
    referee = User(user_id=quest.referee_id, guild_id=quest.guild_id)
    referee.enable_referee()
    fake_users._store[(quest.guild_id, str(referee.user_id))] = referee

    client = TestClient(app)

    response = client.post(
        f"/v1/guilds/{quest.guild_id}/quests/{quest.quest_id}:nudge",
        json={"referee_id": str(referee.user_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["last_nudged_at"] is not None

    stored = fake_quests._store[(quest.guild_id, str(quest.quest_id))]
    assert stored.last_nudged_at is not None

    repeat = client.post(
        f"/v1/guilds/{quest.guild_id}/quests/{quest.quest_id}:nudge",
        json={"referee_id": str(referee.user_id)},
    )

    assert repeat.status_code == 400
    assert "Nudge on cooldown" in repeat.json()["detail"]
