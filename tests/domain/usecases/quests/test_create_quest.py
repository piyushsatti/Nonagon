import pytest
from app.domain.models.UserModel import User, Role
from app.domain.models.QuestModel import Quest
from app.domain.usecases.ports import ForbiddenError
from app.domain.usecases.quests.create_quest import create_quest, CreateQuestInput

pytestmark = pytest.mark.asyncio


class InMemoryUsersRepo:
    def __init__(self, users=None):
        self.users = dict(users or {})
        self.get_calls = []

    async def get(self, user_id: str) -> User:
        self.get_calls.append(user_id)
        return self.users[user_id]

    async def upsert(self, user: User) -> None:
        self.users[user.user_id] = user


class InMemoryQuestsRepo:
    def __init__(self):
        self.seq = 0
        self.next_id_calls = 0
        self.upsert_calls = []
        self.store = {}

    async def next_id(self) -> str:
        self.next_id_calls += 1
        self.seq += 1
        return f"q{self.seq}"

    async def upsert(self, quest: Quest) -> None:
        self.upsert_calls.append(quest.quest_id)
        self.store[quest.quest_id] = quest

    async def get(self, quest_id: str) -> Quest:
        return self.store[quest_id]


async def test_create_quest_happy_path_persists_and_returns():
    dm = User(user_id="u_dm"); dm.enable_referee()
    users = InMemoryUsersRepo({"u_dm": dm})
    quests = InMemoryQuestsRepo()

    data = CreateQuestInput(name="Moon Market", dm_id="u_dm", max_players=4, min_players=2, tags=["city"])
    q = await create_quest(users, quests, data)

    assert quests.next_id_calls == 1
    assert quests.upsert_calls == [q.quest_id]
    assert q.name == "Moon Market"
    assert q.dm_id == "u_dm"
    assert q.max_players == 4 and q.min_players == 2
    assert q.tags == ["city"]


async def test_create_quest_forbidden_if_user_not_referee():
    dm = User(user_id="u1")  # no REFEREE role
    users = InMemoryUsersRepo({"u1": dm})
    quests = InMemoryQuestsRepo()

    with pytest.raises(ForbiddenError):
        await create_quest(users, quests, CreateQuestInput(name="Nope", dm_id="u1"))
