from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import SummaryID
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.usecase._shared import ensure_summary
from app.domain.usecase.ports import SummariesRepo


@dataclass(slots=True)
class GetSummary:
    summaries_repo: SummariesRepo

    async def execute(self, summary_id: SummaryID | str) -> QuestSummary:
        return await ensure_summary(self.summaries_repo, summary_id)
