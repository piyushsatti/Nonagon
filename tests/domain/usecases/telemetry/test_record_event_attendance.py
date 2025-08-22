import pytest
from datetime import datetime, timezone

from app.domain.models.UserModel import User
from app.domain.usecases.telemetry.record_event_attendance import record_event_attendance

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


async def test_increments_each_user_and_sets_last_active_utc():
    u1 = User(user_id="u1")
    u2 = User(user_id="u2")
    repo = InMemoryUsersRepo({"u1": u1, "u2": u2})

    await record_event_attendance(repo, ["u1", "u2"])

    # each user fetched & upserted
    assert repo.get_calls == ["u1", "u2"]
    assert repo.upsert_calls == ["u1", "u2"]

    # counters incremented
    assert repo.users["u1"].events_attended == 1
    assert repo.users["u2"].events_attended == 1

    # last_active_at is tz-aware UTC
    for uid in ("u1", "u2"):
        la = repo.users[uid].last_active_at
        assert isinstance(la, datetime) and la.tzinfo is not None and la.tzinfo.utcoffset(la) == timezone.utc.utcoffset(la)
