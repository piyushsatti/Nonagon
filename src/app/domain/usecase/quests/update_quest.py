from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.models.EntityIDModel import QuestID
from app.domain.models.quest.QuestModel import Quest
from app.domain.usecase._shared import ensure_quest
from app.domain.usecase.ports import QuestsRepo


@dataclass(slots=True)
class UpdateQuestDetails:
    quests_repo: QuestsRepo

    async def execute(
        self,
        quest_id: QuestID | str,
        *,
        title: str | None = None,
        description: str | None = None,
        starting_at: datetime | None = None,
        duration: timedelta | None = None,
        image_url: str | None = None,
        raw: str | None = None,
    ) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)

        if title is not None:
            quest.title = title
        if description is not None:
            quest.description = description
            quest.description_md = description
        if starting_at is not None:
            quest.starting_at = starting_at
            quest.starts_at_utc = starting_at
        if duration is not None:
            quest.duration = duration
            quest.duration_minutes = int(duration.total_seconds() // 60)
        if image_url is not None:
            quest.image_url = image_url
        if raw is not None:
            quest.raw = raw
            quest.raw_markdown = raw

        quest.validate_quest()
        await self.quests_repo.upsert(quest)
        return quest
