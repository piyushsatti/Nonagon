from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Dict, List, cast

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
    api_client: Any, owner_id: str, *, name: str
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "owner_id": owner_id,
        "name": name,
        "ddb_link": f"https://ddb.example/{name}",
        "character_thread_link": f"https://discord.example/threads/{name}",
        "token_link": f"https://tokens.example/{name}.png",
        "art_link": f"https://art.example/{name}.png",
    }
    response = await api_client.post("/v1/characters", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _create_quest(
    api_client: Any,
    referee_id: str,
    *,
    title: str = "Story Hook",
) -> Dict[str, Any]:
    start = (datetime.now(timezone.utc) + timedelta(minutes=5)).replace(microsecond=0)
    payload: Dict[str, Any] = {
        "referee_id": referee_id,
        "channel_id": "ch-001",
        "message_id": "msg-001",
        "title": title,
        "raw": "Quest intro",
        "description": "An adventure begins",
        "starting_at": start.isoformat(),
        "duration_hours": 1,
    }
    response = await api_client.post("/v1/quests", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _create_summary(
    api_client: Any,
    *,
    author_id: str,
    character_id: str,
    quest_id: str,
    additional_players: List[str] | None = None,
    additional_characters: List[str] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "kind": "PLAYER",
        "author_id": author_id,
        "character_id": character_id,
        "quest_id": quest_id,
        "raw": "Summary body",
        "title": "Aftermath",
        "description": "Detailed notes",
        "players": additional_players or [],
        "characters": additional_characters or [],
    }
    response = await api_client.post("/v1/summaries", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def test_summary_crud_and_relationships(api_client: Any) -> None:
    referee = await _create_user(api_client)
    referee = await _enable_referee(api_client, referee["user_id"])
    quest = await _create_quest(api_client, referee["user_id"], title="Mystery Night")

    author = await _create_user(api_client, {"discord_id": "author"})
    author = await _enable_player(api_client, author["user_id"])
    main_character = await _create_character(api_client, author["user_id"], name="bard")

    supporting_player = await _create_user(api_client, {"discord_id": "support"})
    supporting_player = await _enable_player(api_client, supporting_player["user_id"])
    supporting_character = await _create_character(
        api_client, supporting_player["user_id"], name="guardian"
    )

    summary = await _create_summary(
        api_client,
        author_id=author["user_id"],
        character_id=main_character["character_id"],
        quest_id=quest["quest_id"],
        additional_players=[supporting_player["user_id"]],
        additional_characters=[supporting_character["character_id"]],
    )

    summary_id = summary["summary_id"]
    assert summary["title"] == "Aftermath"
    assert summary["players"] == [author["user_id"], supporting_player["user_id"]]
    assert summary["characters"] == [
        main_character["character_id"],
        supporting_character["character_id"],
    ]

    created_on = datetime.fromisoformat(summary["created_on"].replace("Z", "+00:00"))
    edited_at = (created_on + timedelta(minutes=10)).replace(microsecond=0)
    for filter_params in (
        {"author_id": author["user_id"]},
        {"character_id": main_character["character_id"]},
        {"player_id": author["user_id"]},
    ):
        response = await api_client.get(
            "/v1/summaries",
            params={**filter_params, "limit": 10},
        )
        assert response.status_code == HTTPStatus.OK, response.text
        summaries = response.json()
        assert isinstance(summaries, list)
        summary_dicts = cast(List[Dict[str, Any]], summaries)
        assert any(item["summary_id"] == summary_id for item in summary_dicts)

    response = await api_client.patch(
        f"/v1/summaries/{summary_id}",
        json={
            "title": "Revised Title",
            "description": "Updated details",
            "raw": "Updated body",
            "last_edited_at": edited_at.isoformat(),
            "players": [author["user_id"]],
            "characters": [main_character["character_id"]],
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    summary = response.json()
    assert summary["title"] == "Revised Title"
    assert summary["players"] == [author["user_id"]]
    assert summary["characters"] == [main_character["character_id"]]
    assert summary["last_edited_at"].startswith(edited_at.isoformat()[:19])

    response = await api_client.post(
        f"/v1/summaries/{summary_id}/players/{supporting_player['user_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    summary = response.json()
    assert supporting_player["user_id"] in summary["players"]

    response = await api_client.delete(
        f"/v1/summaries/{summary_id}/players/{supporting_player['user_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    summary = response.json()
    assert supporting_player["user_id"] not in summary["players"]

    response = await api_client.post(
        f"/v1/summaries/{summary_id}/characters/{supporting_character['character_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    summary = response.json()
    assert supporting_character["character_id"] in summary["characters"]

    response = await api_client.delete(
        f"/v1/summaries/{summary_id}/characters/{supporting_character['character_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    summary = response.json()
    assert supporting_character["character_id"] not in summary["characters"]

    response = await api_client.post(
        f"/v1/summaries/{summary_id}:updateLastEdited",
        params={"edited_at": edited_at.isoformat()},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    summary = response.json()
    assert summary["last_edited_at"].startswith(edited_at.isoformat()[:19])

    response = await api_client.delete(f"/v1/summaries/{summary_id}")
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    response = await api_client.get(f"/v1/summaries/{summary_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_summary_creation_requires_existing_records(api_client: Any) -> None:
    author = await _create_user(api_client)
    character = await _create_character(api_client, author["user_id"], name="orphan")

    response = await api_client.post(
        "/v1/summaries",
        json={
            "kind": "PLAYER",
            "author_id": author["user_id"],
            "character_id": character["character_id"],
            "quest_id": "QUES9999",
            "raw": "Body",
            "title": "Missing Quest",
            "description": "Should fail",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
    assert "quest" in response.json().get("detail", "").lower()
