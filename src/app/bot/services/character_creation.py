from __future__ import annotations

import logging
from dataclasses import dataclass, field

import discord

from app.domain.models.character.CharacterModel import Character
from app.domain.models.user.UserModel import User
from app.domain.usecase.characters.create_character import CreateCharacter
from app.domain.usecase.ports import CharactersRepo, UsersRepo
from app.domain.usecase.users.link_character import LinkCharacterToUser

from .user_provisioning import UserProvisioningService


class PlayerRoleRequiredError(PermissionError):
    """Raised when a user without the PLAYER role attempts character creation."""


def _empty_tags() -> list[str]:
    return []


@dataclass(slots=True)
class CharacterCreatePayload:
    name: str
    ddb_link: str
    character_thread_link: str
    token_link: str
    art_link: str
    description: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=_empty_tags)


@dataclass(slots=True)
class CharacterCreationResult:
    character: Character
    user: User


class CharacterCreationService:
    def __init__(
        self,
        *,
        characters_repo: CharactersRepo,
        users_repo: UsersRepo,
        user_provisioning: UserProvisioningService,
        logger: logging.Logger | None = None,
    ) -> None:
        self._create_character = CreateCharacter(
            characters_repo=characters_repo, users_repo=users_repo
        )
        self._link_character = LinkCharacterToUser(
            users_repo=users_repo, characters_repo=characters_repo
        )
        self._user_provisioning = user_provisioning
        self._log = logger or logging.getLogger(__name__)

    async def create_for_member(
        self,
        member: discord.Member,
        payload: CharacterCreatePayload,
    ) -> CharacterCreationResult:
        provision = await self._user_provisioning.ensure_member_user(member)
        user = provision.user
        if not user.is_player:
            raise PlayerRoleRequiredError("Player role required to create characters")

        character = await self._create_character.execute(
            owner_id=user.user_id,
            name=payload.name,
            ddb_link=payload.ddb_link,
            character_thread_link=payload.character_thread_link,
            token_link=payload.token_link,
            art_link=payload.art_link,
            description=payload.description,
            notes=payload.notes,
            tags=payload.tags,
        )

        updated_user, _ = await self._link_character.execute(
            user.user_id, character.character_id
        )

        self._log.info(
            "Character created",
            extra={
                "character_id": character.character_id,
                "owner_user_id": str(updated_user.user_id),
                "owner_member_id": member.id,
            },
        )
        return CharacterCreationResult(character=character, user=updated_user)
