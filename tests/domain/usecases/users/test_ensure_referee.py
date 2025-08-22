import pytest

from app.domain.models.UserModel import User, Role, RefereeProfile
from app.domain.usecases.users.ensure_referee import ensure_referee

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


async def test_ensure_referee_adds_role_profile_and_upserts():
    u = User(user_id="u3")
    repo = InMemoryUsersRepo({"u3": u})

    result = await ensure_referee(repo, "u3")

    # fetched & upserted once
    assert repo.get_calls == ["u3"]
    assert repo.upsert_calls == ["u3"]

    # role + profile enabled
    assert Role.REFEREE in result.roles
    assert isinstance(result.referee, RefereeProfile)

    # idempotent on second call
    profile_id_before = id(result.referee)
    result2 = await ensure_referee(repo, "u3")
    assert result2.roles.count(Role.REFEREE) == 1
    assert id(result2.referee) == profile_id_before


async def test_ensure_referee_returns_same_updated_instance_from_repo():
    u = User(user_id="u4")
    repo = InMemoryUsersRepo({"u4": u})

    updated = await ensure_referee(repo, "u4")

    assert repo.users["u4"].referee is not None
    assert updated is repo.users["u4"]
