from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase._shared import parse_character_id, parse_user_id
from app.domain.usecase.ports import SummariesRepo


@dataclass(slots=True)
class ListSummaries:
    summaries_repo: SummariesRepo

    async def execute(
        self,
        *,
        author_id: UserID | str | None = None,
        character_id: CharacterID | str | None = None,
        player_id: UserID | str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QuestSummary]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        filters = [value is not None for value in (author_id, character_id, player_id)]
        if sum(filters) > 1:
            raise ValueError("only one filter can be applied at a time")

        if author_id is not None:
            uid = parse_user_id(author_id)
            return await self.summaries_repo.list_by_author(
                str(uid), limit=limit, offset=offset
            )

        if character_id is not None:
            cid = parse_character_id(character_id)
            return await self.summaries_repo.list_by_character(
                str(cid), limit=limit, offset=offset
            )

        if player_id is not None:
            pid = parse_user_id(player_id)
            return await self.summaries_repo.list_by_player(
                str(pid), limit=limit, offset=offset
            )

        return await self.summaries_repo.list(limit=limit, offset=offset)
