from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from app.api.mappers import user_to_api
from app.api.schemas import User as APIUser, UserIn as APIUserIn
from app.domain.models.EntityIDModel import UserID, CharacterID
from app.domain.usecase.unit import user_unit
from app.domain.models.UserModel import Role  # domain enum

router = APIRouter(prefix="/v1/users", tags=["Users"])

def _repos(req: Request):
    """Tiny helper to keep lines short."""
    return req.app.state

@router.post(
    "",
    response_model=APIUser,
    status_code=201,
    response_model_exclude_none=True,
)
def create_user(request: Request, body: APIUserIn):
    try:
        roles = None if body.roles is None else [Role(r) for r in body.roles]
        u = user_unit.create_user(
            users_repo=_repos(request).users_repo,
            user_id=UserID.parse(body.user_id),
            roles=roles,
            joined_at=datetime.now(timezone.utc),
        )
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{user_id}",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def get_user(request: Request, user_id: str):
    try:
        u = user_unit.get_user(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get(
    "/by-discord/{discord_id}",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def get_user_by_discord(request: Request, discord_id: str):
    try:
        u = user_unit.get_user_by_discord_id(_repos(request).users_repo, discord_id)
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch(
    "/{user_id}",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def patch_user(request: Request, user_id: str, body: APIUserIn):
    try:
        roles = None if body.roles is None else [Role(r) for r in body.roles]
        u = user_unit.update_user(
            users_repo=_repos(request).users_repo,
            user_id=UserID.parse(user_id),
            roles=roles,  # None => no change, per your usecase contract
        )
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}", status_code=204)
def delete_user(request: Request, user_id: str):
    try:
        user_unit.delete_user(_repos(request).users_repo, UserID.parse(user_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ---- Role commands ----
@router.post(
    "/{user_id}:enablePlayer",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def enable_player(request: Request, user_id: str):
    try:
        u = user_unit.enable_player_role(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{user_id}:disablePlayer",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def disable_player(request: Request, user_id: str):
    try:
        u = user_unit.disable_player_role(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{user_id}:enableReferee",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def enable_referee(request: Request, user_id: str):
    try:
        u = user_unit.enable_referee_role(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{user_id}:disableReferee",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def disable_referee(request: Request, user_id: str):
    try:
        u = user_unit.disable_referee_role(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---- Linking characters ----
@router.post(
    "/{user_id}/characters/{character_id}:link",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def link_character(request: Request, user_id: str, character_id: str):
    try:
        u, _ = user_unit.link_character_to_user(
            users_repo=_repos(request).users_repo,
            characters_repo=_repos(request).chars_repo,
            user_id=UserID.parse(user_id),
            character_id=CharacterID.parse(character_id),
        )
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{user_id}/characters/{character_id}:unlink",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def unlink_character(request: Request, user_id: str, character_id: str):
    try:
        u, _ = user_unit.unlink_character_from_user(
            users_repo=_repos(request).users_repo,
            characters_repo=_repos(request).chars_repo,
            user_id=UserID.parse(user_id),
            character_id=CharacterID.parse(character_id),
        )
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---- Telemetry ----
@router.post(
    "/{user_id}:updateLastActive",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def update_last_active(request: Request, user_id: str):
    try:
        u = user_unit.update_user_last_active(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{user_id}:updatePlayerLastActive",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def update_player_last_active(request: Request, user_id: str):
    try:
        u = user_unit.update_player_last_active(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{user_id}:updateRefereeLastActive",
    response_model=APIUser,
    response_model_exclude_none=True,
)
def update_referee_last_active(request: Request, user_id: str):
    try:
        u = user_unit.update_referee_last_active(_repos(request).users_repo, UserID.parse(user_id))
        return user_to_api(u)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
