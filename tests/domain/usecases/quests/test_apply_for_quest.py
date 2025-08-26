import pytest
from app.domain.models.UserModel import User, Role
from app.domain.models.quest.QuestModel import Quest, SignupStatus
from app.domain.usecases.ports import ForbiddenError, InvalidOperationError
from app.domain.usecases.quests.apply_for_quest import apply_for_quest, ApplyForQuestInput

pytestmark = pytest.mark.asyncio


class InMemoryUsersRepo:
    def __init__(self, users=None):
        self.users = dict(users or {})
        self.get_calls = []
        self.upsert_calls = []

    async def get(self, user_id: str) -> User:
        self.get_calls.append(user_id)
        return self.users[user_id]

    async def upsert(self, user: User) -> None:
        self.upsert_calls.append(user.user_id)
        self.users[user.user_id] = user


class InMemoryQuestsRepo:
    def __init__(self, quests=None):
        self.store = dict(quests or {})
        self.upsert_calls = []

    async def get(self, quest_id: str) -> Quest:
        return self.store[quest_id]

    async def upsert(self, quest: Quest) -> None:
        self.upsert_calls.append(quest.quest_id)
        self.store[quest.quest_id] = quest


async def test_apply_happy_path_adds_signup_and_increments_user_counter():
    u = User(user_id="u1"); u.enable_player()
    q = Quest(quest_id="q1", name="Moon Market", dm_id="u_dm"); q.open_signups()

    users = InMemoryUsersRepo({"u1": u})
    quests = InMemoryQuestsRepo({"q1": q})

    data = ApplyForQuestInput(quest_id="q1", user_id="u1", character_id="c1", note="can play late")
    updated = await apply_for_quest(users, quests, data)

    assert len(updated.signups) == 1
    s = updated.signups[0]
    assert (s.user_id, s.character_id, s.status) == ("u1", "c1", SignupStatus.APPLIED)
    assert users.users["u1"].player.quests_applied == 1
    assert quests.upsert_calls == ["q1"] and users.upsert_calls == ["u1"]


async def test_apply_forbidden_when_user_not_player():
    u = User(user_id="u2")  # no PLAYER role
    q = Quest(quest_id="q2", name="Lab", dm_id="u_dm"); q.open_signups()
    users = InMemoryUsersRepo({"u2": u})
    quests = InMemoryQuestsRepo({"q2": q})

    with pytest.raises(ForbiddenError):
        await apply_for_quest(users, quests, ApplyForQuestInput(quest_id="q2", user_id="u2", character_id="c1"))


async def test_apply_fails_when_signups_closed():
    u = User(user_id="u3"); u.enable_player()
    q = Quest(quest_id="q3", name="Lab", dm_id="u_dm")  # still DRAFT
    users = InMemoryUsersRepo({"u3": u})
    quests = InMemoryQuestsRepo({"q3": q})

    with pytest.raises(InvalidOperationError):
        await apply_for_quest(users, quests, ApplyForQuestInput(quest_id="q3", user_id="u3", character_id="c1"))


async def test_apply_fails_on_duplicate_application():
    u = User(user_id="u4"); u.enable_player()
    q = Quest(quest_id="q4", name="Lab", dm_id="u_dm"); q.open_signups()
    # Pre-seed one application for (u4, c1)
    q.add_signup("u4", "c1")

    users = InMemoryUsersRepo({"u4": u})
    quests = InMemoryQuestsRepo({"q4": q})

    with pytest.raises(InvalidOperationError):
        await apply_for_quest(users, quests, ApplyForQuestInput(quest_id="q4", user_id="u4", character_id="c1"))
