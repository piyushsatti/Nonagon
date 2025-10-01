from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import SummaryID
from app.domain.usecase._shared import parse_summary_id
from app.domain.usecase.ports import SummariesRepo


@dataclass(slots=True)
class DeleteSummary:
    summaries_repo: SummariesRepo

    async def execute(self, summary_id: SummaryID | str) -> None:
        raw = str(parse_summary_id(summary_id))
        if not await self.summaries_repo.exists(raw):
            raise ValueError(f"Summary ID does not exist: {summary_id}")
        await self.summaries_repo.delete(raw)
