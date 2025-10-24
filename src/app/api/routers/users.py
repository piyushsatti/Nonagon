from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.api.mappers import user_to_api
from app.api.schemas import User as APIUser
from app.api.schemas import UserIn as APIUserIn
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.UserModel import Player, Role, User
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.users_repo import UsersRepoMongo

router = APIRouter(prefix="/v1/guilds/{guild_id}/users", tags=["users"])
users_repo = UsersRepoMongo()
characters_repo = CharactersRepoMongo()


def _now() -> datetime:
	return datetime.now(timezone.utc)


def _normalize_roles(raw: Optional[list[str]]) -> list[Role]:
	if not raw:
		return [Role.MEMBER]
	seen: set[Role] = set()
	roles: list[Role] = []
	for value in raw:
		role = Role(value)
		if role not in seen:
			seen.add(role)
			roles.append(role)
	return roles or [Role.MEMBER]


async def _require_user(guild_id: int, user_id: str) -> User:
	user = await users_repo.get(guild_id, user_id)
	if user is None:
		raise HTTPException(status_code=404, detail="User not found")
	user.guild_id = guild_id
	return user


async def _persist_user(guild_id: int, user: User) -> APIUser:
	user.guild_id = guild_id
	user.validate_user()
	await users_repo.upsert(guild_id, user)
	return user_to_api(user)


@router.post("", response_model=APIUser, status_code=201)
async def create_user(guild_id: int, body: APIUserIn) -> APIUser:
	raw_id = await users_repo.next_id(guild_id)
	uid = raw_id if isinstance(raw_id, str) else str(raw_id)
	user = User(
		user_id=UserID.parse(uid),
		guild_id=guild_id,
		discord_id=body.discord_id,
		dm_channel_id=body.dm_channel_id,
		dm_opt_in=body.dm_opt_in if body.dm_opt_in is not None else True,
		roles=_normalize_roles(body.roles),
		joined_at=_now(),
		last_active_at=_now(),
	)
	return await _persist_user(guild_id, user)


@router.get("/{user_id}", response_model=APIUser)
async def get_user(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	return user_to_api(user)


@router.get("/by-discord/{discord_id}", response_model=APIUser)
async def get_user_by_discord(guild_id: int, discord_id: str) -> APIUser:
	user = await users_repo.get_by_discord_id(guild_id, discord_id)
	if user is None:
		raise HTTPException(status_code=404, detail="User not found")
	user.guild_id = guild_id
	return user_to_api(user)


@router.patch("/{user_id}", response_model=APIUser)
async def patch_user(guild_id: int, user_id: str, body: APIUserIn) -> APIUser:
	user = await _require_user(guild_id, user_id)
	if body.dm_channel_id is not None:
		user.dm_channel_id = body.dm_channel_id
	if body.dm_opt_in is not None:
		user.dm_opt_in = body.dm_opt_in
	if body.roles is not None and body.roles:
		user.roles = _normalize_roles(body.roles)
	if body.discord_id is not None:
		user.discord_id = body.discord_id
	return await _persist_user(guild_id, user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(guild_id: int, user_id: str) -> None:
	deleted = await users_repo.delete(guild_id, user_id)
	if not deleted:
		raise HTTPException(status_code=404, detail="User not found")


@router.post("/{user_id}:enablePlayer", response_model=APIUser)
async def enable_player(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	user.enable_player()
	return await _persist_user(guild_id, user)


@router.post("/{user_id}:disablePlayer", response_model=APIUser)
async def disable_player(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	user.disable_player()
	return await _persist_user(guild_id, user)


@router.post("/{user_id}:enableReferee", response_model=APIUser)
async def enable_referee(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	user.enable_referee()
	return await _persist_user(guild_id, user)


@router.post("/{user_id}:disableReferee", response_model=APIUser)
async def disable_referee(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	user.disable_referee()
	return await _persist_user(guild_id, user)


def _ensure_player_profile(user: User) -> None:
	if user.player is None:
		user.player = Player()
	if not user.is_player:
		user.enable_player()


@router.post("/{user_id}/characters/{character_id}:link", response_model=APIUser)
async def link_character(guild_id: int, user_id: str, character_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	character = await characters_repo.get(guild_id, character_id)
	if character is None:
		raise HTTPException(status_code=404, detail="Character not found")

	_ensure_player_profile(user)
	parsed = CharacterID.parse(character_id)
	if parsed not in user.player.characters:
		user.player.characters.append(parsed)

	character.guild_id = guild_id
	character.owner_id = user.user_id
	await characters_repo.upsert(guild_id, character)

	return await _persist_user(guild_id, user)


@router.post("/{user_id}/characters/{character_id}:unlink", response_model=APIUser)
async def unlink_character(guild_id: int, user_id: str, character_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	parsed = CharacterID.parse(character_id)

	if user.player is not None and parsed in user.player.characters:
		user.player.characters.remove(parsed)

	return await _persist_user(guild_id, user)


@router.post("/{user_id}:updateLastActive", response_model=APIUser)
async def update_last_active(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	user.update_last_active(_now())
	return await _persist_user(guild_id, user)


@router.post("/{user_id}:updatePlayerLastActive", response_model=APIUser)
async def update_player_last_active(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	if not user.is_player:
		raise HTTPException(status_code=400, detail="User is not a player")
	user.update_last_active(_now())
	return await _persist_user(guild_id, user)


@router.post("/{user_id}:updateRefereeLastActive", response_model=APIUser)
async def update_referee_last_active(guild_id: int, user_id: str) -> APIUser:
	user = await _require_user(guild_id, user_id)
	if not user.is_referee:
		raise HTTPException(status_code=400, detail="User is not a referee")
	user.update_last_active(_now())
	return await _persist_user(guild_id, user)
