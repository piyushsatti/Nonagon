from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import discord

from app.domain.models.user.UserModel import Role, User
from app.domain.usecase._shared import parse_user_id
from app.domain.usecase.ports import UsersRepo
from app.infra.ids.service import IdService


@dataclass(frozen=True, slots=True)
class ProvisionResult:
    user: User
    created: bool


@dataclass(frozen=True, slots=True)
class SyncStats:
    processed: int
    created: int


class UserProvisioningService:
    """Ensures every Discord guild member has a corresponding ``User`` record."""

    def __init__(
        self,
        *,
        users_repo: UsersRepo,
        id_service: IdService,
        logger: logging.Logger | None = None,
    ) -> None:
        self._users_repo = users_repo
        self._id_service = id_service
        self._log = logger or logging.getLogger(__name__)

    async def ensure_member_user(self, member: discord.Member) -> ProvisionResult:
        """Create a ``User`` record for ``member`` if one does not already exist."""

        return await self.ensure_member_record(
            discord_id=str(member.id),
            joined_at=member.joined_at,
            guild_id=member.guild.id if member.guild else None,
            is_bot=member.bot,
        )

    async def ensure_member_record(
        self,
        *,
        discord_id: str,
        joined_at: datetime | None,
        guild_id: int | str | None = None,
        is_bot: bool = False,
    ) -> ProvisionResult:
        if is_bot:
            self._log.debug(
                "Skipping bot member for provisioning",
                extra={"discord_id": discord_id},
            )
            raise ValueError("Bots are not provisioned")

        existing = await self._users_repo.get_by_discord_id(discord_id)
        if existing is not None:
            return ProvisionResult(user=existing, created=False)

        user_id = await self._id_service.ensure_user_id(discord_id)
        user = User(
            user_id=parse_user_id(user_id),
            discord_id=discord_id,
            joined_at=joined_at,
            roles=[Role.MEMBER],
        )
        user.validate_user()
        await self._users_repo.upsert(user)
        self._log.info(
            "Provisioned member",
            extra={
                "discord_id": discord_id,
                "user_id": str(user.user_id),
                "guild_id": guild_id,
            },
        )
        return ProvisionResult(user=user, created=True)

    async def sync_guild_members(self, guild: discord.Guild) -> SyncStats:
        processed = 0
        created = 0
        for member in guild.members:
            if member.bot:
                continue
            processed += 1
            result = await self.ensure_member_user(member)
            if result.created:
                created += 1
        return SyncStats(processed=processed, created=created)

    async def sync_members_payload(
        self,
        *,
        guild_id: int | str,
        members: Iterable[dict[str, object]],
    ) -> SyncStats:
        processed = 0
        created = 0
        for payload in members:
            raw_id = payload.get("discord_id")
            if raw_id is None:
                continue
            discord_id = str(raw_id).strip()
            if not discord_id:
                continue
            if payload.get("is_bot"):
                self._log.debug(
                    "Skipping bot member for provisioning",
                    extra={"discord_id": discord_id, "guild_id": guild_id},
                )
                continue
            processed += 1
            joined_at = payload.get("joined_at")
            joined_at_value: datetime | None
            if isinstance(joined_at, str):
                try:
                    joined_at_value = datetime.fromisoformat(joined_at)
                except ValueError:
                    self._log.warning(
                        "Invalid joined_at timestamp during sync",
                        extra={
                            "discord_id": discord_id,
                            "guild_id": guild_id,
                            "joined_at": joined_at,
                        },
                    )
                    joined_at_value = None
            elif isinstance(joined_at, datetime):
                joined_at_value = joined_at
            else:
                joined_at_value = None
            result = await self.ensure_member_record(
                discord_id=discord_id,
                joined_at=joined_at_value,
                guild_id=guild_id,
                is_bot=False,
            )
            if result.created:
                created += 1
        return SyncStats(processed=processed, created=created)
