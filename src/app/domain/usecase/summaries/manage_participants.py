from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import CharacterID, SummaryID, UserID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase._shared import (
    ensure_character,
    ensure_summary,
    ensure_user,
    parse_character_id,
    parse_user_id,
)
from app.domain.usecase.ports import CharactersRepo, SummariesRepo, UsersRepo


@dataclass(slots=True)
class AddPlayerToSummary:
    summaries_repo: SummariesRepo
    users_repo: UsersRepo

    async def execute(
        self, summary_id: SummaryID | str, player_id: UserID | str
    ) -> QuestSummary:
        summary = await ensure_summary(self.summaries_repo, summary_id)
        player = await ensure_user(self.users_repo, player_id)

        if player.user_id in summary.players:
            raise ValueError(
                f"Player {player.user_id} already in summary {summary.summary_id}"
            )

        summary.players.append(player.user_id)
        summary.validate_summary()
        await self.summaries_repo.upsert(summary)
        return summary


@dataclass(slots=True)
class RemovePlayerFromSummary:
    summaries_repo: SummariesRepo
    users_repo: UsersRepo

    async def execute(
        self, summary_id: SummaryID | str, player_id: UserID | str
    ) -> QuestSummary:
        summary = await ensure_summary(self.summaries_repo, summary_id)
        player_id = parse_user_id(player_id)

        if player_id not in summary.players:
            raise ValueError(f"Player {player_id} not in summary {summary.summary_id}")

        summary.players.remove(player_id)
        summary.validate_summary()
        await self.summaries_repo.upsert(summary)
        return summary


@dataclass(slots=True)
class AddCharacterToSummary:
    summaries_repo: SummariesRepo
    characters_repo: CharactersRepo

    async def execute(
        self, summary_id: SummaryID | str, character_id: CharacterID | str
    ) -> QuestSummary:
        summary = await ensure_summary(self.summaries_repo, summary_id)
        await ensure_character(self.characters_repo, character_id)
        char_id = parse_character_id(character_id)

        if char_id in summary.characters:
            raise ValueError(
                f"Character {char_id} already in summary {summary.summary_id}"
            )

        summary.characters.append(char_id)
        summary.validate_summary()
        await self.summaries_repo.upsert(summary)
        return summary


@dataclass(slots=True)
class RemoveCharacterFromSummary:
    summaries_repo: SummariesRepo
    characters_repo: CharactersRepo

    async def execute(
        self, summary_id: SummaryID | str, character_id: CharacterID | str
    ) -> QuestSummary:
        summary = await ensure_summary(self.summaries_repo, summary_id)
        char_id = parse_character_id(character_id)

        if char_id not in summary.characters:
            raise ValueError(f"Character {char_id} not in summary {summary.summary_id}")

        summary.characters.remove(char_id)
        summary.validate_summary()
        await self.summaries_repo.upsert(summary)
        return summary
