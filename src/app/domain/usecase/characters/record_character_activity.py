from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.models.character.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID
from app.domain.usecase._shared import (
    ensure_character,
    parse_character_id,
    parse_quest_id,
    parse_summary_id,
)
from app.domain.usecase.ports import CharactersRepo


@dataclass(slots=True)
class IncrementCharacterQuestsPlayed:
    characters_repo: CharactersRepo

    async def execute(self, character_id: CharacterID | str) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        character.increment_quests_played()
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class IncrementCharacterSummariesWritten:
    characters_repo: CharactersRepo

    async def execute(self, character_id: CharacterID | str) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        character.increment_summaries_written()
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class UpdateCharacterLastPlayed:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, *, played_at: datetime | None = None
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        character.update_last_played(played_at or datetime.now(timezone.utc))
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class AddCharacterPlayedWith:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, other_character_id: CharacterID | str
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        other_id = parse_character_id(other_character_id)
        character.add_played_with(other_id)
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class RemoveCharacterPlayedWith:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, other_character_id: CharacterID | str
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        other_id = parse_character_id(other_character_id)
        character.remove_played_with(other_id)
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class AddCharacterPlayedIn:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, quest_id: QuestID | str
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        quest = parse_quest_id(quest_id)
        character.add_played_in(quest)
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class RemoveCharacterPlayedIn:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, quest_id: QuestID | str
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        quest = parse_quest_id(quest_id)
        character.remove_played_in(quest)
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class AddCharacterMentionedIn:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, summary_id: SummaryID | str
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        summary = parse_summary_id(summary_id)
        character.add_mentioned_in(summary)
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character


@dataclass(slots=True)
class RemoveCharacterMentionedIn:
    characters_repo: CharactersRepo

    async def execute(
        self, character_id: CharacterID | str, summary_id: SummaryID | str
    ) -> Character:
        character = await ensure_character(self.characters_repo, character_id)
        summary = parse_summary_id(summary_id)
        character.remove_mentioned_in(summary)
        character.validate_character()
        await self.characters_repo.upsert(character)
        return character
