from __future__ import annotations

import logging
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.config import DiscordBotConfig
from app.bot.services.bot_settings import BotSettingsService
from app.bot.settings import GuildBotSettings


class BotSetupCog(commands.Cog):
    """Administrative helper commands for configuring the Discord bot."""

    def __init__(
        self,
        bot: commands.Bot,
        *,
        config: DiscordBotConfig,
        settings_service: BotSettingsService,
    ) -> None:
        """Store bot instance plus configuration and settings service dependencies."""
        super().__init__()
        self.bot = bot
        self._config = config
        self._settings = settings_service
        self._log = logging.getLogger(__name__)

    @app_commands.command(
        name="bot-setup", description="Configure quest/summary channels and roles."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def command_setup(
        self,
        interaction: discord.Interaction,
        quest_channel: discord.TextChannel,
        summary_channel: discord.TextChannel,
        player_role: discord.Role,
        referee_role: discord.Role,
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
        }
        self._log.info("bot-setup invoked", extra=context)
        try:
            settings = await self._settings.update_all(
                guild.id,
                quest_channel_id=quest_channel.id,
                summary_channel_id=summary_channel.id,
                player_role_id=player_role.id,
                referee_role_id=referee_role.id,
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
            embed.add_field(name="Quest channel", value=quest_channel, inline=False)
            embed.add_field(name="Summary channel", value=summary_channel, inline=False)
            embed.add_field(name="Player role", value=player_role, inline=True)
            embed.add_field(name="Referee role", value=referee_role, inline=True)
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
