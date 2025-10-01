from __future__ import annotations

from fastapi import APIRouter, HTTPException

import app.api.deps as deps
from app.api.mappers import user_to_api
from app.api.schemas import ActivityPing
from app.api.schemas import User as APIUser
from app.api.schemas import UserIn as APIUserIn
from app.domain.usecase import users as user_usecases

router = APIRouter(prefix="/v1/users", tags=["Users"])
users_repo = deps.user_repo
chars_repo = deps.chars_repo


@router.get("/healthz")
async def users_healthz() -> dict[str, bool]:
    return {"ok": True}


@router.post(
    "",
    response_model=APIUser,
    status_code=201,
    response_model_exclude_none=True,
)
async def create_user(body: APIUserIn | None = None) -> APIUser:
    payload = body or APIUserIn()

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


@router.get("/{user_id}", response_model=APIUser, response_model_exclude_none=True)
async def get_user(user_id: str) -> APIUser:
    try:
        usecase = user_usecases.GetUser(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get(
    "/by-discord/{discord_id}",
    response_model=APIUser,
    response_model_exclude_none=True,
)
async def get_user_by_discord(discord_id: str) -> APIUser:
    try:
        usecase = user_usecases.GetUserByDiscord(users_repo=users_repo)
        user = await usecase.execute(discord_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.patch("/{user_id}", response_model=APIUser, response_model_exclude_none=True)
async def patch_user(user_id: str, body: APIUserIn | None = None) -> APIUser:
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
    try:
        usecase = user_usecases.DeleteUser(users_repo=users_repo)
        await usecase.execute(user_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


# ---- Role commands ----
@router.post("/{user_id}:enablePlayer", response_model=APIUser)
async def enable_player(user_id: str) -> APIUser:
    try:
        usecase = user_usecases.PromoteUserToPlayer(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{user_id}:disablePlayer",
    response_model=APIUser,
    response_model_exclude_none=True,
)
async def disable_player(user_id: str) -> APIUser:
    try:
        usecase = user_usecases.DemotePlayerToMember(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:enableReferee", response_model=APIUser)
async def enable_referee(user_id: str) -> APIUser:
    try:
        usecase = user_usecases.PromotePlayerToReferee(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:disableReferee", response_model=APIUser)
async def disable_referee(user_id: str) -> APIUser:
    try:
        usecase = user_usecases.RevokeRefereeRole(users_repo=users_repo)
        user = await usecase.execute(user_id)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# ---- Linking characters ----
@router.post(
    "/{user_id}/characters/{character_id}:link",
    response_model=APIUser,
    response_model_exclude_none=True,
)
async def link_character(user_id: str, character_id: str) -> APIUser:
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
    response_model=APIUser,
    response_model_exclude_none=True,
)
async def unlink_character(user_id: str, character_id: str) -> APIUser:
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
@router.post("/{user_id}:updateLastActive", response_model=APIUser)
async def update_last_active(user_id: str, body: ActivityPing | None = None) -> APIUser:
    payload = body or ActivityPing()

    try:
        usecase = user_usecases.UpdateLastActive(users_repo=users_repo)
        user = await usecase.execute(user_id, active_at=payload.active_at)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:updatePlayerLastActive", response_model=APIUser)
async def update_player_last_active(
    user_id: str, body: ActivityPing | None = None
) -> APIUser:
    payload = body or ActivityPing()

    try:
        usecase = user_usecases.UpdatePlayerLastActive(users_repo=users_repo)
        user = await usecase.execute(user_id, active_at=payload.active_at)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}:updateRefereeLastActive", response_model=APIUser)
async def update_referee_last_active(
    user_id: str, body: ActivityPing | None = None
) -> APIUser:
    payload = body or ActivityPing()

    try:
        usecase = user_usecases.UpdateRefereeLastActive(users_repo=users_repo)
        user = await usecase.execute(user_id, active_at=payload.active_at)
        return user_to_api(user)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
