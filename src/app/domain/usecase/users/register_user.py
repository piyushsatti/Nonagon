from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.domain.models.user.UserModel import Role, User
from app.domain.usecase._shared import ensure_distinct, parse_user_id
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class RegisterUser:
    users_repo: UsersRepo

    async def execute(
        self,
        *,
        discord_id: str | None = None,
        dm_channel_id: str | None = None,
        joined_at: datetime | None = None,
        roles: Iterable[Role | str] | None = None,
    ) -> User:
        raw_id = await self.users_repo.next_id()
        user_id = parse_user_id(raw_id)

        normalised_roles: list[Role] | None = None
        if roles is not None:
            normalised_roles = [Role(role) for role in roles]
            normalised_roles = ensure_distinct(normalised_roles)

        if normalised_roles is not None:
            user = User(
                user_id=user_id,
                discord_id=discord_id,
                dm_channel_id=dm_channel_id,
                joined_at=joined_at,
                roles=normalised_roles,
            )
        else:
            user = User(
                user_id=user_id,
                discord_id=discord_id,
                dm_channel_id=dm_channel_id,
                joined_at=joined_at,
            )
        user.validate_user()
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class ImportUser:
    users_repo: UsersRepo

    async def execute(self, user: User) -> User:
        user.validate_user()
        await self.users_repo.upsert(user)
        return user
