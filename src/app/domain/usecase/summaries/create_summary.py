from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.summary.SummaryModel import QuestSummary, SummaryKind
from app.domain.usecase._shared import (
    ensure_character,
    ensure_distinct,
    ensure_quest,
    ensure_user,
    parse_character_id,
    parse_quest_id,
    parse_summary_id,
    parse_user_id,
)
from app.domain.usecase.ports import (
    CharactersRepo,
    QuestsRepo,
    SummariesRepo,
    UsersRepo,
)


@dataclass(slots=True)
class CreateSummary:
    summaries_repo: SummariesRepo
    users_repo: UsersRepo
    characters_repo: CharactersRepo
    quests_repo: QuestsRepo

    async def execute(
        self,
        *,
        kind: SummaryKind | str,
        author_id: UserID | str,
        character_id: CharacterID | str,
        quest_id: QuestID | str,
        raw: str,
        title: str,
        description: str,
        created_on: datetime | None = None,
        players: Iterable[UserID | str] | None = None,
        characters: Iterable[CharacterID | str] | None = None,
        linked_quests: Iterable[QuestID | str] | None = None,
        linked_summaries: Iterable[SummaryID | str] | None = None,
    ) -> QuestSummary:
        author = await ensure_user(self.users_repo, author_id)
        await ensure_character(self.characters_repo, character_id)
        await ensure_quest(self.quests_repo, quest_id)

        summary_id = parse_summary_id(await self.summaries_repo.next_id())

        player_ids = [author.user_id]
        if players is not None:
            player_ids.extend(parse_user_id(player) for player in players)
        player_ids = ensure_distinct(player_ids)

        character_ids = [parse_character_id(character_id)]
        if characters is not None:
            character_ids.extend(parse_character_id(ch) for ch in characters)
        character_ids = ensure_distinct(character_ids)

        quest_links = [parse_quest_id(quest_id)]
        if linked_quests is not None:
            quest_links.extend(parse_quest_id(q) for q in linked_quests)
        quest_links = ensure_distinct(quest_links)

        summary_links: list[SummaryID] = []
        if linked_summaries is not None:
            summary_links = ensure_distinct(
                parse_summary_id(summary) for summary in linked_summaries
            )

        summary = QuestSummary(
            summary_id=summary_id,
            kind=SummaryKind(kind),
            author_id=author.user_id,
            character_id=parse_character_id(character_id),
            quest_id=parse_quest_id(quest_id),
            raw=raw,
            title=title,
            description=description,
            created_on=created_on or datetime.now(timezone.utc),
            players=player_ids,
            characters=character_ids,
            linked_quests=quest_links,
            linked_summaries=summary_links,
        )
        summary.validate_summary()
        await self.summaries_repo.upsert(summary)
        return summary
