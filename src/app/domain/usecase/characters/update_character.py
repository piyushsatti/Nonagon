from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.domain.models.character.CharacterModel import Character, CharacterRole
from app.domain.models.EntityIDModel import CharacterID
from app.domain.usecase._shared import ensure_character, ensure_distinct
from app.domain.usecase.ports import CharactersRepo


@dataclass(slots=True)
class UpdateCharacterDetails:
    characters_repo: CharactersRepo

    async def execute(
        self,
        character_id: CharacterID | str,
        *,
        name: str | None = None,
        ddb_link: str | None = None,
        character_thread_link: str | None = None,
        token_link: str | None = None,
        art_link: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: CharacterRole | str | None = None,
        tags: Iterable[str] | None = None,
        created_at: datetime | None = None,
        last_played_at: datetime | None = None,
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)

        if name is not None:
            character.name = name
        if ddb_link is not None:
            character.ddb_link = ddb_link
        if character_thread_link is not None:
            character.character_thread_link = character_thread_link
        if token_link is not None:
            character.token_link = token_link
        if art_link is not None:
            character.art_link = art_link
        if description is not None:
            character.description = description
        if notes is not None:
            character.notes = notes

        if status is not None:
            character.status = CharacterRole(status)

        if tags is not None:
            character.tags = ensure_distinct(tags)

        if created_at is not None:
            character.set_created_at(created_at, override=True)

        if last_played_at is not None:
            character.update_last_played(last_played_at)

        character.validate_character()
        await self.characters_repo.upsert(character)
        return character
