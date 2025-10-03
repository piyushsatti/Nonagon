from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import discord

from app.domain.models.user.UserModel import User
from app.domain.usecase.ports import UsersRepo
from app.domain.usecase.users.manage_roles import (
    DemotePlayerToMember,
    PromotePlayerToReferee,
    PromoteUserToPlayer,
    RevokeRefereeRole,
)

from .user_provisioning import UserProvisioningService


class PlayerRoleStatus(Enum):
    PROMOTED = auto()
    ALREADY = auto()
    DEMOTED = auto()
    NOT_PLAYER = auto()
    BLOCKED_REFEREE = auto()


class RefereeRoleStatus(Enum):
    PROMOTED = auto()
    ALREADY = auto()
    DEMOTED = auto()
    NOT_REFEREE = auto()


@dataclass(slots=True)
class PlayerRoleResult:
    user: User
    status: PlayerRoleStatus


@dataclass(slots=True)
class RefereeRoleResult:
    user: User
    status: RefereeRoleStatus


class RoleManagementService:
    def __init__(
        self,
        *,
        users_repo: UsersRepo,
        user_provisioning: UserProvisioningService,
    ) -> None:
        self._users_repo = users_repo
        self._user_provisioning = user_provisioning

    async def grant_player(self, member: discord.Member) -> PlayerRoleResult:
        provision = await self._user_provisioning.ensure_member_user(member)
        user = provision.user
        if user.is_player:
            return PlayerRoleResult(user=user, status=PlayerRoleStatus.ALREADY)
        updated = await PromoteUserToPlayer(self._users_repo).execute(user.user_id)
        return PlayerRoleResult(user=updated, status=PlayerRoleStatus.PROMOTED)

    async def revoke_player(self, member: discord.Member) -> PlayerRoleResult:
        provision = await self._user_provisioning.ensure_member_user(member)
        user = provision.user
        if not user.is_player:
            return PlayerRoleResult(user=user, status=PlayerRoleStatus.NOT_PLAYER)
        if user.is_referee:
            return PlayerRoleResult(user=user, status=PlayerRoleStatus.BLOCKED_REFEREE)
        updated = await DemotePlayerToMember(self._users_repo).execute(user.user_id)
        return PlayerRoleResult(user=updated, status=PlayerRoleStatus.DEMOTED)

    async def grant_referee(self, member: discord.Member) -> RefereeRoleResult:
        provision = await self._user_provisioning.ensure_member_user(member)
        user = provision.user
        if user.is_referee:
            return RefereeRoleResult(user=user, status=RefereeRoleStatus.ALREADY)
        updated = await PromotePlayerToReferee(self._users_repo).execute(user.user_id)
        return RefereeRoleResult(user=updated, status=RefereeRoleStatus.PROMOTED)

    async def revoke_referee(self, member: discord.Member) -> RefereeRoleResult:
        provision = await self._user_provisioning.ensure_member_user(member)
        user = provision.user
        if not user.is_referee:
            return RefereeRoleResult(user=user, status=RefereeRoleStatus.NOT_REFEREE)
        updated = await RevokeRefereeRole(self._users_repo).execute(user.user_id)
        return RefereeRoleResult(user=updated, status=RefereeRoleStatus.DEMOTED)
