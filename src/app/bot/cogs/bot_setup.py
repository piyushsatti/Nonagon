from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Sequence, cast

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.client import CogReloadResult
from app.bot.config import DiscordBotConfig
from app.bot.services.bot_settings import BotSettingsService
from app.bot.services.guild_logging import GuildLoggingService
from app.bot.settings import GuildBotSettings


class BotSetupCog(commands.Cog):
    """Administrative helper commands for configuring the Discord bot."""

    def __init__(
        self,
        bot: commands.Bot,
        *,
        config: DiscordBotConfig,
        settings_service: BotSettingsService,
        logging_service: GuildLoggingService,
    ) -> None:
        """Store bot instance plus configuration and settings service dependencies."""
        super().__init__()
        self.bot = bot
        self._config = config
        self._settings = settings_service
        self._logging = logging_service
        self._log = logging.getLogger(__name__)

    @app_commands.command(
        name="bot-setup", description="Configure quest/summary channels and roles."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        quest_channel="Channel where new quests will be posted",
        summary_channel="Channel where summaries will be ingested",
        player_role="Role required for players to create characters",
        referee_role="Role required to referee quests",
        logging_channel="Channel where the bot should post administrative logs",
    )
    async def command_setup(
        self,
        interaction: discord.Interaction,
        quest_channel: discord.TextChannel,
        summary_channel: discord.TextChannel,
        player_role: discord.Role,
        referee_role: discord.Role,
        logging_channel: discord.TextChannel,
    ) -> None:
        """Configure the tracked channels and roles for quest and summary management."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "quest_channel_id": quest_channel.id,
            "summary_channel_id": summary_channel.id,
            "player_role_id": player_role.id,
            "referee_role_id": referee_role.id,
            "log_channel_id": logging_channel.id,
        }
        self._log.info("bot-setup invoked", extra=context)
        try:
            settings = await self._settings.update_all(
                guild.id,
                quest_channel_id=quest_channel.id,
                summary_channel_id=summary_channel.id,
                player_role_id=player_role.id,
                referee_role_id=referee_role.id,
                log_channel_id=logging_channel.id,
            )
        except Exception:
            self._log.exception("bot-setup failed", extra=context)
            await self._reply(
                interaction,
                "Failed to update configuration. Check bot logs for details.",
            )
            return
        embed = self._settings_embed(
            "Configuration updated",
            "The bot will now listen for quests and summaries in the selected channels.",
            settings,
        )
        await self._reply(interaction, embed=embed)
        await self._log_admin_action(
            guild,
            title="/bot-setup applied",
            fields=[
                ("Quest channel", quest_channel.mention),
                ("Summary channel", summary_channel.mention),
                ("Player role", player_role.mention),
                ("Referee role", referee_role.mention),
                (
                    "Log channel",
                    logging_channel.mention,
                ),
            ],
        )

    @commands.command(name="botsetup", aliases=["bot-setup"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_setup_prefix(
        self,
        ctx: commands.Context[commands.Bot],
        quest_channel: discord.TextChannel,
        summary_channel: discord.TextChannel,
        player_role: str,
        referee_role: str,
        logging_channel: discord.TextChannel,
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        try:
            player_role_obj = await self._resolve_role(ctx, player_role)
            referee_role_obj = await self._resolve_role(ctx, referee_role)
        except commands.RoleNotFound as exc:
            await ctx.reply(f"Couldn't find role `{exc.argument}` in this server.")
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "quest_channel_id": quest_channel.id,
            "summary_channel_id": summary_channel.id,
            "player_role_id": player_role_obj.id,
            "referee_role_id": referee_role_obj.id,
            "log_channel_id": logging_channel.id,
        }
        self._log.info("botsetup invoked", extra=context)
        try:
            settings = await self._settings.update_all(
                guild.id,
                quest_channel_id=quest_channel.id,
                summary_channel_id=summary_channel.id,
                player_role_id=player_role_obj.id,
                referee_role_id=referee_role_obj.id,
                log_channel_id=logging_channel.id,
            )
        except Exception:
            self._log.exception("botsetup failed", extra=context)
            await ctx.reply(
                "Failed to update configuration. Check bot logs for details."
            )
            return
        embed = self._settings_embed(
            "Configuration updated",
            "The bot will now listen for quests and summaries in the selected channels.",
            settings,
        )
        await ctx.reply(embed=embed)
        await self._log_admin_action(
            guild,
            title="!botsetup",
            fields=[
                ("Quest channel", quest_channel.mention),
                ("Summary channel", summary_channel.mention),
                ("Player role", player_role_obj.mention),
                ("Referee role", referee_role_obj.mention),
                ("Log channel", logging_channel.mention),
            ],
        )

    @app_commands.command(
        name="bot-set-main-channel",
        description="Update the channel monitored for quest announcements.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def command_set_main_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        """Update the guild quest channel configuration."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        context: dict[str, Any] = {"guild_id": guild.id, "quest_channel_id": channel.id}
        self._log.info("bot-set-main-channel invoked", extra=context)
        try:
            settings = await self._settings.update_channels(
                guild.id, quest_channel_id=channel.id
            )
        except Exception:
            self._log.exception("Failed to update quest channel", extra=context)
            await self._reply(
                interaction,
                "Failed to update the quest channel. Check bot logs for details.",
            )
            return
        embed = self._settings_embed(
            "Quest channel updated",
            f"Now monitoring {channel.mention} for quest posts.",
            settings,
        )
        await self._reply(interaction, embed=embed)
        await self._log_admin_action(
            guild,
            title="/bot-set-main-channel",
            fields=[("Quest channel", channel.mention)],
        )

    @commands.command(name="botsetmain", aliases=["bot-set-main"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_set_main_channel_prefix(
        self, ctx: commands.Context[commands.Bot], channel: discord.TextChannel
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        context: dict[str, Any] = {"guild_id": guild.id, "quest_channel_id": channel.id}
        self._log.info("botsetmain invoked", extra=context)
        try:
            settings = await self._settings.update_channels(
                guild.id, quest_channel_id=channel.id
            )
        except Exception:
            self._log.exception("Failed to update quest channel", extra=context)
            await ctx.reply(
                "Failed to update the quest channel. Check bot logs for details."
            )
            return
        embed = self._settings_embed(
            "Quest channel updated",
            f"Now monitoring {channel.mention} for quest posts.",
            settings,
        )
        await ctx.reply(embed=embed)
        await self._log_admin_action(
            guild,
            title="!botsetmain",
            fields=[("Quest channel", channel.mention)],
        )

    @app_commands.command(
        name="bot-set-summary-channel",
        description="Update the channel monitored for adventure summaries.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def command_set_summary_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        """Update the guild summary channel configuration."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "summary_channel_id": channel.id,
        }
        self._log.info("bot-set-summary-channel invoked", extra=context)
        try:
            settings = await self._settings.update_channels(
                guild.id, summary_channel_id=channel.id
            )
        except Exception:
            self._log.exception("Failed to update summary channel", extra=context)
            await self._reply(
                interaction,
                "Failed to update the summary channel. Check bot logs for details.",
            )
            return
        embed = self._settings_embed(
            "Summary channel updated",
            f"Now monitoring {channel.mention} for summaries.",
            settings,
        )
        await self._reply(interaction, embed=embed)
        await self._log_admin_action(
            guild,
            title="/bot-set-summary-channel",
            fields=[("Summary channel", channel.mention)],
        )

    @commands.command(name="botsetsummary", aliases=["bot-set-summary"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_set_summary_channel_prefix(
        self, ctx: commands.Context[commands.Bot], channel: discord.TextChannel
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "summary_channel_id": channel.id,
        }
        self._log.info("botsetsummary invoked", extra=context)
        try:
            settings = await self._settings.update_channels(
                guild.id, summary_channel_id=channel.id
            )
        except Exception:
            self._log.exception("Failed to update summary channel", extra=context)
            await ctx.reply(
                "Failed to update the summary channel. Check bot logs for details."
            )
            return
        embed = self._settings_embed(
            "Summary channel updated",
            f"Now monitoring {channel.mention} for summaries.",
            settings,
        )
        await ctx.reply(embed=embed)
        await self._log_admin_action(
            guild,
            title="!botsetsummary",
            fields=[("Summary channel", channel.mention)],
        )

    @app_commands.command(
        name="bot-set-log-channel",
        description="Update or clear the channel used for administrative logs.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        channel="Channel where the bot should post configuration and ingestion logs. Leave empty to disable.",
    )
    async def command_set_log_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Update or remove the configured guild logging channel."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        log_channel_id = channel.id if channel else None
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "log_channel_id": log_channel_id,
        }
        self._log.info("bot-set-log-channel invoked", extra=context)
        try:
            settings = await self._settings.update_logging(
                guild.id, log_channel_id=log_channel_id
            )
        except Exception:
            self._log.exception("Failed to update log channel", extra=context)
            await self._reply(
                interaction,
                "Failed to update the logging channel. Check bot logs for details.",
            )
            return
        channel_display = channel.mention if channel else _format_channel(None)
        embed = self._settings_embed(
            "Logging channel updated",
            "The bot will send administrative updates to the selected channel.",
            settings,
        )
        await self._reply(interaction, embed=embed)
        await self._log_admin_action(
            guild,
            title="/bot-set-log-channel",
            fields=[("Log channel", channel_display)],
        )

    @commands.command(name="botsetlog", aliases=["bot-set-log"])
    @commands.has_permissions(administrator=True)
    async def command_set_log_channel_prefix(
        self,
        ctx: commands.Context[commands.Bot],
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        log_channel_id = channel.id if channel else None
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "log_channel_id": log_channel_id,
        }
        self._log.info("botsetlog invoked", extra=context)
        try:
            settings = await self._settings.update_logging(
                guild.id, log_channel_id=log_channel_id
            )
        except Exception:
            self._log.exception("Failed to update log channel", extra=context)
            await ctx.reply(
                "Failed to update the logging channel. Check bot logs for details."
            )
            return
        channel_display = channel.mention if channel else _format_channel(None)
        embed = self._settings_embed(
            "Logging channel updated",
            "The bot will send administrative updates to the selected channel.",
            settings,
        )
        await ctx.reply(embed=embed)
        await self._log_admin_action(
            guild,
            title="!botsetlog",
            fields=[("Log channel", channel_display)],
        )

    @app_commands.command(
        name="bot-reload",
        description="Reload bot cogs without restarting the process.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def command_reload(
        self, interaction: discord.Interaction, targets: Optional[str] = None
    ) -> None:
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        parsed_targets = self._parse_reload_targets_from_str(targets)
        try:
            results = await self._reload_cogs(parsed_targets)
        except RuntimeError as exc:
            await self._reply(interaction, str(exc))
            return
        embed = self._build_reload_embed(results)
        await self._reply(interaction, embed=embed)
        await self._log_reload_action(
            guild,
            actor=interaction.user,
            source="/bot-reload",
            results=results,
        )

    @commands.command(name="botreload", aliases=["bot-reload"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_reload_prefix(
        self, ctx: commands.Context[commands.Bot], *targets: str
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        parsed_targets = self._parse_reload_targets_from_args(targets)
        try:
            results = await self._reload_cogs(parsed_targets)
        except RuntimeError as exc:
            await ctx.reply(str(exc))
            return
        embed = self._build_reload_embed(results)
        await ctx.reply(embed=embed)
        actor = getattr(ctx, "author", None)
        await self._log_reload_action(
            guild,
            actor=actor,
            source="!botreload",
            results=results,
        )

    def _parse_reload_targets_from_str(self, raw: Optional[str]) -> list[str] | None:
        if raw is None:
            return None
        cleaned = raw.replace(";", ",")
        tokens = [segment.strip().lower() for segment in cleaned.split(",")]
        filtered = [token for token in tokens if token]
        return filtered or None

    def _parse_reload_targets_from_args(self, args: Sequence[str]) -> list[str] | None:
        if not args:
            return None
        joined = ",".join(args)
        return self._parse_reload_targets_from_str(joined)

    async def _reload_cogs(self, targets: list[str] | None) -> list[CogReloadResult]:
        bot = self.bot
        reload_method = getattr(bot, "reload_cogs", None)
        if not callable(reload_method):
            raise RuntimeError("Hot reload is not available on this bot instance.")
        typed_reload = cast(
            Callable[[Sequence[str] | None], Awaitable[list[CogReloadResult]]],
            reload_method,
        )
        results = await typed_reload(targets)
        return results

    def _build_reload_embed(self, results: Sequence[CogReloadResult]) -> discord.Embed:
        status_map = {
            "ok": ("✅", "Reloaded successfully."),
            "error": ("❌", "Reload failed."),
            "unknown": ("⚠️", "Unknown cog name."),
        }
        embed = discord.Embed(
            title="Cog reload",
            description="Reloaded bot extensions without restarting the process.",
            color=discord.Color.blurple(),
        )
        for result in results:
            key = getattr(result, "key", "<unknown>")
            status = getattr(result, "status", "unknown")
            emoji, default_detail = status_map.get(status, ("ℹ️", ""))
            detail = getattr(result, "detail", None) or default_detail
            embed.add_field(
                name=f"{emoji} {key}",
                value=detail,
                inline=False,
            )
        list_method = getattr(self.bot, "list_cogs", None)
        if callable(list_method):
            maybe_cogs = list_method()
            if isinstance(maybe_cogs, Sequence):
                items = cast(Sequence[object], maybe_cogs)
                available_parts: list[str] = []
                for item in items:
                    text = str(item)
                    if text:
                        available_parts.append(text)
                if available_parts:
                    available = ", ".join(available_parts)
                    embed.set_footer(text=f"Available cogs: {available}")
        return embed

    async def _log_reload_action(
        self,
        guild: discord.Guild,
        *,
        actor: discord.abc.User | None,
        source: str,
        results: Sequence[CogReloadResult],
    ) -> None:
        summary: list[tuple[str, str]] = []
        successes = [r.key for r in results if getattr(r, "status", "") == "ok"]
        failures = [r for r in results if getattr(r, "status", "") == "error"]
        unknowns = [r.key for r in results if getattr(r, "status", "") == "unknown"]
        if actor is not None:
            summary.append(("Actor", getattr(actor, "mention", str(actor))))
        if successes:
            summary.append(("Reloaded", ", ".join(successes)))
        if failures:
            detail = "; ".join(
                f"{getattr(r, 'key', '<unknown>')}: {getattr(r, 'detail', 'error')}"
                for r in failures
            )
            summary.append(("Failed", detail))
        if unknowns:
            summary.append(("Unknown", ", ".join(unknowns)))
        if not summary:
            summary.append(("Status", "No matching cogs provided."))
        await self._log_admin_action(guild, title=source, fields=summary)

    @app_commands.command(
        name="bot-load-cog",
        description="Load a Discord cog extension by module name.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        extension="Python module path or short name for the cog to load."
    )
    async def command_load_cog(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        try:
            normalized = self._normalize_extension(extension)
        except commands.ExtensionError:
            await self._reply(
                interaction,
                "Extension name must be provided. Use the module path or short cog name.",
            )
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "extension": normalized,
        }
        self._log.info("bot-load-cog invoked", extra=context)
        try:
            await asyncio.to_thread(self.bot.load_extension, normalized)
        except commands.ExtensionAlreadyLoaded:
            await self._reply(
                interaction,
                f"Extension `{normalized}` is already loaded.",
            )
            return
        except commands.ExtensionFailed as exc:
            self._log.exception("Failed to load extension", extra=context)
            await self._reply(
                interaction,
                f"Failed to load `{normalized}`: {exc.__class__.__name__}.",
            )
            return
        except commands.ExtensionNotFound:
            await self._reply(
                interaction,
                f"Extension `{normalized}` was not found.",
            )
            return
        await self._reply(
            interaction,
            f"Loaded extension `{normalized}` successfully.",
        )
        await self._log_admin_action(
            guild,
            title="/bot-load-cog",
            fields=[("Extension", normalized)],
        )

    @app_commands.command(
        name="bot-unload-cog",
        description="Unload a Discord cog extension by module name.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        extension="Python module path or short name for the cog to unload."
    )
    async def command_unload_cog(
        self, interaction: discord.Interaction, extension: str
    ) -> None:
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        try:
            normalized = self._normalize_extension(extension)
        except commands.ExtensionError:
            await self._reply(
                interaction,
                "Extension name must be provided. Use the module path or short cog name.",
            )
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "extension": normalized,
        }
        self._log.info("bot-unload-cog invoked", extra=context)
        try:
            await asyncio.to_thread(self.bot.unload_extension, normalized)
        except commands.ExtensionNotLoaded:
            await self._reply(
                interaction,
                f"Extension `{normalized}` is not currently loaded.",
            )
            return
        await self._reply(
            interaction,
            f"Unloaded extension `{normalized}` successfully.",
        )
        await self._log_admin_action(
            guild,
            title="/bot-unload-cog",
            fields=[("Extension", normalized)],
        )

    @commands.command(name="botload", aliases=["bot-load-cog"])
    @commands.has_permissions(administrator=True)
    async def command_load_cog_prefix(
        self, ctx: commands.Context[commands.Bot], extension: str
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        try:
            normalized = self._normalize_extension(extension)
        except commands.ExtensionError:
            await ctx.reply(
                "Extension name must be provided. Use the module path or short cog name."
            )
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "extension": normalized,
        }
        self._log.info("botload invoked", extra=context)
        try:
            await asyncio.to_thread(self.bot.load_extension, normalized)
        except commands.ExtensionAlreadyLoaded:
            await ctx.reply(f"Extension `{normalized}` is already loaded.")
            return
        except commands.ExtensionFailed as exc:
            self._log.exception("Failed to load extension", extra=context)
            await ctx.reply(f"Failed to load `{normalized}`: {exc.__class__.__name__}.")
            return
        except commands.ExtensionNotFound:
            await ctx.reply(f"Extension `{normalized}` was not found.")
            return
        await ctx.reply(f"Loaded extension `{normalized}` successfully.")
        await self._log_admin_action(
            guild,
            title="!botload",
            fields=[("Extension", normalized)],
        )

    @commands.command(name="botunload", aliases=["bot-unload-cog"])
    @commands.has_permissions(administrator=True)
    async def command_unload_cog_prefix(
        self, ctx: commands.Context[commands.Bot], extension: str
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        try:
            normalized = self._normalize_extension(extension)
        except commands.ExtensionError:
            await ctx.reply(
                "Extension name must be provided. Use the module path or short cog name."
            )
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "extension": normalized,
        }
        self._log.info("botunload invoked", extra=context)
        try:
            await asyncio.to_thread(self.bot.unload_extension, normalized)
        except commands.ExtensionNotLoaded:
            await ctx.reply(f"Extension `{normalized}` is not currently loaded.")
            return
        await ctx.reply(f"Unloaded extension `{normalized}` successfully.")
        await self._log_admin_action(
            guild,
            title="!botunload",
            fields=[("Extension", normalized)],
        )

    @app_commands.command(
        name="bot-set-player-role",
        description="Set the role that grants player permissions.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def command_set_player_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        """Assign which role grants player permissions for character creation."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        context: dict[str, Any] = {"guild_id": guild.id, "player_role_id": role.id}
        self._log.info("bot-set-player-role invoked", extra=context)
        try:
            settings = await self._settings.update_roles(
                guild.id, player_role_id=role.id
            )
        except Exception:
            self._log.exception("Failed to update player role", extra=context)
            await self._reply(
                interaction,
                "Failed to update the player role. Check bot logs for details.",
            )
            return
        embed = self._settings_embed(
            "Player role updated",
            f"Members require {role.mention} to create characters.",
            settings,
        )
        await self._reply(interaction, embed=embed)
        await self._log_admin_action(
            guild,
            title="/bot-set-player-role",
            fields=[("Player role", role.mention)],
        )

    @commands.command(name="botsetplayerrole", aliases=["bot-set-player-role"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_set_player_role_prefix(
        self, ctx: commands.Context[commands.Bot], role: str
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        try:
            role_obj = await self._resolve_role(ctx, role)
        except commands.RoleNotFound as exc:
            await ctx.reply(f"Couldn't find role `{exc.argument}` in this server.")
            return
        context: dict[str, Any] = {"guild_id": guild.id, "player_role_id": role_obj.id}
        self._log.info("botsetplayerrole invoked", extra=context)
        try:
            settings = await self._settings.update_roles(
                guild.id, player_role_id=role_obj.id
            )
        except Exception:
            self._log.exception("Failed to update player role", extra=context)
            await ctx.reply(
                "Failed to update the player role. Check bot logs for details."
            )
            return
        embed = self._settings_embed(
            "Player role updated",
            f"Members require {role_obj.mention} to create characters.",
            settings,
        )
        await ctx.reply(embed=embed)
        await self._log_admin_action(
            guild,
            title="!botsetplayerrole",
            fields=[("Player role", role_obj.mention)],
        )

    @app_commands.command(
        name="bot-set-referee-role",
        description="Set the role required for quest/referee actions.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def command_set_referee_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        """Assign which role grants referee posting permissions."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        context: dict[str, Any] = {"guild_id": guild.id, "referee_role_id": role.id}
        self._log.info("bot-set-referee-role invoked", extra=context)
        try:
            settings = await self._settings.update_roles(
                guild.id, referee_role_id=role.id
            )
        except Exception:
            self._log.exception("Failed to update referee role", extra=context)
            await self._reply(
                interaction,
                "Failed to update the referee role. Check bot logs for details.",
            )
            return
        embed = self._settings_embed(
            "Referee role updated",
            f"Members require {role.mention} to post quests and summaries.",
            settings,
        )
        await self._reply(interaction, embed=embed)
        await self._log_admin_action(
            guild,
            title="/bot-set-referee-role",
            fields=[("Referee role", role.mention)],
        )

    @commands.command(name="botsetrefereerole", aliases=["bot-set-referee-role"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_set_referee_role_prefix(
        self, ctx: commands.Context[commands.Bot], role: str
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        try:
            role_obj = await self._resolve_role(ctx, role)
        except commands.RoleNotFound as exc:
            await ctx.reply(f"Couldn't find role `{exc.argument}` in this server.")
            return
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "referee_role_id": role_obj.id,
        }
        self._log.info("botsetrefereerole invoked", extra=context)
        try:
            settings = await self._settings.update_roles(
                guild.id, referee_role_id=role_obj.id
            )
        except Exception:
            self._log.exception("Failed to update referee role", extra=context)
            await ctx.reply(
                "Failed to update the referee role. Check bot logs for details."
            )
            return
        embed = self._settings_embed(
            "Referee role updated",
            f"Members require {role_obj.mention} to post quests and summaries.",
            settings,
        )
        await ctx.reply(embed=embed)
        await self._log_admin_action(
            guild,
            title="!botsetrefereerole",
            fields=[("Referee role", role_obj.mention)],
        )

    @app_commands.command(
        name="bot-dm-player",
        description="Send a direct message to a player from the bot account.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(message="Optional message to include in the DM")
    async def command_dm_player(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: Optional[str] = None,
    ) -> None:
        """Send an optional bot-authored direct message to a player."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        content = message or "Hello!"
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "member_id": member.id,
            "has_message": bool(message),
        }
        self._log.info("bot-dm-player invoked", extra=context)
        try:
            await member.send(content)
        except discord.Forbidden:
            await self._reply(
                interaction,
                f"I couldn't DM {member.mention}. They may have DMs disabled.",
            )
            return
        except discord.HTTPException as exc:  # pragma: no cover - defensive
            self._log.warning("Failed to DM member", extra=context, exc_info=exc)
            await self._reply(
                interaction,
                f"Discord rejected the DM to {member.mention}. Try again later.",
            )
            return
        await self._reply(
            interaction,
            f"Sent a DM to {member.mention}.",
        )

    @commands.command(name="botdmplayer", aliases=["bot-dm-player"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def command_dm_player_prefix(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        *,
        message: Optional[str] = None,
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        content = message or "Hello!"
        context: dict[str, Any] = {
            "guild_id": guild.id,
            "member_id": member.id,
            "has_message": bool(message),
        }
        self._log.info("botdmplayer invoked", extra=context)
        try:
            await member.send(content)
        except discord.Forbidden:
            await ctx.reply(
                f"I couldn't DM {member.mention}. They may have DMs disabled."
            )
            return
        except discord.HTTPException as exc:  # pragma: no cover - defensive
            self._log.warning("Failed to DM member", extra=context, exc_info=exc)
            await ctx.reply(
                f"Discord rejected the DM to {member.mention}. Try again later."
            )
            return
        await ctx.reply(f"Sent a DM to {member.mention}.")

    @app_commands.command(
        name="bot-settings",
        description="Show the current bot configuration for this guild.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def command_show_settings(self, interaction: discord.Interaction) -> None:
        """Display the stored bot configuration for the current guild."""
        guild = await self._ensure_guild(interaction)
        if guild is None:
            return
        await self._defer_ephemeral(interaction)
        context: dict[str, Any] = {"guild_id": guild.id}
        self._log.info("bot-settings invoked", extra=context)
        try:
            settings = await self._settings.get_settings(guild.id)
        except Exception:
            self._log.exception("Failed to load bot settings", extra=context)
            await self._reply(
                interaction,
                "Failed to load settings. Check bot logs for details.",
            )
            return
        embed = self._settings_embed("Current bot settings", None, settings)
        await self._reply(interaction, embed=embed)

    @commands.command(name="botsettings", aliases=["bot-settings"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def command_show_settings_prefix(
        self, ctx: commands.Context[commands.Bot]
    ) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command must be used inside a server.")
            return
        context: dict[str, Any] = {"guild_id": guild.id}
        self._log.info("botsettings invoked", extra=context)
        try:
            settings = await self._settings.get_settings(guild.id)
        except Exception:
            self._log.exception("Failed to load bot settings", extra=context)
            await ctx.reply("Failed to load settings. Check bot logs for details.")
            return
        embed = self._settings_embed("Current bot settings", None, settings)
        await ctx.reply(embed=embed)

    async def _ensure_guild(
        self, interaction: discord.Interaction
    ) -> discord.Guild | None:
        """Return the guild for an interaction or notify the user if absent."""
        guild = interaction.guild
        if guild is None:
            await self._reply(interaction, "This command must be used inside a server.")
            return None
        return guild

    async def _defer_ephemeral(self, interaction: discord.Interaction) -> None:
        """Defer a response ephemerally if the interaction hasn't replied yet."""
        if interaction.response.is_done():
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

    def _settings_embed(
        self,
        title: str,
        description: str | None,
        settings: GuildBotSettings | None = None,
    ) -> discord.Embed:
        """Construct a settings embed that mirrors the stored configuration values."""
        embed = discord.Embed(
            title=title, description=description, color=discord.Color.blurple()
        )
        if settings:
            quest_channel = _format_channel(settings.quest_channel_id)
            summary_channel = _format_channel(settings.summary_channel_id)
            player_role = _format_role(settings.player_role_id)
            referee_role = _format_role(settings.referee_role_id)
            log_channel = _format_channel(settings.log_channel_id)
            embed.add_field(name="Quest channel", value=quest_channel, inline=False)
            embed.add_field(name="Summary channel", value=summary_channel, inline=False)
            embed.add_field(name="Player role", value=player_role, inline=True)
            embed.add_field(name="Referee role", value=referee_role, inline=True)
            embed.add_field(name="Log channel", value=log_channel, inline=False)
        return embed

    async def _reply(
        self,
        interaction: discord.Interaction,
        content: Optional[str] = None,
        *,
        embed: discord.Embed | None = None,
        ephemeral: bool = True,
    ) -> None:
        """Reply to an interaction, reusing followups when the initial response is complete."""
        payload: dict[str, Any] = {"ephemeral": ephemeral}
        if content is not None:
            payload["content"] = content
        if embed is not None:
            payload["embed"] = embed
        if interaction.response.is_done():
            await interaction.followup.send(**payload)
        else:
            await interaction.response.send_message(**payload)

    async def _log_admin_action(
        self,
        guild: discord.Guild,
        *,
        title: str,
        description: str | None = None,
        fields: list[tuple[str, str]] | None = None,
    ) -> None:
        await self._logging.log_event(
            guild.id,
            title=title,
            description=description,
            fields=fields or [],
        )

    def _normalize_extension(self, extension: str) -> str:
        candidate = (extension or "").strip()
        if not candidate:
            raise commands.ExtensionNotFound("<empty>")
        if "." not in candidate:
            candidate = f"app.bot.cogs.{candidate}"
        return candidate

    async def _resolve_role(
        self, ctx: commands.Context[commands.Bot], value: str
    ) -> discord.Role:
        converter = commands.RoleConverter()
        try:
            return await converter.convert(ctx, value)
        except commands.RoleNotFound:
            guild = ctx.guild
            if guild is None:
                raise
            cleaned = value.strip()
            if cleaned.isdigit():
                role = guild.get_role(int(cleaned))
                if role:
                    return role
            cleaned = cleaned.strip("<@&>")
            if cleaned.isdigit():
                role = guild.get_role(int(cleaned))
                if role:
                    return role
            lower = cleaned.lower()
            for role in guild.roles:
                if role.name.lower() == lower:
                    return role
            raise


def _format_channel(channel_id: int | None) -> str:
    """Format a stored channel ID for embed display."""
    if channel_id is None:
        return "Not configured"
    return f"<#{channel_id}>"


def _format_role(role_id: int | None) -> str:
    """Format a stored role ID for embed display."""
    if role_id is None:
        return "Not configured"
    return f"<@&{role_id}>"
