from dataclasses import dataclass
from typing import Optional
from app.domain.usecases.ports import ForbiddenError, InvalidOperationError
from app.domain.models.UserModel import Role, UserId, CharacterId
from app.domain.models.quest.QuestModel import Quest

@dataclass
class ApplyForQuestInput:
    quest_id: str
    user_id: UserId
    character_id: CharacterId
    note: Optional[str] = None

async def apply_for_quest(users_repo, quests_repo, data: ApplyForQuestInput) -> Quest:
    user = await users_repo.get(data.user_id)
    if Role.PLAYER not in user.roles:
        raise ForbiddenError("Only players can apply for quests.")

    quest = await quests_repo.get(data.quest_id)
    if not quest.is_signup_open():
        raise InvalidOperationError("Sign-ups are not open.")
    if any(s.user_id == data.user_id and s.character_id == data.character_id for s in quest.signups):
        raise InvalidOperationError("Already applied with this character.")

    quest.add_signup(user_id=data.user_id, character_id=data.character_id, note=data.note)
    if user.player:
        user.player.quests_applied += 1

    await quests_repo.upsert(quest)
    await users_repo.upsert(user)
    return quest
