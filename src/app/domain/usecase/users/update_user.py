from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.models.EntityIDModel import UserID
from app.domain.models.user.UserModel import User
from app.domain.usecase._shared import ensure_user
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class UpdateUserProfile:
    users_repo: UsersRepo

    async def execute(
        self,
        user_id: UserID | str,
        *,
        discord_id: str | None = None,
        dm_channel_id: str | None = None,
        joined_at: datetime | None = None,
        last_active_at: datetime | None = None,
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)

        if discord_id is not None:
            user.discord_id = discord_id
        if dm_channel_id is not None:
            user.update_dm_channel(dm_channel_id)
        if joined_at is not None:
            user.update_joined_at(joined_at, override=True)
        if last_active_at is not None:
            user.update_last_active(last_active_at)

        user.validate_user()
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class UpdateDmChannel:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str, dm_channel_id: str) -> User:
        user = await ensure_user(self.users_repo, user_id)
        user.update_dm_channel(dm_channel_id)
        await self.users_repo.upsert(user)
        return user
