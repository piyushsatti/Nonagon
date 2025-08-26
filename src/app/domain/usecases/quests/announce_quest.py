from typing import Optional
from app.domain.usecases.ports import InvalidOperationError
from app.domain.models.quest.QuestModel import Quest, QuestStatus

async def announce_quest(
    quests_repo,
    quest_id: str,
    guild_id: Optional[int],
    channel_id: Optional[int],
    message_id: Optional[int],
    thread_id: Optional[int] = None,
) -> Quest:
    q = await quests_repo.get(quest_id)
    if q.status not in (QuestStatus.DRAFT, QuestStatus.ANNOUNCED):
        raise InvalidOperationError("Quest must be in DRAFT/ANNOUNCED to open signups.")
    q.guild_id, q.channel_id = guild_id, channel_id
    q.signup_message_id, q.thread_id = message_id, thread_id
    q.open_signups()
    await quests_repo.upsert(q)
    return q
