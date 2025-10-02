"""Admin endpoints for coordinating guild-level synchronization tasks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

import app.api.deps as deps
from app.api.schemas import GuildSyncRequest, SyncStats
from app.bot.services.user_provisioning import UserProvisioningService

router = APIRouter(prefix="/v1/admin", tags=["Admin"])


@router.post(
    "/users/sync",
    response_model=SyncStats,
    dependencies=[Depends(deps.require_admin)],
)
async def sync_guild_members(
    payload: GuildSyncRequest,
    provisioning_service: UserProvisioningService = Depends(
        deps.get_user_provisioning_service
    ),
) -> SyncStats:
    """Trigger a bulk synchronization between Discord guild membership and the persisted user store."""
    try:
        stats = await provisioning_service.sync_members_payload(
            guild_id=payload.guild_id,
            members=[member.model_dump() for member in payload.members],
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    return SyncStats(processed=stats.processed, created=stats.created)
