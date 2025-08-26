import pytest
from app.domain.models.UserModel import User
from app.domain.models.quest.QuestModel import Quest, QuestStatus, SignupStatus
from app.domain.usecases.ports import ForbiddenError, InvalidOperationError
from app.domain.usecases.quests.select_roster import select_roster, SelectRosterInput

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
        self.get_calls = []
        self.upsert_calls = []

    async def get(self, quest_id: str) -> Quest:
        self.get_calls.append(quest_id)
        return self.store[quest_id]

    async def upsert(self, quest: Quest) -> None:
        self.upsert_calls.append(quest.quest_id)
        self.store[quest.quest_id] = quest


async def test_select_roster_happy_path_updates_status_lists_and_player_counts():
    dm = User(user_id="u_dm"); dm.enable_referee()
    p1 = User(user_id="u1"); p1.enable_player()
    p2 = User(user_id="u2"); p2.enable_player()
    p3 = User(user_id="u3"); p3.enable_player()

    q = Quest(quest_id="q1", name="Gilded Labyrinth", dm_id="u_dm", max_players=2)
    q.open_signups()
    # everyone applied with their characters
    q.add_signup("u1", "c1"); q.add_signup("u2", "c2"); q.add_signup("u3", "c3")

    users = InMemoryUsersRepo({"u_dm": dm, "u1": p1, "u2": p2, "u3": p3})
    quests = InMemoryQuestsRepo({"q1": q})

    data = SelectRosterInput(quest_id="q1", dm_id="u_dm",
                             selected=[("u1", "c1"), ("u2", "c2")],
                             waitlisted=[("u3", "c3")])

    updated = await select_roster(users, quests, data)

    # quest status and lists
    assert updated.status is QuestStatus.ROSTER_SELECTED
    assert len(updated.roster) == 2 and len(updated.waitlist) == 1

    # signup statuses mirrored
    by_key = {(s.user_id, s.character_id): s for s in updated.signups}
    assert by_key[("u1", "c1")].status is SignupStatus.SELECTED
    assert by_key[("u2", "c2")].status is SignupStatus.SELECTED
    assert by_key[("u3", "c3")].status is SignupStatus.WAITLISTED

    # player acceptance counters incremented
    assert users.users["u1"].player.quests_accepted == 1
    assert users.users["u2"].player.quests_accepted == 1
    assert users.users["u3"].player.quests_accepted == 0  # waitlisted not accepted

    # persistence happened
    assert quests.upsert_calls == ["q1"]
    # u1 and u2 were upserted, and potentially u_dm fetched only
    assert set(users.upsert_calls) == {"u1", "u2"}


async def test_select_roster_forbidden_if_caller_not_referee():
    not_dm = User(user_id="u_x")  # no referee role
    q = Quest(quest_id="q2", name="Ivory", dm_id="u_x"); q.open_signups()

    users = InMemoryUsersRepo({"u_x": not_dm})
    quests = InMemoryQuestsRepo({"q2": q})

    with pytest.raises(ForbiddenError):
        await select_roster(users, quests, SelectRosterInput(quest_id="q2", dm_id="u_x", selected=[]))


async def test_select_roster_forbidden_if_not_quest_owner():
    dm1 = User(user_id="u1"); dm1.enable_referee()
    dm2 = User(user_id="u2"); dm2.enable_referee()

    q = Quest(quest_id="q3", name="Gate", dm_id="u1"); q.open_signups()

    users = InMemoryUsersRepo({"u1": dm1, "u2": dm2})
    quests = InMemoryQuestsRepo({"q3": q})

    with pytest.raises(ForbiddenError):
        await select_roster(users, quests, SelectRosterInput(quest_id="q3", dm_id="u2", selected=[]))


async def test_select_roster_invalid_if_status_not_signup_open():
    dm = User(user_id="u_dm"); dm.enable_referee()
    q = Quest(quest_id="q4", name="Gate", dm_id="u_dm")  # DRAFT

    users = InMemoryUsersRepo({"u_dm": dm})
    quests = InMemoryQuestsRepo({"q4": q})

    with pytest.raises(InvalidOperationError):
        await select_roster(users, quests, SelectRosterInput(quest_id="q4", dm_id="u_dm", selected=[]))
