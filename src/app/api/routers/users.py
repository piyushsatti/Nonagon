"""FastAPI routes for managing Nonagon users and their related state."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import app.api.deps as deps
from app.api.mappers import user_to_api
from app.api.schemas import ActivityPing, User, UserCreate, UserUpdate
from app.domain.usecase import users as user_usecases

router = APIRouter(prefix="/v1/users", tags=["Users"])
users_repo = deps.user_repo
chars_repo = deps.chars_repo


@router.get("/healthz")
async def users_healthz() -> dict[str, bool]:
    """Return a static healthy response so external systems can probe the API."""
    return {"ok": True}


@router.post(
    "",
    response_model=User,
    status_code=201,
    response_model_exclude_none=True,
)
async def create_user(body: UserCreate | None = None) -> User:
    """Register a new user or ensure one exists using optional Discord metadata."""
    payload = body or UserCreate()

    try:
        usecase = user_usecases.RegisterUser(users_repo=users_repo)
        user = await usecase.execute(
            discord_id=payload.discord_id,
            dm_channel_id=payload.dm_channel_id,
            joined_at=payload.joined_at,
            roles=payload.roles,
        )
        return user_to_api(user)
    except ValueError as err:  # pragma: no cover - validation mapped to HTTP
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/{user_id}", response_model=User, response_model_exclude_none=True)
async def get_user(user_id: str) -> User:
    """Fetch a user by canonical Nonagon user identifier."""
    try:
        usecase = user_usecases.GetUser(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get(
    "/by-discord/{discord_id}",
    response_model=User,
    response_model_exclude_none=True,
)
async def get_user_by_discord(discord_id: str) -> User:
    """Look up a user by their Discord snowflake identifier."""
    try:
        usecase = user_usecases.GetUserByDiscord(users_repo=users_repo)
        user = await usecase.execute(discord_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.patch("/{user_id}", response_model=User, response_model_exclude_none=True)
async def patch_user(user_id: str, body: UserUpdate | None = None) -> User:
    """Partially update a user's contact or lifecycle metadata."""
    payload = body.model_dump(exclude_unset=True) if body else {}

    try:
        usecase = user_usecases.UpdateUserProfile(users_repo=users_repo)
        user = await usecase.execute(
            user_id,
            discord_id=payload.get("discord_id"),
            dm_channel_id=payload.get("dm_channel_id"),
            joined_at=payload.get("joined_at"),
            last_active_at=payload.get("last_active_at"),
        )
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str) -> None:
    """Remove a user record when it is no longer needed."""
    try:
        usecase = user_usecases.DeleteUser(users_repo=users_repo)
        await usecase.execute(user_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


# ---- Role commands ----
@router.post("/{user_id}:enablePlayer", response_model=User)
async def enable_player(user_id: str) -> User:
    """Grant the player role to a user by toggling their domain profile."""
    try:
        usecase = user_usecases.PromoteUserToPlayer(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{user_id}:disablePlayer",
    response_model=User,
    response_model_exclude_none=True,
)
async def disable_player(user_id: str) -> User:
    """Revoke the player role for a user while keeping their base membership."""
    try:
        usecase = user_usecases.DemotePlayerToMember(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:enableReferee", response_model=User)
async def enable_referee(user_id: str) -> User:
    """Promote a player to referee so they can post quests and summaries."""
    try:
        usecase = user_usecases.PromotePlayerToReferee(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:disableReferee", response_model=User)
async def disable_referee(user_id: str) -> User:
    """Revoke referee capabilities while keeping the user's player role intact."""
    try:
        usecase = user_usecases.RevokeRefereeRole(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# ---- Linking characters ----
@router.post(
    "/{user_id}/characters/{character_id}:link",
    response_model=User,
    response_model_exclude_none=True,
)
async def link_character(user_id: str, character_id: str) -> User:
    """Associate a character record with the specified user."""
    try:
        usecase = user_usecases.LinkCharacterToUser(
            users_repo=users_repo,
            characters_repo=chars_repo,
        )
        user, _ = await usecase.execute(user_id=user_id, character_id=character_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{user_id}/characters/{character_id}:unlink",
    response_model=User,
    response_model_exclude_none=True,
)
async def unlink_character(user_id: str, character_id: str) -> User:
    """Detach a character from the user, preventing it from showing in their roster."""
    try:
        usecase = user_usecases.UnlinkCharacterFromUser(
            users_repo=users_repo,
            characters_repo=chars_repo,
        )
        user, _ = await usecase.execute(user_id=user_id, character_id=character_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# ---- Telemetry ----
@router.post("/{user_id}:updateLastActive", response_model=User)
async def update_last_active(user_id: str, body: ActivityPing | None = None) -> User:
    """Record a generic last-active timestamp for any user role."""
    payload = body or ActivityPing()

    try:
        usecase = user_usecases.UpdateLastActive(users_repo=users_repo)
        user = await usecase.execute(user_id, active_at=payload.active_at)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:updatePlayerLastActive", response_model=User)
async def update_player_last_active(
    user_id: str, body: ActivityPing | None = None
) -> User:
    """Capture player-specific activity, leaving other roles untouched."""
    payload = body or ActivityPing()

    try:
        usecase = user_usecases.UpdatePlayerLastActive(users_repo=users_repo)
        user = await usecase.execute(user_id, active_at=payload.active_at)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:updateRefereeLastActive", response_model=User)
async def update_referee_last_active(
    user_id: str, body: ActivityPing | None = None
) -> User:
    """Record the latest activity time for a referee role."""
    payload = body or ActivityPing()

    try:
        usecase = user_usecases.UpdateRefereeLastActive(users_repo=users_repo)
        user = await usecase.execute(user_id, active_at=payload.active_at)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
