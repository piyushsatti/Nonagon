from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any


async def _create_user(
    api_client: Any, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = dict(payload or {})
    response = await api_client.post("/v1/users", json=body)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _character_payload(
    owner_id: str, *, index: int = 1, **overrides: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "owner_id": owner_id,
        "name": f"Character-{index}",
        "ddb_link": f"https://ddb.example/{index}",
        "character_thread_link": f"https://discord.example/threads/{index}",
        "token_link": f"https://tokens.example/{index}.png",
        "art_link": f"https://art.example/{index}.png",
    }
    payload.update(overrides)
    return payload


async def _create_character(
    api_client: Any, owner_id: str, *, index: int = 1, **overrides: Any
) -> dict[str, Any]:
    payload = _character_payload(owner_id, index=index, **overrides)
    response = await api_client.post("/v1/characters", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _get_character(
    api_client: Any, character_id: str
) -> tuple[int, dict[str, Any]]:
    response = await api_client.get(f"/v1/characters/{character_id}")
    data: dict[str, Any] = {}
    if response.headers.get("content-type", "").startswith("application/json"):
        data = response.json()
    return response.status_code, data


async def test_create_character_assigns_defaults(api_client: Any) -> None:
    user = await _create_user(api_client)
    character = await _create_character(api_client, user["user_id"], index=1)

    assert character["character_id"].startswith("CHAR")
    assert character["owner_id"] == user["user_id"]
    assert character["description"] == ""
    assert character["notes"] == ""
    assert character["tags"] == []
    assert character["quests_played"] == 0
    assert character["summaries_written"] == 0


async def test_create_character_requires_existing_owner(api_client: Any) -> None:
    payload = _character_payload("USER9999")
    response = await api_client.post("/v1/characters", json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


async def test_patch_character_updates_metadata(api_client: Any) -> None:
    user = await _create_user(api_client)
    character = await _create_character(api_client, user["user_id"], index=2)
    character_id = character["character_id"]

    played_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=5)
    update_payload: Any = {
        "name": "Updated Name",
        "description": "New adventures await",
        "notes": "Prefers close combat",
        "tags": ["Fighter", "Leader", "Fighter"],
        "status": "INACTIVE",
        "last_played_at": played_at.isoformat(),
    }

    response = await api_client.patch(
        f"/v1/characters/{character_id}",
        json=update_payload,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    updated = response.json()

    assert updated["name"] == "Updated Name"
    assert updated["description"] == "New adventures await"
    assert updated["notes"] == "Prefers close combat"
    assert updated["status"] == "INACTIVE"
    assert updated["tags"] == ["Fighter", "Leader"]
    returned_last_played = datetime.fromisoformat(
        updated["last_played_at"].replace("Z", "+00:00")
    )
    assert returned_last_played == played_at

    status_code, fetched = await _get_character(api_client, character_id)
    assert status_code == HTTPStatus.OK
    assert fetched["status"] == "INACTIVE"
    assert fetched["tags"] == ["Fighter", "Leader"]


async def test_increment_counters(api_client: Any) -> None:
    user = await _create_user(api_client)
    character = await _create_character(api_client, user["user_id"], index=3)
    character_id = character["character_id"]

    response = await api_client.post(
        f"/v1/characters/{character_id}:incrementQuestsPlayed"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert payload["quests_played"] == 1

    response = await api_client.post(
        f"/v1/characters/{character_id}:incrementSummariesWritten"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert payload["summaries_written"] == 1


async def test_update_last_played_endpoint(api_client: Any) -> None:
    user = await _create_user(api_client)
    character = await _create_character(api_client, user["user_id"], index=4)
    character_id = character["character_id"]

    response = await api_client.post(f"/v1/characters/{character_id}:updateLastPlayed")
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert payload["last_played_at"] is not None


async def test_manage_played_with_relationship(api_client: Any) -> None:
    user = await _create_user(api_client)
    primary = await _create_character(api_client, user["user_id"], index=5)
    partner = await _create_character(api_client, user["user_id"], index=6)

    response = await api_client.post(
        f"/v1/characters/{primary['character_id']}/playedWith/{partner['character_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert partner["character_id"] in payload["played_with"]

    response = await api_client.delete(
        f"/v1/characters/{primary['character_id']}/playedWith/{partner['character_id']}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert partner["character_id"] not in payload["played_with"]


async def test_manage_quest_and_summary_links(api_client: Any) -> None:
    user = await _create_user(api_client)
    character = await _create_character(api_client, user["user_id"], index=7)
    character_id = character["character_id"]

    quest_id = "QUES1234"
    response = await api_client.post(
        f"/v1/characters/{character_id}/playedIn/{quest_id}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert quest_id in payload["played_in"]

    response = await api_client.delete(
        f"/v1/characters/{character_id}/playedIn/{quest_id}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert quest_id not in payload["played_in"]

    summary_id = "SUMM4321"
    response = await api_client.post(
        f"/v1/characters/{character_id}/mentionedIn/{summary_id}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert summary_id in payload["mentioned_in"]

    response = await api_client.delete(
        f"/v1/characters/{character_id}/mentionedIn/{summary_id}"
    )
    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert summary_id not in payload["mentioned_in"]


async def test_delete_character_and_confirm_absent(api_client: Any) -> None:
    user = await _create_user(api_client)
    character = await _create_character(api_client, user["user_id"], index=8)
    character_id = character["character_id"]

    response = await api_client.delete(f"/v1/characters/{character_id}")
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    status_code, _ = await _get_character(api_client, character_id)
    assert status_code == HTTPStatus.NOT_FOUND


async def test_get_missing_character_returns_404(api_client: Any) -> None:
    response = await api_client.get("/v1/characters/CHAR9999")
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text
