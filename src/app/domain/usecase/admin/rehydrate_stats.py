from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.domain.models.EntityIDModel import UserID
from app.domain.models.user.UserModel import InteractionStats, User
from app.domain.usecase._shared import ensure_user, parse_user_id
from app.domain.usecase.ports import UsersRepo


@dataclass(slots=True)
class RebuildCollaborationStats:
    users_repo: UsersRepo

    async def execute(
        self,
        user_id: UserID | str,
        *,
        collaborations: Mapping[UserID | str, tuple[int, float]],
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)
        if user.referee is None:
            user.enable_referee()
        rebuilt: dict[UserID, InteractionStats] = {}
        for partner, legacy in collaborations.items():
            stats = InteractionStats()
            stats.merge_legacy(legacy)
            rebuilt[parse_user_id(partner)] = stats
        user.get_referee().collabed_with = rebuilt
        user.validate_user()
        await self.users_repo.upsert(user)
        return user


@dataclass(slots=True)
class RebuildHostedForCounts:
    users_repo: UsersRepo

    async def execute(
        self,
        user_id: UserID | str,
        *,
        hosted_for: Mapping[UserID | str, int],
    ) -> User:
        user = await ensure_user(self.users_repo, user_id)
        if user.referee is None:
            user.enable_referee()
        rebuilt = {
            parse_user_id(partner): int(count)
            for partner, count in hosted_for.items()
            if int(count) >= 0
        }
        user.get_referee().hosted_for = rebuilt
        user.validate_user()
        await self.users_repo.upsert(user)
        return user
