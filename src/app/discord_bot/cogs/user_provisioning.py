from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ..services.user_provisioning import SyncStats, UserProvisioningService


class UserProvisioningCog(commands.Cog):
    """Ensures Discord guild members are synchronised with domain users."""

    def __init__(self, *, service: UserProvisioningService) -> None:
        self._service = service
        self._log = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        bot = getattr(self, "bot", None)
        if bot is None:
            return
        if not bot.guilds:
            return
        for guild in list(bot.guilds):
            stats = await self._sync_guild(guild)
            if stats.created:
                self._log.info(
                    "Provisioned users from startup sync",
                    extra={
                        "guild_id": guild.id,
                        "created": stats.created,
                        "processed": stats.processed,
                    },
                )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        await self._service.ensure_member_user(member)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        stats = await self._sync_guild(guild)
        if stats.created:
            self._log.info(
                "Provisioned users for new guild",
                extra={
                    "guild_id": guild.id,
                    "created": stats.created,
                    "processed": stats.processed,
                },
            )

    async def _sync_guild(self, guild: discord.Guild) -> SyncStats:
        available = getattr(guild, "available", True)
        if not available:
            return SyncStats(processed=0, created=0)
        return await self._service.sync_guild_members(guild)
