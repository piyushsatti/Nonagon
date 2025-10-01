from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.domain.models.character.CharacterModel import Character
from app.domain.models.EntityIDModel import UserID
from app.domain.usecase._shared import ensure_user
from app.domain.usecase.ports import CharactersRepo, UsersRepo


@dataclass(slots=True)
class CreateCharacter:
    characters_repo: CharactersRepo
    users_repo: UsersRepo

    async def execute(
        self,
        *,
        owner_id: UserID | str,
        name: str,
        ddb_link: str,
        character_thread_link: str,
        token_link: str,
        art_link: str,
        description: str | None = None,
        notes: str | None = None,
        tags: Iterable[str] | None = None,
        created_at: datetime | None = None,
    ) -> Character:
        owner = await ensure_user(self.users_repo, owner_id)
        raw_id = await self.characters_repo.next_id()
        created_on = created_at or datetime.now(timezone.utc)

        character = Character(
            character_id=str(raw_id),
            owner_id=owner.user_id,
            name=name,
            ddb_link=ddb_link,
            character_thread_link=character_thread_link,
            token_link=token_link,
            art_link=art_link,
            created_at=created_on,
            description=description or "",
            notes=notes or "",
            tags=list(tags) if tags is not None else [],
        )
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character
