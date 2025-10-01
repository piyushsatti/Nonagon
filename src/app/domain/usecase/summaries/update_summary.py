from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase._shared import (
    ensure_distinct,
    ensure_summary,
    parse_character_id,
    parse_quest_id,
    parse_summary_id,
    parse_user_id,
)
from app.domain.usecase.ports import SummariesRepo


@dataclass(slots=True)
class UpdateSummaryContent:
    summaries_repo: SummariesRepo

    async def execute(
        self,
        summary_id: SummaryID | str,
        *,
        raw: str | None = None,
        title: str | None = None,
        description: str | None = None,
        last_edited_at: datetime | None = None,
        players: Iterable[UserID | str] | None = None,
        characters: Iterable[CharacterID | str] | None = None,
        linked_quests: Iterable[QuestID | str] | None = None,
        linked_summaries: Iterable[SummaryID | str] | None = None,
    ) -> QuestSummary:
        summary = await ensure_summary(self.summaries_repo, summary_id)

        if raw is not None:
            summary.raw = raw
        if title is not None:
            summary.title = title
        if description is not None:
            summary.description = description
        if last_edited_at is not None:
            summary.last_edited_at = last_edited_at

        if players is not None:
            summary.players = ensure_distinct(
                parse_user_id(player) for player in players
            )
        if characters is not None:
            summary.characters = ensure_distinct(
                parse_character_id(character) for character in characters
            )
        if linked_quests is not None:
            summary.linked_quests = ensure_distinct(
                parse_quest_id(quest) for quest in linked_quests
            )
        if linked_summaries is not None:
            summary.linked_summaries = ensure_distinct(
                parse_summary_id(link) for link in linked_summaries
            )

        summary.validate_summary()
        await self.summaries_repo.upsert(summary)
        return summary
