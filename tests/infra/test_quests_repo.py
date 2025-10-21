from __future__ import annotations

import types

import pytest

from app.domain.models.EntityIDModel import QuestID, UserID
from app.domain.models.QuestModel import Quest
from app.infra.mongo import quests_repo


class _FakeCollection:
    def __init__(self):
        self.last_replace_one = None

    async def replace_one(self, filt, doc, upsert=False):
        self.last_replace_one = (filt, doc, upsert)
        return types.SimpleNamespace()


@pytest.mark.asyncio
async def test_quests_repo_upsert_scopes_by_guild(monkeypatch):
    repo = quests_repo.QuestsRepoMongo()
    fake = _FakeCollection()
    monkeypatch.setattr(quests_repo, "COLL", lambda guild_id: fake)

    quest = Quest(
        quest_id=QuestID(5),
        guild_id=789,
        referee_id=UserID(2),
        channel_id="123",
        message_id="456",
        raw="Quest details",
    )

    await repo.upsert(789, quest)

    filt, doc, upsert = fake.last_replace_one
    assert filt == {"guild_id": 789, "quest_id.value": str(quest.quest_id)}
    assert doc["guild_id"] == 789
    assert upsert is True
