import pytest
from app.domain.models.quest.QuestModel import Quest, QuestStatus
from app.domain.usecases.ports import InvalidOperationError
from app.domain.usecases.quests.mark_completed import mark_completed

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


async def test_mark_completed_from_running_or_roster_selected_sets_flags_and_persists():
    # Case 1: from RUNNING
    q1 = Quest(quest_id="q1", name="Moon", dm_id="u"); q1.mark_running()
    repo1 = InMemoryQuestsRepo({"q1": q1})

    updated1 = await mark_completed(repo1, "q1")
    assert updated1.status is QuestStatus.COMPLETED
    assert updated1.summary_needed is True
    assert repo1.upsert_calls == ["q1"]

    # Case 2: from ROSTER_SELECTED
    q2 = Quest(quest_id="q2", name="Gate", dm_id="u"); q2.status = QuestStatus.ROSTER_SELECTED
    repo2 = InMemoryQuestsRepo({"q2": q2})

    updated2 = await mark_completed(repo2, "q2")
    assert updated2.status is QuestStatus.COMPLETED
    assert updated2.summary_needed is True


async def test_mark_completed_invalid_from_other_statuses():
    q = Quest(quest_id="q3", name="Lab", dm_id="u")  # DRAFT
    repo = InMemoryQuestsRepo({"q3": q})

    with pytest.raises(InvalidOperationError):
        await mark_completed(repo, "q3")
