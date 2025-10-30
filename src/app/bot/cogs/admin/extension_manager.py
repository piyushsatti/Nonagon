from __future__ import annotations

import importlib
from typing import Iterable, List

import discord
import inspect
from discord import app_commands
from discord.ext import commands

from app.bot.utils.logging import get_logger
from app.bot.utils.sync import sync_guilds
from app.bot.cogs.manifest import ALIASES
from typing import Union


def _iter_extensions(bot: Union[commands.Bot, discord.Client]) -> Iterable[str]:
    # bot.extensions exists on both Bot and Client runtime instances
    return sorted(getattr(bot, "extensions", {}).keys())


async def extension_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    """Autocomplete available extensions. Returns choices showing a short name -> full path.

    Supports selecting either the short alias (e.g. `guild`) or the full path.
    """
    try:
        exts = list(_iter_extensions(interaction.client))
    except Exception:
        exts = []

    choices: List[app_commands.Choice[str]] = []
    seen_values = set()
    for ext in exts:
        parts = ext.split(".")
        short = parts[-2] if len(parts) >= 2 and parts[-1] == "cog" else parts[-1]
        # label shows short and full; value is the short alias (we no longer accept full paths)
        label = f"{short} → {ext}"
        if label.lower().find(current.lower()) != -1 or short.lower().find(current.lower()) != -1:
            if ext not in seen_values:
                # prefer offering the short alias as the selectable value
                choices.append(app_commands.Choice(name=label, value=short))
                seen_values.add(short)
        if len(choices) >= 25:
            break

    return choices


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

    def _resolve_extension(self, name: str) -> str:
        """Resolve a short alias to a full extension path.

        If `name` contains a dot it's treated as a path and returned unchanged.
        Otherwise we try to match the short name (last meaningful segment) to an available extension.
        """
        # Deterministic resolution via ALIASES manifest only (no backward full-path compatibility)
        resolved = ALIASES.get(name)
        if resolved:
            return resolved
        # if not mapped, raise ValueError to let the caller know quickly
        raise ValueError(f"Unknown extension alias: {name}")

    @app_commands.command(name="load", description="Load a bot extension module.")
    @app_commands.check(_owner_check)
    @app_commands.autocomplete(extension=extension_autocomplete)
    async def load_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            ext_to_load = self._resolve_extension(extension)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            await self.bot.load_extension(ext_to_load)
        except Exception as exc:
            logger.exception("Failed to load extension %s", ext_to_load)
            await interaction.followup.send(
                f"Unable to load `{ext_to_load}`: {exc}", ephemeral=True
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
                ext_to_load,
                actor_display,
            )
        await interaction.followup.send(
            f"Loaded extension `{ext_to_load}`", ephemeral=True
        )

    @app_commands.command(name="unload", description="Unload a bot extension module.")
    @app_commands.check(_owner_check)
    @app_commands.autocomplete(extension=extension_autocomplete)
    async def unload_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            ext_to_unload = self._resolve_extension(extension)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            await self.bot.unload_extension(ext_to_unload)
        except Exception as exc:
            logger.exception("Failed to unload extension %s", ext_to_unload)
            await interaction.followup.send(
                f"Unable to unload `{ext_to_unload}`: {exc}", ephemeral=True
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
                ext_to_unload,
                actor_display,
            )
        await interaction.followup.send(
            f"Unloaded extension `{ext_to_unload}`", ephemeral=True
        )

    @app_commands.command(name="reload", description="Reload a bot extension module.")
    @app_commands.check(_owner_check)
    @app_commands.autocomplete(extension=extension_autocomplete)
    async def reload_extension(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            ext_to_reload = self._resolve_extension(extension)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            importlib.reload(importlib.import_module(ext_to_reload))
            await self.bot.reload_extension(ext_to_reload)
        except Exception as exc:
            logger.exception("Failed to reload extension %s", ext_to_reload)
            await interaction.followup.send(
                f"Unable to reload `{ext_to_reload}`: {exc}", ephemeral=True
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
                ext_to_reload,
                actor_display,
            )
        await interaction.followup.send(
            f"Reloaded extension `{ext_to_reload}`", ephemeral=True
        )

    @commands.command(name="aliases")
    @commands.is_owner()
    async def aliases(self, ctx: commands.Context) -> None:
        """Owner-only prefix command: DM the owner the alias -> module mapping."""
        lines = [f"{alias}: {module}" for alias, module in ALIASES.items()]
        content = "\n".join(lines)
        try:
            # send full mapping via DM
            await ctx.author.send(f"Alias mapping (short -> full module):\n```\n{content}\n```")
            # brief channel confirmation
            await ctx.send("Sent you a DM with the current aliases.", delete_after=10)
        except Exception:
            # fallback to posting in-channel if DM fails
            await ctx.send(f"Alias mapping:\n```\n{content}\n```")

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
