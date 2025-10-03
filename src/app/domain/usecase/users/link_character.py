from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.character.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.user.UserModel import User
from app.domain.usecase._shared import ensure_character, ensure_user, parse_character_id
from app.domain.usecase.ports import CharactersRepo, UsersRepo


@dataclass(slots=True)
class LinkCharacterToUser:
    users_repo: UsersRepo
    characters_repo: CharactersRepo

    async def execute(
        self, user_id: UserID | str, character_id: CharacterID | str
    ) -> tuple[User, Character]:
        user = await ensure_user(self.users_repo, user_id)
        character = await ensure_character(self.characters_repo, character_id)

        if character.owner_id != user.user_id:
            raise ValueError(
                f"User {user.user_id} is not the owner of character {character.character_id}"
            )

        char_id = parse_character_id(character_id)

        if not user.is_player:
            user.enable_player()
        player = user.get_player()

        if char_id in player.characters:
            raise ValueError(
                f"Character {char_id} is already linked to user {user.user_id}"
            )

        player.add_character(char_id)
        player.ensure_sanity()
        user.validate_user()

        await self.users_repo.upsert(user)
        return user, character


@dataclass(slots=True)
class UnlinkCharacterFromUser:
    users_repo: UsersRepo
    characters_repo: CharactersRepo

    async def execute(
        self, user_id: UserID | str, character_id: CharacterID | str
    ) -> tuple[User, Character]:
        user = await ensure_user(self.users_repo, user_id)
        character = await ensure_character(self.characters_repo, character_id)
        char_id = parse_character_id(character_id)

        if character.owner_id != user.user_id:
            raise ValueError(
                f"User {user.user_id} is not the owner of character {character.character_id}"
            )

        if user.player is None or char_id not in user.player.characters:
            raise ValueError(
                f"Character {char_id} is not linked to user {user.user_id}"
            )

        user.player.remove_character(char_id)
        user.player.ensure_sanity()
        user.validate_user()

        await self.users_repo.upsert(user)
        return user, character
