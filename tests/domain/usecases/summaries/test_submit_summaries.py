import pytest
from datetime import datetime

from app.domain.models.UserModel import User, Role, PlayerProfile, RefereeProfile
from app.domain.models.QuestModel import Quest
from app.domain.models.SummaryModel import SummaryKind

from app.domain.usecases.summaries.submit_summary import submit_summary, SubmitSummaryInput
from app.domain.usecases.ports import ForbiddenError

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
        self.quests = dict(quests or {})
        self.get_calls = []
        self.upsert_calls = []

    async def get(self, quest_id: str) -> Quest:
        self.get_calls.append(quest_id)
        return self.quests[quest_id]

    async def upsert(self, quest: Quest) -> None:
        self.upsert_calls.append(quest.quest_id)
        self.quests[quest.quest_id] = quest


class InMemorySummariesRepo:
    def __init__(self):
        self.summaries = {}
        self.seq = 0
        self.next_id_calls = 0
        self.upsert_calls = []

    async def next_id(self) -> str:
        self.next_id_calls += 1
        self.seq += 1
        return f"s{self.seq}"

    async def upsert(self, summary) -> None:
        self.upsert_calls.append(summary.summary_id)
        self.summaries[summary.summary_id] = summary


async def test_player_summary_happy_path_links_everything_and_updates_stats():
    # user is a PLAYER with a profile
    u = User(user_id="u1")
    u.enable_player()
    # quest exists
    q = Quest(quest_id="q1", name="Moon Market", dm_id="u_dm")

    users = InMemoryUsersRepo({"u1": u})
    quests = InMemoryQuestsRepo({"q1": q})
    sums = InMemorySummariesRepo()

    data = SubmitSummaryInput(
        quest_id="q1",
        author_user_id="u1",
        text="We bargained with fae merchants.",
        kind=SummaryKind.PLAYER,
    )

    summary = await submit_summary(users, quests, sums, data)

    # created one summary id and persisted all 3 resources
    assert sums.next_id_calls == 1
    assert sums.upsert_calls == [summary.summary_id]
    assert quests.upsert_calls == ["q1"]
    assert users.upsert_calls == ["u1"]

    # quest links the new summary id
    assert summary.summary_id in quests.quests["q1"].summary_ids

    # author stats updated
    assert summary.summary_id in users.users["u1"].player.quest_summaries_written
    assert isinstance(users.users["u1"].player.last_played_at, datetime)

    # visibility defaults for player summaries
    assert summary.is_private is False
    assert summary.audience_roles == []


async def test_dm_summary_happy_path_sets_private_and_updates_referee_stats():
    u = User(user_id="u2")
    u.enable_referee()
    q = Quest(quest_id="q2", name="Gilded Labyrinth", dm_id="u2")

    users = InMemoryUsersRepo({"u2": u})
    quests = InMemoryQuestsRepo({"q2": q})
    sums = InMemorySummariesRepo()

    data = SubmitSummaryInput(
        quest_id="q2",
        author_user_id="u2",
        text="Behind the screen notes.",
        kind=SummaryKind.DM,
    )

    summary = await submit_summary(users, quests, sums, data)

    # DM summaries default to private + restricted audience
    assert summary.is_private is True
    assert set(summary.audience_roles) == {"admin", "referee"}

    # quest linkage + referee profile updates
    assert summary.summary_id in quests.quests["q2"].summary_ids
    assert summary.summary_id in users.users["u2"].referee.dm_summaries_written
    assert isinstance(users.users["u2"].referee.last_dmed_at, datetime)


async def test_is_private_can_be_overridden():
    u = User(user_id="u3")
    u.enable_referee()
    q = Quest(quest_id="q3", name="Ivory Gate", dm_id="u3")

    users = InMemoryUsersRepo({"u3": u})
    quests = InMemoryQuestsRepo({"q3": q})
    sums = InMemorySummariesRepo()

    data = SubmitSummaryInput(
        quest_id="q3",
        author_user_id="u3",
        text="Sharing with players intentionally.",
        kind=SummaryKind.DM,
        is_private=False,  # override
    )

    summary = await submit_summary(users, quests, sums, data)
    assert summary.is_private is False   # overridden
    # audience_roles still the DM default set in the use case
    assert set(summary.audience_roles) == {"admin", "referee"}


async def test_forbidden_when_non_player_submits_player_summary():
    # user without PLAYER role
    u = User(user_id="u4")
    q = Quest(quest_id="q4", name="Starfall Ferry", dm_id="u_dm")

    users = InMemoryUsersRepo({"u4": u})
    quests = InMemoryQuestsRepo({"q4": q})
    sums = InMemorySummariesRepo()

    data = SubmitSummaryInput(
        quest_id="q4",
        author_user_id="u4",
        text="Trying to submit as player without role.",
        kind=SummaryKind.PLAYER,
    )

    with pytest.raises(ForbiddenError):
        await submit_summary(users, quests, sums, data)


async def test_forbidden_when_non_referee_submits_dm_summary():
    # user with only PLAYER role
    u = User(user_id="u5")
    u.enable_player()
    q = Quest(quest_id="q5", name="Saffron Road", dm_id="u_dm")

    users = InMemoryUsersRepo({"u5": u})
    quests = InMemoryQuestsRepo({"q5": q})
    sums = InMemorySummariesRepo()

    data = SubmitSummaryInput(
        quest_id="q5",
        author_user_id="u5",
        text="Trying DM summary without referee role.",
        kind=SummaryKind.DM,
    )

    with pytest.raises(ForbiddenError):
        await submit_summary(users, quests, sums, data)
