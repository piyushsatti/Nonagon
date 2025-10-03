from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.character.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID
from app.domain.usecase._shared import ensure_character
from app.domain.usecase.ports import CharactersRepo


@dataclass(slots=True)
class GetCharacter:
    characters_repo: CharactersRepo

    async def execute(self, character_id: CharacterID | str) -> Character:
        return await ensure_character(self.characters_repo, character_id)
