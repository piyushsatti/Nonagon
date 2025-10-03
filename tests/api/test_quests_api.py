from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict

import pytest

pytestmark = pytest.mark.asyncio


async def _create_user(
    api_client: Any, payload: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    response = await api_client.post("/v1/users", json=payload or {})
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _enable_referee(api_client: Any, user_id: str) -> Dict[str, Any]:
    response = await api_client.post(f"/v1/users/{user_id}:enableReferee")
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


async def _enable_player(api_client: Any, user_id: str) -> Dict[str, Any]:
    response = await api_client.post(f"/v1/users/{user_id}:enablePlayer")
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


async def _create_character(
    api_client: Any, owner_id: str, *, name: str = "Hero"
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "owner_id": owner_id,
        "name": name,
        "ddb_link": "https://ddb.example/hero",
        "character_thread_link": "https://discord.example/thread/hero",
        "token_link": "https://tokens.example/hero.png",
        "art_link": "https://art.example/hero.png",
    }
    response = await api_client.post("/v1/characters", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _create_quest(
    api_client: Any,
    referee_id: str,
    *,
    title: str = "Epic Quest",
) -> Dict[str, Any]:
    start = (datetime.now(timezone.utc) + timedelta(minutes=5)).replace(microsecond=0)
    payload: Dict[str, Any] = {
        "referee_id": referee_id,
        "channel_id": "12345",
        "message_id": "67890",
        "raw": "Quest details",
        "title": title,
        "description": "An unforgettable adventure",
        "starting_at": start.isoformat(),
        "duration_hours": 3,
        "image_url": "https://example.com/quest.png",
    }

    response = await api_client.post("/v1/quests", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def test_create_quest_requires_referee_role(api_client: Any) -> None:
    user = await _create_user(api_client)

    response = await api_client.post(
        "/v1/quests",
        json={
            "referee_id": user["user_id"],
            "channel_id": "chan",
            "message_id": "msg",
            "title": "Needs Referee",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
    assert "referee" in response.json().get("detail", "").lower()


async def test_quest_lifecycle_and_signups(api_client: Any) -> None:
    referee = await _create_user(api_client)
    referee = await _enable_referee(api_client, referee["user_id"])

    quest = await _create_quest(api_client, referee["user_id"], title="Season Opener")
    quest_id = quest["quest_id"]

    assert quest["status"] == "ANNOUNCED"
    assert quest["signups_open"] is True
    assert quest["signups"] == []

    player = await _create_user(api_client, {"discord_id": "player-1"})
    player = await _enable_player(api_client, player["user_id"])
    character = await _create_character(api_client, player["user_id"], name="Rogue")

    response = await api_client.post(
        f"/v1/quests/{quest_id}/signups",
        json={
            "user_id": player["user_id"],
            "character_id": character["character_id"],
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert len(quest["signups"]) == 1
    signup = quest["signups"][0]
    assert signup["user_id"] == player["user_id"]
    assert signup["character_id"] == character["character_id"]
    assert signup["selected"] is False

    response = await api_client.post(
        f"/v1/quests/{quest_id}/signups/{player['user_id']}:select"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert quest["signups"][0]["selected"] is True

    response = await api_client.post(f"/v1/quests/{quest_id}:closeSignups")
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert quest["signups_open"] is False

    response = await api_client.post(
        f"/v1/quests/{quest_id}/signups",
        json={
            "user_id": player["user_id"],
            "character_id": character["character_id"],
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
    assert "closed" in response.json().get("detail", "").lower()

    response = await api_client.delete(
        f"/v1/quests/{quest_id}/signups/{player['user_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert quest["signups"] == []

    response = await api_client.post(f"/v1/quests/{quest_id}:setCompleted")
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert quest["status"] == "COMPLETED"

    response = await api_client.post(f"/v1/quests/{quest_id}:setCancelled")
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert quest["status"] == "CANCELLED"

    response = await api_client.post(f"/v1/quests/{quest_id}:setAnnounced")
    assert response.status_code == HTTPStatus.OK, response.text
    quest = response.json()
    assert quest["status"] == "ANNOUNCED"

    response = await api_client.delete(f"/v1/quests/{quest_id}")
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    response = await api_client.get(f"/v1/quests/{quest_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_add_signup_rejects_non_player(api_client: Any) -> None:
    referee = await _create_user(api_client)
    referee = await _enable_referee(api_client, referee["user_id"])
    quest = await _create_quest(api_client, referee["user_id"], title="Weekend Raid")

    member = await _create_user(api_client)
    character = await _create_character(api_client, member["user_id"], name="Mage")

    response = await api_client.post(
        f"/v1/quests/{quest['quest_id']}/signups",
        json={
            "user_id": member["user_id"],
            "character_id": character["character_id"],
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
    assert "player" in response.json().get("detail", "").lower()
