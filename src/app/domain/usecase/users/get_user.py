from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import UserID
from app.domain.models.user.UserModel import User
from app.domain.usecase._shared import ensure_user
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class GetUser:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str) -> User:
        return await ensure_user(self.users_repo, user_id)


@dataclass(slots=True)
class GetUserByDiscord:
    users_repo: UsersRepo

    async def execute(self, discord_id: str) -> User:
        user = await self.users_repo.get_by_discord_id(discord_id)
        if user is None:
            raise ValueError(f"User with Discord ID does not exist: {discord_id}")
        return user
