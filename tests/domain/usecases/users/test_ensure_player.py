import pytest

from app.domain.models.UserModel import User, Role, PlayerProfile
from app.domain.usecases.users.ensure_player import ensure_player

pytestmark = pytest.mark.asyncio


class InMemoryUsersRepo:
    """Minimal async repo stub for juniors to read easily."""
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


async def test_ensure_player_adds_role_profile_and_upserts():
    u = User(user_id="u1")                   # starts as MEMBER only
    repo = InMemoryUsersRepo({"u1": u})

    result = await ensure_player(repo, "u1")

    # fetched & upserted once
    assert repo.get_calls == ["u1"]
    assert repo.upsert_calls == ["u1"]

    # role + profile enabled
    assert Role.PLAYER in result.roles
    assert isinstance(result.player, PlayerProfile)

    # idempotent: calling again doesn't duplicate role or replace profile
    profile_id_before = id(result.player)
    result2 = await ensure_player(repo, "u1")
    assert result2.roles.count(Role.PLAYER) == 1
    assert id(result2.player) == profile_id_before


async def test_ensure_player_returns_same_updated_instance_from_repo():
    u = User(user_id="u2")
    repo = InMemoryUsersRepo({"u2": u})

    updated = await ensure_player(repo, "u2")

    # the object in the repo is the updated one
    assert repo.users["u2"].player is not None
    assert updated is repo.users["u2"]  # same object identity is fine here
