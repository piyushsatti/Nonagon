from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.models.EntityIDModel import SummaryID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase._shared import ensure_summary
from app.domain.usecase.ports import SummariesRepo


@dataclass(slots=True)
class TouchSummary:
    summaries_repo: SummariesRepo

    async def execute(
        self, summary_id: SummaryID | str, *, edited_at: datetime | None = None
    ) -> QuestSummary:
        summary = await ensure_summary(self.summaries_repo, summary_id)
        summary.last_edited_at = edited_at or datetime.now(timezone.utc)
        await self.summaries_repo.upsert(summary)
        return summary
