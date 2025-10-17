from __future__ import annotations

import importlib
import logging
from typing import Iterable

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.utils.log_stream import send_demo_log


def _iter_extensions(bot: commands.Bot) -> Iterable[str]:
    return sorted(bot.extensions.keys())


class ExtensionManagerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.load_extension)
        self.bot.tree.add_command(self.unload_extension)
        self.bot.tree.add_command(self.reload_extension)
        self.bot.tree.add_command(self.list_extensions)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.load_extension.name, type=self.load_extension.type
        )
        self.bot.tree.remove_command(
            self.unload_extension.name, type=self.unload_extension.type
        )
        self.bot.tree.remove_command(
            self.reload_extension.name, type=self.reload_extension.type
        )
        self.bot.tree.remove_command(
            self.list_extensions.name, type=self.list_extensions.type
        )

    @app_commands.command(name="load", description="Load a bot extension module.")
    async def load_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.load_extension(extension)
        except Exception as exc:
            logging.exception("Failed to load extension %s", extension)
            await interaction.followup.send(
                f"Unable to load `{extension}`: {exc}", ephemeral=True
            )
            return

        if interaction.guild is not None:
            await send_demo_log(
                interaction.client,
                interaction.guild,
                f"Extension `{extension}` loaded by {interaction.user.mention if isinstance(interaction.user, discord.Member) else interaction.user}",
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
            logging.exception("Failed to unload extension %s", extension)
            await interaction.followup.send(
                f"Unable to unload `{extension}`: {exc}", ephemeral=True
            )
            return

        if interaction.guild is not None:
            await send_demo_log(
                interaction.client,
                interaction.guild,
                f"Extension `{extension}` unloaded by {interaction.user.mention if isinstance(interaction.user, discord.Member) else interaction.user}",
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
            logging.exception("Failed to reload extension %s", extension)
            await interaction.followup.send(
                f"Unable to reload `{extension}`: {exc}", ephemeral=True
            )
            return

        if interaction.guild is not None:
            await send_demo_log(
                interaction.client,
                interaction.guild,
                f"Extension `{extension}` reloaded by {interaction.user.mention if isinstance(interaction.user, discord.Member) else interaction.user}",
            )
        await interaction.followup.send(
            f"Reloaded extension `{extension}`", ephemeral=True
        )

    @app_commands.command(name="extensions", description="List loaded extensions.")
    async def list_extensions(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        exts = list(_iter_extensions(self.bot))
        if not exts:
            logging.info("No extensions loaded.")
            await interaction.followup.send("No extensions loaded.", ephemeral=True)
            return

        formatted = "\n".join(exts)
        logging.info("Loaded extensions: %s", formatted)
        await interaction.followup.send(
            f"Loaded extensions:\n{formatted}", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ExtensionManagerCog(bot))
