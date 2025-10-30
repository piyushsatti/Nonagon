from __future__ import annotations

import importlib
from typing import Iterable

import discord
import inspect
from discord import app_commands
from discord.ext import commands

from app.bot.utils.logging import get_logger
from app.bot.utils.sync import sync_guilds


def _iter_extensions(bot: commands.Bot) -> Iterable[str]:
    return sorted(bot.extensions.keys())


logger = get_logger(__name__)
async def _owner_check(interaction: discord.Interaction) -> bool:
    """App-command check that only allows the bot owner to run the command."""
    # discord.py provides a coroutine to check ownership on the client/bot
    try:
        is_owner_callable = getattr(interaction.client, "is_owner", None)
        if callable(is_owner_callable):
            result = is_owner_callable(interaction.user)
            if inspect.isawaitable(result):
                return await result
            return bool(result)
    except Exception:
        logger.exception("Failed running owner check for extension manager")
    return False


class ExtensionManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="load", description="Load a bot extension module.")
    @app_commands.check(_owner_check)
    async def load_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.load_extension(extension)
        except Exception as exc:
            logger.exception("Failed to load extension %s", extension)
            await interaction.followup.send(
                f"Unable to load `{extension}`: {exc}", ephemeral=True
            )
            return

        if interaction.guild is not None:
            actor_display = (
                interaction.user.mention
                if isinstance(interaction.user, discord.Member)
                else str(interaction.user)
            )
            await logger.audit(
                interaction.client,
                interaction.guild,
                "Extension `%s` loaded by %s",
                extension,
                actor_display,
            )
        await interaction.followup.send(
            f"Loaded extension `{extension}`", ephemeral=True
        )

    @app_commands.command(name="unload", description="Unload a bot extension module.")
    @app_commands.check(_owner_check)
    async def unload_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.unload_extension(extension)
        except Exception as exc:
            logger.exception("Failed to unload extension %s", extension)
            await interaction.followup.send(
                f"Unable to unload `{extension}`: {exc}", ephemeral=True
            )
            return

        if interaction.guild is not None:
            actor_display = (
                interaction.user.mention
                if isinstance(interaction.user, discord.Member)
                else str(interaction.user)
            )
            await logger.audit(
                interaction.client,
                interaction.guild,
                "Extension `%s` unloaded by %s",
                extension,
                actor_display,
            )
        await interaction.followup.send(
            f"Unloaded extension `{extension}`", ephemeral=True
        )

    @app_commands.command(name="reload", description="Reload a bot extension module.")
    @app_commands.check(_owner_check)
    async def reload_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            importlib.reload(importlib.import_module(extension))
            await self.bot.reload_extension(extension)
        except Exception as exc:
            logger.exception("Failed to reload extension %s", extension)
            await interaction.followup.send(
                f"Unable to reload `{extension}`: {exc}", ephemeral=True
            )
            return

        if interaction.guild is not None:
            actor_display = (
                interaction.user.mention
                if isinstance(interaction.user, discord.Member)
                else str(interaction.user)
            )
            await logger.audit(
                interaction.client,
                interaction.guild,
                "Extension `%s` reloaded by %s",
                extension,
                actor_display,
            )
        await interaction.followup.send(
            f"Reloaded extension `{extension}`", ephemeral=True
        )

    @app_commands.command(name="extensions", description="List loaded extensions.")
    @app_commands.check(_owner_check)
    async def list_extensions(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        exts = list(_iter_extensions(self.bot))
        if not exts:
            logger.info("No extensions loaded.")
            await interaction.followup.send("No extensions loaded.", ephemeral=True)
            return

        formatted = "\n".join(exts)
        logger.info("Loaded extensions: %s", formatted)
        await interaction.followup.send(
            f"Loaded extensions:\n{formatted}", ephemeral=True
        )

    @app_commands.command(name="sync", description="Sync application commands to this guild (owner-only).")
    @app_commands.guild_only()
    @app_commands.check(_owner_check)
    async def sync(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send("This command must be run inside a guild.", ephemeral=True)
            return

        try:
            results = await sync_guilds(self.bot, {interaction.guild.id})
            await interaction.followup.send(f"Synced: {results[0] if results else 'no results'}", ephemeral=True)
        except Exception as exc:
            logger.exception("Failed to sync application commands for guild %s: %s", getattr(interaction.guild, "id", "<unknown>"), exc)
            await interaction.followup.send(f"Failed to sync commands: {exc}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ExtensionManagerCog(bot))
