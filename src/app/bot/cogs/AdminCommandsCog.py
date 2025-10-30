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

    async def _sync_guilds(self, target_ids: set[int]) -> list[str]:
        results: list[str] = []
        for guild_id in target_ids:
            guild_obj = discord.Object(id=guild_id)
            try:
                self.bot.tree.copy_global_to(guild=guild_obj)
                commands_synced = await self.bot.tree.sync(guild=guild_obj)
                results.append(f"{guild_id}: {len(commands_synced)} commands")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to sync commands for guild %s", guild_id)
                results.append(f"{guild_id}: failed ({exc})")
        return results

    @admin.command(
        name="sync",
        description="Force a slash-command sync for this guild (or every guild).",
    )
    @app_commands.describe(all_guilds="Sync every guild the bot is in (defaults to current guild only).")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync(
        self, interaction: discord.Interaction, all_guilds: Optional[bool] = False
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        target_ids: set[int]
        if all_guilds:
            target_ids = {guild.id for guild in self.bot.guilds}
            if not target_ids:
                await interaction.followup.send(
                    "I'm not connected to any guilds yet; nothing to sync.",
                    ephemeral=True,
                )
                return
        else:
            if interaction.guild is None:
                await interaction.followup.send(
                    "This command can only be used inside a guild.",
                    ephemeral=True
                )
                return
            target_ids = {interaction.guild.id}

        results = await self._sync_guilds(target_ids)
        await interaction.followup.send(
            "Command sync results:\n" + "\n".join(results),
            ephemeral=True
        )

    @commands.group(name="admin", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def admin_text_group(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "Available admin subcommands: sync, sync_all.",
                delete_after=15,
            )

    @admin_text_group.command(name="sync")
    async def admin_text_sync(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            await ctx.send("This command can only be used inside a guild.")
            return

        results = await self._sync_guilds({ctx.guild.id})
        await ctx.send("Command sync results:\n" + "\n".join(results))

    @admin_text_group.command(name="sync_all")
    async def admin_text_sync_all(self, ctx: commands.Context) -> None:
        target_ids = {guild.id for guild in self.bot.guilds}
        if not target_ids:
            await ctx.send("I'm not connected to any guilds yet; nothing to sync.")
            return

        results = await self._sync_guilds(target_ids)
        await ctx.send("Command sync results:\n" + "\n".join(results))


async def setup(bot: commands.Bot) -> None:
    # Allow reloading without duplicate app command errors
    await bot.add_cog(AdminCommandsCog(bot), override=True)
