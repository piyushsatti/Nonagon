from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import QuestID
from app.domain.models.quest.QuestModel import Quest
from app.domain.usecase._shared import ensure_quest
from app.domain.usecase.ports import QuestsRepo


@dataclass(slots=True)
class GetQuest:
    quests_repo: QuestsRepo

    async def execute(self, quest_id: QuestID | str) -> Quest:
        return await ensure_quest(self.quests_repo, quest_id)
