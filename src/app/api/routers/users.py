from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

import app.api.deps as deps
from app.api.mappers import user_to_api
from app.api.schemas import User as APIUser
from app.api.schemas import UserIn as APIUserIn
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.usecase.unit import user_unit

router = APIRouter(prefix="/v1/users")
users_repo = deps.user_repo
chars_repo = deps.chars_repo


@router.get("/healthz")
def users_healthz():
    return {"ok": True}


@router.post("", response_model=APIUser, status_code=201)
def create_user():

    try:
        u = user_unit.create_user(users_repo=users_repo)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}", response_model=APIUser)
def get_user(request: Request, user_id: str):

    try:
        u = user_unit.get_user(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/by-discord/{discord_id}",
    response_model=APIUser,
)
def get_user_by_discord(discord_id: str):
    try:
        u = user_unit.get_user_by_discord_id(users_repo, discord_id)
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{user_id}", response_model=APIUser)
def patch_user(user_id: str, body: APIUserIn):
    try:
        u = user_unit.update_user(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str):
    try:
        user_unit.delete_user(users_repo, user_id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Role commands ----
@router.post("/{user_id}:enablePlayer", response_model=APIUser)
def enable_player(user_id: str):
    try:
        u = user_unit.enable_player_role(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{user_id}:disablePlayer",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def disable_player(user_id: str):
    try:
        u = user_unit.disable_player_role(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}:enableReferee", response_model=APIUser)
def enable_referee(user_id: str):
    try:
        u = user_unit.enable_referee_role(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}:disableReferee", response_model=APIUser)
def disable_referee(request: Request, user_id: str):
    try:
        u = user_unit.disable_referee_role(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- Linking characters ----
@router.post("/{user_id}/characters/{character_id}:link", response_model=APIUser)
def link_character(request: Request, user_id: str, character_id: str):
    try:
        u, _ = user_unit.link_character_to_user(
            users_repo=users_repo,
            characters_repo=chars_repo,
            user_id=user_id,
            character_id=character_id,
        )
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/characters/{character_id}:unlink", response_model=APIUser)
def unlink_character(request: Request, user_id: str, character_id: str):
    try:
        u, _ = user_unit.unlink_character_from_user(
            users_repo=users_repo,
            characters_repo=chars_repo,
            user_id=UserID.parse(user_id),
            character_id=CharacterID.parse(character_id),
        )
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- Telemetry ----
@router.post("/{user_id}:updateLastActive", response_model=APIUser)
def update_last_active(request: Request, user_id: str):
    try:
        u = user_unit.update_user_last_active(users_repo, UserID.parse(user_id))
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}:updatePlayerLastActive", response_model=APIUser)
def update_player_last_active(request: Request, user_id: str):
    try:
        u = user_unit.update_player_last_active(users_repo, user_id)
        return user_to_api(u)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}:updateRefereeLastActive", response_model=APIUser)
def update_referee_last_active(request: Request, user_id: str):
    try:
        u = user_unit.update_referee_last_active(users_repo, user_id)
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
