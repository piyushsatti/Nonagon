from __future__ import annotations

from http import HTTPStatus
from typing import Any

import pytest

from app.api import deps
from app.api.main import app
from app.bot.services.user_provisioning import SyncStats as ProvisionSyncStats

pytestmark = pytest.mark.asyncio


class _StubProvisioningService:
    def __init__(self, *, should_raise: bool = False) -> None:
        self.should_raise = should_raise
        self.calls: list[tuple[str, int]] = []

    async def sync_members_payload(
        self,
        *,
        guild_id: str | int,
        members: list[dict[str, Any]],
    ) -> ProvisionSyncStats:
        if self.should_raise:
            raise ValueError("boom")
        snapshot = list(members)
        self.calls.append((str(guild_id), len(snapshot)))
        return ProvisionSyncStats(processed=len(snapshot), created=1)


async def test_sync_guild_members_success(
    api_client: Any, admin_headers: dict[str, str]
) -> None:
    stub = _StubProvisioningService()
    app.dependency_overrides[deps.get_user_provisioning_service] = lambda: stub
    try:
        response = await api_client.post(
            "/v1/admin/users/sync",
            json={
                "guild_id": "guild-1",
                "members": [
                    {"discord_id": "100", "joined_at": "2024-01-01T00:00:00Z"},
                    {"discord_id": "101", "joined_at": "2024-02-02T00:00:00Z"},
                ],
            },
            headers=admin_headers,
        )
    finally:
        app.dependency_overrides.pop(deps.get_user_provisioning_service, None)

    assert response.status_code == HTTPStatus.OK, response.text
    payload = response.json()
    assert payload == {"processed": 2, "created": 1}
    assert stub.calls == [("guild-1", 2)]


async def test_sync_guild_members_value_error(
    api_client: Any, admin_headers: dict[str, str]
) -> None:
    stub = _StubProvisioningService(should_raise=True)
    app.dependency_overrides[deps.get_user_provisioning_service] = lambda: stub
    try:
        response = await api_client.post(
            "/v1/admin/users/sync",
            json={"guild_id": "guild-2", "members": []},
            headers=admin_headers,
        )
    finally:
        app.dependency_overrides.pop(deps.get_user_provisioning_service, None)

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
    assert "boom" in response.json().get("detail", "")


async def test_sync_requires_admin_token(api_client: Any) -> None:
    response = await api_client.post(
        "/v1/admin/users/sync",
        json={"guild_id": "guild-3", "members": []},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    assert "token" in response.json().get("detail", "").lower()
