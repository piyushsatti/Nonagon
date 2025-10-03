from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ..services.user_provisioning import SyncStats, UserProvisioningService


class UserProvisioningCog(commands.Cog):
    """Ensures Discord guild members are synchronised with domain users."""

    def __init__(self, *, service: UserProvisioningService) -> None:
        """Persist the provisioning service used to mirror guild members."""
        self._service = service
        self._log = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Synchronise known guilds once the bot is ready."""
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
        """Provision a domain user when a real member joins the guild."""
        if member.bot:
            return
        await self._service.ensure_member_user(member)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Sync every member when the bot is added to a new guild."""
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
        """Return provisioning stats after reconciling guild membership."""
        available = getattr(guild, "available", True)
        if not available:
            return SyncStats(processed=0, created=0)
        return await self._service.sync_guild_members(guild)
