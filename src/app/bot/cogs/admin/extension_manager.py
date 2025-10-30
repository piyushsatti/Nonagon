from __future__ import annotations

import importlib
from typing import Iterable

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.utils.logging import get_logger


def _iter_extensions(bot: commands.Bot) -> Iterable[str]:
    return sorted(bot.extensions.keys())


logger = get_logger(__name__)


class ExtensionManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="load", description="Load a bot extension module.")
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


async def setup(bot: commands.Bot):
    await bot.add_cog(ExtensionManagerCog(bot))
