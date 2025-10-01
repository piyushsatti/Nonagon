from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.models.EntityIDModel import UserID
from app.domain.models.user.UserModel import User
from app.domain.usecase._shared import ensure_user
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class UpdateLastActive:
    users_repo: UsersRepo

    async def execute(
        self, user_id: UserID | str, *, active_at: datetime | None = None
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.update_last_active(active_at)
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class UpdatePlayerLastActive:
    users_repo: UsersRepo

    async def execute(
        self, user_id: UserID | str, *, active_at: datetime | None = None
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)
        if not user.is_player:
            raise ValueError(f"User {user.user_id} is not a player")
        user.update_last_active(active_at)
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class UpdateRefereeLastActive:
    users_repo: UsersRepo

    async def execute(
        self, user_id: UserID | str, *, active_at: datetime | None = None
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)
        if not user.is_referee:
            raise ValueError(f"User {user.user_id} is not a referee")
        user.update_last_active(active_at)
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class RecordUserInteraction:
    users_repo: UsersRepo

    async def execute(
        self,
        user_id: UserID | str,
        *,
        messages: int = 0,
        reactions_given: int = 0,
        reactions_received: int = 0,
        voice_seconds: int = 0,
        at: datetime | None = None,
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.record_interaction(
            messages=messages,
            reactions_given=reactions_given,
            reactions_received=reactions_received,
            voice_seconds=voice_seconds,
            at=at,
        )
        user.validate_user()
        await self.users_repo.upsert(user)
        return user
