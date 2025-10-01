from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import UserID
from app.domain.usecase._shared import parse_user_id
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class DeleteUser:
    users_repo: UsersRepo

    async def execute(self, user_id: UserID | str) -> None:
        raw = str(parse_user_id(user_id))
        if not await self.users_repo.exists(raw):
            raise ValueError(f"User ID does not exist: {user_id}")
        await self.users_repo.delete(raw)
