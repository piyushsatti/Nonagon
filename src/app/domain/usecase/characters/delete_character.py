from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import CharacterID
from app.domain.usecase._shared import parse_character_id
from app.domain.usecase.ports import CharactersRepo


@dataclass(slots=True)
class DeleteCharacter:
    characters_repo: CharactersRepo

    async def execute(self, character_id: CharacterID | str) -> None:
        raw = str(parse_character_id(character_id))
        if not await self.characters_repo.exists(raw):
            raise ValueError(f"Character ID does not exist: {character_id}")
        await self.characters_repo.delete(raw)
