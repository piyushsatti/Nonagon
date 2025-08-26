from dataclasses import dataclass
from typing import List, Tuple, Optional
from app.domain.usecases.ports import ForbiddenError, InvalidOperationError
from app.domain.models.UserModel import Role, UserId, CharacterId
from app.domain.models.quest.QuestModel import Quest, QuestStatus

@dataclass
class SelectRosterInput:
    quest_id: str
    dm_id: UserId
    selected: List[Tuple[UserId, CharacterId]]
    waitlisted: Optional[List[Tuple[UserId, CharacterId]]] = None

async def select_roster(users_repo, quests_repo, data: SelectRosterInput) -> Quest:
    dm = await users_repo.get(data.dm_id)
    if Role.REFEREE not in dm.roles:
        raise ForbiddenError("Only referees can select rosters.")

    q = await quests_repo.get(data.quest_id)
    if q.dm_id != data.dm_id:
        raise ForbiddenError("Only this quest's DM can select its roster.")
    if q.status != QuestStatus.SIGNUP_OPEN:
        raise InvalidOperationError("Quest must be SIGNUP_OPEN.")

    q.select_roster(selected=data.selected, waitlisted=data.waitlisted or [])

    # update acceptance counters
    for uid, _ in data.selected:
        u = await users_repo.get(uid)
        if u.player:
            u.player.quests_accepted += 1
        await users_repo.upsert(u)

    await quests_repo.upsert(q)
    return q
