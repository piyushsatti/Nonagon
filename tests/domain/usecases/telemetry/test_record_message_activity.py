import pytest
from datetime import datetime, timezone

from app.domain.models.UserModel import User
from app.domain.usecases.telemetry.record_message_activity import record_message_activity

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


async def test_increments_total_and_sets_last_active_utc():
    u = User(user_id="u1")
    repo = InMemoryUsersRepo({"u1": u})

    await record_message_activity(repo, "u1")

    # fetched + upserted once
    assert repo.get_calls == ["u1"]
    assert repo.upsert_calls == ["u1"]

    # counters
    assert repo.users["u1"].messages_count_total == 1

    # last_active_at should be tz-aware UTC
    la = repo.users["u1"].last_active_at
    assert isinstance(la, datetime) and la.tzinfo is not None and la.tzinfo.utcoffset(la) == timezone.utc.utcoffset(la)


async def test_category_counter_only_when_category_present():
    u = User(user_id="u2")
    repo = InMemoryUsersRepo({"u2": u})

    # with a category
    await record_message_activity(repo, "u2", category_id=123)
    # without a category
    await record_message_activity(repo, "u2")

    assert repo.users["u2"].messages_count_total == 2
    assert repo.users["u2"].messages_count_by_category.get(123) == 1
