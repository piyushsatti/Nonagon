from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import QuestID
from app.domain.usecase._shared import parse_quest_id
from app.domain.usecase.ports import QuestsRepo


@dataclass(slots=True)
class DeleteQuest:
    quests_repo: QuestsRepo

    async def execute(self, quest_id: QuestID | str) -> None:
        raw = str(parse_quest_id(quest_id))
        if not await self.quests_repo.exists(raw):
            raise ValueError(f"Quest ID does not exist: {quest_id}")
        await self.quests_repo.delete(raw)
