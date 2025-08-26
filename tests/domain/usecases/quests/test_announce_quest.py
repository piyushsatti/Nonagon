import pytest
from app.domain.models.quest.QuestModel import Quest, QuestStatus
from app.domain.usecases.ports import InvalidOperationError
from app.domain.usecases.quests.announce_quest import announce_quest

pytestmark = pytest.mark.asyncio


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


async def test_announce_from_draft_sets_linkage_and_opens_signups():
    q = Quest(quest_id="q1", name="Gilded Labyrinth", dm_id="u_dm")
    repo = InMemoryQuestsRepo({"q1": q})

    updated = await announce_quest(repo, "q1", guild_id=1, channel_id=2, message_id=3, thread_id=4)

    assert updated.status is QuestStatus.SIGNUP_OPEN
    assert updated.guild_id == 1 and updated.channel_id == 2
    assert updated.signup_message_id == 3 and updated.thread_id == 4
    assert repo.upsert_calls == ["q1"]


async def test_announce_fails_if_status_not_draft_or_announced():
    q = Quest(quest_id="q2", name="Ivory Gate", dm_id="u_dm")
    q.open_signups()  # now SIGNUP_OPEN
    repo = InMemoryQuestsRepo({"q2": q})

    with pytest.raises(InvalidOperationError):
        await announce_quest(repo, "q2", guild_id=1, channel_id=2, message_id=3)
