from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.utils.logging import get_logger


logger = get_logger(__name__)

class AdminCommandsCog(commands.Cog):
    """Administrative slash commands for rapid iteration helpers."""

    admin = app_commands.Group(
        name="admin", description="Administrative utilities for Nonagon."
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Register the admin command group globally so guild sync retains it
        self.bot.tree.add_command(self.admin, override=True)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.admin.name, type=self.admin.type)

    # NOTE: Sync logic moved out of admin cog. Use owner diagnostics or extension manager to run syncs.

    @admin.command(
        name="sync",
        description="(disabled) Sync moved to owner diagnostics and extension manager.",
    )
    async def sync(self, interaction: discord.Interaction, all_guilds: Optional[bool] = False) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "The `/admin sync` command has been disabled. Bot owner can run `n!sync` (current guild) or `n!syncall` (all guilds).",
            ephemeral=True,
        )

    @commands.group(name="admin", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def admin_text_group(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "Available admin subcommands: (sync commands disabled). Use owner-only diagnostics for sync tasks.",
                delete_after=15,
            )

    @admin_text_group.command(name="sync")
    async def admin_text_sync(self, ctx: commands.Context) -> None:
        await ctx.send(
            "This command has been disabled. Bot owner can run `n!sync` for diagnostics.",
            delete_after=15,
        )

    @admin_text_group.command(name="sync_all")
    async def admin_text_sync_all(self, ctx: commands.Context) -> None:
        await ctx.send(
            "This command has been disabled. Bot owner can run `n!syncall` for diagnostics.",
            delete_after=15,
        )


async def setup(bot: commands.Bot) -> None:
    # Allow reloading without duplicate app command errors
    await bot.add_cog(AdminCommandsCog(bot), override=True)
