from app.domain.usecases.ports import InvalidOperationError
from app.domain.models.QuestModel import Quest, QuestStatus

async def mark_completed(quests_repo, quest_id: str) -> Quest:
    q = await quests_repo.get(quest_id)
    if q.status not in (QuestStatus.RUNNING, QuestStatus.ROSTER_SELECTED):
        raise InvalidOperationError("Quest must be RUNNING/ROSTER_SELECTED.")
    q.mark_completed()
    await quests_repo.upsert(q)
    return q
