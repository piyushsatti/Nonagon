from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


async def _create_user(
    api_client: Any, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = await api_client.post("/v1/users", json=payload or {})
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


async def _get_user(api_client: Any, user_id: str) -> tuple[int, dict[str, Any]]:
    response = await api_client.get(f"/v1/users/{user_id}")
    data: dict[str, Any] = {}
    if response.headers.get("content-type", "").startswith("application/json"):
        data = response.json()
    return response.status_code, data
    if response.headers.get("content-type", "").startswith("application/json"):
        data = response.json()


async def _get_user_by_discord(
    api_client: Any, discord_id: str
) -> tuple[int, dict[str, Any]]:
    response = await api_client.get(f"/v1/users/by-discord/{discord_id}")
    data: dict[str, Any] = {}
    if response.headers.get("content-type", "").startswith("application/json"):
        data = response.json()
    return response.status_code, data
    if response.headers.get("content-type", "").startswith("application/json"):
        data = response.json()
    return response.status_code, data


async def test_create_user_returns_member_defaults(api_client: Any) -> None:
    user = await _create_user(api_client)

    assert user["user_id"].startswith("USER")
    assert "MEMBER" in user["roles"], user
    assert user["is_member"] is True
    assert "discord_id" not in user
    assert user.get("discord_id") is None


async def test_create_user_with_payload_and_fetch(api_client: Any) -> None:
    payload: Any = {
        "discord_id": "1234567890",
        "dm_channel_id": "0987654321",
        "roles": ["MEMBER"],
    }

    created = await _create_user(api_client, payload)

    assert created["discord_id"] == payload["discord_id"]
    assert "MEMBER" in created["roles"], created
    assert created["is_member"] is True
    assert created["is_player"] is False

    status_code, fetched = await _get_user(api_client, created["user_id"])
    assert status_code == HTTPStatus.OK
    assert fetched["user_id"] == created["user_id"]
    assert fetched["discord_id"] == payload["discord_id"]

    status_code, fetched_by_discord = await _get_user_by_discord(
        api_client, payload["discord_id"]
    )
    assert status_code == HTTPStatus.OK
    assert fetched_by_discord["user_id"] == created["user_id"]


async def test_create_user_with_player_role_requires_profile(api_client: Any) -> None:
    response = await api_client.post(
        "/v1/users",
        json={"roles": ["PLAYER"]},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    detail = response.json().get("detail")
    assert detail and "PLAYER role" in detail


async def test_patch_user_updates_contact_fields(api_client: Any) -> None:
    created = await _create_user(api_client)
    user_id = created["user_id"]

    now = datetime.now(timezone.utc).replace(microsecond=0)
    update_payload = {
        "discord_id": "updated_discord",
        "dm_channel_id": "dm-channel-123",
        "joined_at": now.isoformat(),
        "last_active_at": now.isoformat(),
    }

    response = await api_client.patch(
        f"/v1/users/{user_id}",
        json=update_payload,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    updated = response.json()

    assert updated["discord_id"] == update_payload["discord_id"]
    assert updated["dm_channel_id"] == update_payload["dm_channel_id"]
    assert updated["joined_at"].startswith(now.isoformat()[:19])
    assert updated["last_active_at"].startswith(now.isoformat()[:19])

    status_code, fetched = await _get_user(api_client, user_id)
    assert status_code == HTTPStatus.OK
    assert fetched["discord_id"] == update_payload["discord_id"]
    assert fetched["dm_channel_id"] == update_payload["dm_channel_id"]


async def test_delete_user_removes_document(api_client: Any) -> None:
    created = await _create_user(api_client)
    user_id = created["user_id"]

    response = await api_client.delete(f"/v1/users/{user_id}")
    assert response.status_code == HTTPStatus.NO_CONTENT, response.text

    status_code, _ = await _get_user(api_client, user_id)
    assert status_code == HTTPStatus.NOT_FOUND


async def test_get_missing_user_returns_404(api_client: Any) -> None:
    response = await api_client.get("/v1/users/USER9999")
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


async def test_patch_missing_user_returns_400(api_client: Any) -> None:
    response = await api_client.patch(
        "/v1/users/USER9999",
        json={"discord_id": "non-existent"},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
