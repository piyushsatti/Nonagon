from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import QuestID
from app.domain.models.quest.QuestModel import Quest
from app.domain.usecase._shared import ensure_quest
from app.domain.usecase.ports import QuestsRepo


@dataclass(slots=True)
class MarkQuestCompleted:
    quests_repo: QuestsRepo

    async def execute(self, quest_id: QuestID | str) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        quest.set_completed()
        await self.quests_repo.upsert(quest)
        return quest


@dataclass(slots=True)
class MarkQuestCancelled:
    quests_repo: QuestsRepo

    async def execute(self, quest_id: QuestID | str) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        quest.set_cancelled()
        await self.quests_repo.upsert(quest)
        return quest


@dataclass(slots=True)
class MarkQuestAnnounced:
    quests_repo: QuestsRepo

    async def execute(self, quest_id: QuestID | str) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        quest.set_announced()
        await self.quests_repo.upsert(quest)
        return quest
