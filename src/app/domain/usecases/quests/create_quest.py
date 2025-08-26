from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from app.domain.usecases.ports import ForbiddenError
from app.domain.models.UserModel import Role, UserId
from app.domain.models.quest.QuestModel import Quest

@dataclass
class CreateQuestInput:
    name: str
    dm_id: UserId
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_players: int = 5
    min_players: int = 3
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    region: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None

async def create_quest(users_repo, quests_repo, data: CreateQuestInput) -> Quest:
    dm = await users_repo.get(data.dm_id)
    if Role.REFEREE not in dm.roles:
        raise ForbiddenError("Only referees can create quests.")

    quest_id = await quests_repo.next_id()
    quest = Quest(
        quest_id=quest_id,
        name=data.name,
        dm_id=data.dm_id,
        description=data.description,
        scheduled_at=data.scheduled_at,
        max_players=data.max_players,
        min_players=data.min_players,
        category=data.category,
        tags=data.tags or [],
        region=data.region,
        level_min=data.level_min,
        level_max=data.level_max,
    )
    await quests_repo.upsert(quest)
    return quest
