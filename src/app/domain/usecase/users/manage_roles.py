from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import UserID
from app.domain.models.user.UserModel import User
from app.domain.usecase._shared import ensure_user
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class PromoteUserToPlayer:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.enable_player()
        user.validate_user()
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class DemotePlayerToMember:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.disable_player()
        user.validate_user()
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class PromotePlayerToReferee:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.enable_referee()
        user.validate_user()
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class RevokeRefereeRole:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.disable_referee()
        user.validate_user()
        await self.users_repo.upsert(user)
        return user
