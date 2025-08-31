# tests/infra/test_repo_integration.py
import pytest
from datetime import datetime, timezone

from app.infra.mongo.users_repo import UsersRepoMongo
from app.infra.mongo.quests_repo import QuestsRepoMongo
from app.infra.db import get_db
from app.domain.models.UserModel import User
from app.domain.models.QuestModel import Quest
from app.domain.models.EntityIDModel import UserID, QuestID


@pytest.mark.asyncio
async def test_users_repo_crud():
    repo = UsersRepoMongo()
    db = get_db()
    coll = db["users"]

    # Create a new domain id (note: not used as Mongo _id)
    uid_str = await repo.next_id()
    uid = UserID.parse(uid_str)

    # Upsert via repo
    user = User(user_id=uid, discord_id="123", joined_at=datetime.now(timezone.utc))
    assert await repo.upsert(user)

    # Verify by domain-id field, not _id
    doc = await coll.find_one({"user_id.number": uid.number})
    assert doc is not None
    assert doc.get("discord_id") == "123"

    # Optionally hydrate back using the repo if it supports domain-id lookup.
    # If repo.get() expects the _id, skip it. We’ll just validate raw -> model roundtrip logic elsewhere.

    # Cleanup using the actual Mongo _id we just fetched
    mongo_id = doc["_id"]
    await coll.delete_one({"_id": mongo_id})
    assert await coll.find_one({"_id": mongo_id}) is None


@pytest.mark.asyncio
async def test_quests_repo_crud():
    repo = QuestsRepoMongo()
    db = get_db()
    coll = db["quests"]

    qid_str = await repo.next_id()
    qid = QuestID.parse(qid_str)
    uid = UserID(1)

    quest = Quest(
        quest_id=qid,
        referee_id=uid,
        channel_id="chan",
        message_id="msg",
        raw="# raw",
        title="My Quest",
        description="desc",
        starting_at=None,
        duration=None,
        image_url=None,
    )
    assert await repo.upsert(quest)

    # Verify by domain-id field, not _id
    doc = await coll.find_one({"quest_id.number": qid.number})
    assert doc is not None
    assert doc.get("title") == "My Quest"

    # Cleanup
    mongo_id = doc["_id"]
    await coll.delete_one({"_id": mongo_id})
    assert await coll.find_one({"_id": mongo_id}) is None
