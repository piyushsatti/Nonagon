from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional
import logging

import discord
from discord import app_commands
from discord.ext import commands
from pymongo.errors import PyMongoError

from app.bot.database import db_client
from app.bot.services import guild_settings_store
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_user_sync
from app.infra.mongo.users_repo import UsersRepoMongo


class SetupCommandsCog(commands.Cog):
    """Slash command group for configuring Nonagon in a guild."""

    setup = app_commands.Group(
        name="setup", description="Configure Nonagon for this Discord guild."
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.users_repo = UsersRepoMongo()

    # ------------------------------------------------------------------ #
    # Shared helpers

    def _save_settings(
        self, guild: discord.Guild, actor_id: int, updates: Dict[str, object]
    ) -> Dict[str, object]:
        config = guild_settings_store.fetch_settings(guild.id) or {}
        config.update(updates)
        config["guild_id"] = guild.id
        config["configured_by"] = actor_id
        now = datetime.now(timezone.utc)
        if "configured_at" not in config:
            config["configured_at"] = now
        config["updated_at"] = now
        guild_settings_store.save_settings(guild.id, config)
        return config

    @staticmethod
    def _coerce_int(raw: Optional[object]) -> Optional[int]:
        try:
            if raw is None:
                return None
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_channel(
        guild: discord.Guild,
        channel_id: Optional[int],
        fallback_name: Optional[str],
    ) -> str:
        if channel_id is None:
            return "Not set"
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel.mention
        name = fallback_name or "Unknown"
        return f"# {name}"

    @staticmethod
    def _format_role(
        guild: discord.Guild,
        role_id: Optional[int],
        fallback_name: Optional[str],
    ) -> str:
        if role_id is None:
            return "Not set"
        role = guild.get_role(role_id)
        if isinstance(role, discord.Role):
            return role.mention
        name = fallback_name or "Unknown"
        return f"@ {name}"

    @staticmethod
    def _member_has_server_tag(
        member: discord.Member,
        role_id: Optional[int],
        pattern: Optional[str],
    ) -> bool:
        if role_id is not None:
            role = member.guild.get_role(role_id)
            if role and role in member.roles:
                return True
        if pattern:
            target = (member.nick or member.display_name or member.name or "").lower()
            if pattern.lower() in target:
                return True
        return False

    @staticmethod
    def _ensure_bot_permissions(
        channel: discord.TextChannel,
        *,
        require_send: bool = True,
        require_private_threads: bool = False,
    ) -> Optional[str]:
        me = channel.guild.me
        if me is None:
            return "Unable to resolve bot permissions in this guild."

        perms = channel.permissions_for(me)
        if require_send and not perms.send_messages:
            return (
                f"I need the **Send Messages** permission in {channel.mention} before "
                "I can store it."
            )
        if require_private_threads and not (perms.create_private_threads or perms.manage_threads):
            return (
                f"I need the **Create Private Threads** permission in {channel.mention} "
                "to support onboarding threads."
            )
        return None

    def _build_status_embed(
        self, guild: discord.Guild, settings: Dict[str, object]
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{guild.name} configuration",
            colour=discord.Colour.blurple(),
            timestamp=settings.get("updated_at") or settings.get("configured_at"),
        )

        embed.add_field(
            name="Quest announcement channel",
            value=self._format_channel(
                guild,
                self._coerce_int(settings.get("quest_commands_channel_id")),
                settings.get("quest_commands_channel_name"),
            ),
            inline=False,
        )
        embed.add_field(
            name="Quest ping role",
            value=self._format_role(
                guild,
                self._coerce_int(settings.get("quest_ping_role_id")),
                settings.get("quest_ping_role_name"),
            ),
            inline=False,
        )

        embed.add_field(
            name="Summary channel",
            value=self._format_channel(
                guild,
                self._coerce_int(settings.get("summary_channel_id")),
                settings.get("summary_channel_name"),
            ),
            inline=False,
        )
        embed.add_field(
            name="Character channel",
            value=self._format_channel(
                guild,
                self._coerce_int(settings.get("character_commands_channel_id")),
                settings.get("character_commands_channel_name"),
            ),
            inline=False,
        )
        embed.add_field(
            name="Logging channel",
            value=self._format_channel(
                guild,
                self._coerce_int(settings.get("log_channel_id")),
                settings.get("log_channel_name"),
            ),
            inline=False,
        )

        server_tag_enabled = bool(settings.get("server_tag_enabled"))
        if server_tag_enabled:
            server_tag_details = [
                f"Role: {self._format_role(guild, self._coerce_int(settings.get('server_tag_role_id')), settings.get('server_tag_role_name'))}",
                f"Pattern: `{settings.get('server_tag_pattern')}`"
                if settings.get("server_tag_pattern")
                else "Pattern: Not set",
                f"Mention Role: {self._format_role(guild, self._coerce_int(settings.get('server_tag_mention_role_id')), settings.get('server_tag_mention_role_name'))}",
            ]
            embed.add_field(
                name="Server tag tracking",
                value="\n".join(server_tag_details),
                inline=False,
            )
        else:
            embed.add_field(name="Server tag tracking", value="Disabled", inline=False)

        boosters_enabled = bool(settings.get("boosters_enabled"))
        if boosters_enabled:
            embed.add_field(
                name="Booster tracking",
                value=f"Enabled, role: {self._format_role(guild, self._coerce_int(settings.get('boosters_role_id')), settings.get('boosters_role_name'))}",
                inline=False,
            )
        else:
            embed.add_field(name="Booster tracking", value="Disabled", inline=False)

        allowed_names = settings.get("allowed_role_names") or []
        if allowed_names:
            embed.add_field(
                name="Allowed roles (legacy)",
                value=", ".join(f"`{name}`" for name in allowed_names),
                inline=False,
            )

        configured_by = settings.get("configured_by")
        if configured_by:
            embed.set_footer(text=f"Last updated by <@{configured_by}>")

        return embed

    # ------------------------------------------------------------------ #
    # Core commands

    @setup.command(name="help", description="Learn what the /setup commands do.")
    @app_commands.guild_only()
    async def setup_help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Nonagon Setup Commands",
            colour=discord.Colour.blurple(),
            description="Configure channels, roles, and sync utilities for this guild.",
        )
        embed.add_field(
            name="/setup quest",
            value="Set quest announcement channel and optional ping role.",
            inline=False,
        )
        embed.add_field(
            name="/setup summary",
            value="Choose the channel where summaries are posted.",
            inline=False,
        )
        embed.add_field(
            name="/setup character",
            value="Select the channel for character announcements (requires thread perms).",
            inline=False,
        )
        embed.add_field(
            name="/setup logging",
            value="Direct diagnostic logs to a specific channel.",
            inline=False,
        )
        embed.add_field(
            name="/setup server_tag",
            value="Enable/disable server tag tracking and optional mention role.",
            inline=False,
        )
        embed.add_field(
            name="/setup boosters",
            value="Toggle booster tracking and optionally store a booster role.",
            inline=False,
        )
        embed.add_field(
            name="/setup refresh",
            value="Reload guild members into Nonagon's cache and update server-tag flags.",
            inline=False,
        )
        embed.add_field(
            name="/setup status",
            value="View the current settings snapshot.",
            inline=False,
        )
        embed.add_field(
            name="/setup reset",
            value="Clear all stored settings (does not delete Discord resources).",
            inline=False,
        )
        embed.add_field(
            name="/setup sync",
            value="Force a slash-command sync for this guild (rapid iteration helper).",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup.command(name="status", description="View current Nonagon configuration.")
    @app_commands.guild_only()
    async def setup_status(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        settings = guild_settings_store.fetch_settings(interaction.guild.id) or {}
        if not settings:
            await interaction.response.send_message(
                "No settings stored yet. Use `/setup quest`, `/setup character`, etc. to configure Nonagon.",
                ephemeral=True,
            )
            return

        embed = self._build_status_embed(interaction.guild, settings)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup.command(name="reset", description="Clear stored setup data for this guild.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_reset(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        deleted = guild_settings_store.delete_settings(interaction.guild.id)
        if deleted:
            message = "Stored configuration cleared. Existing roles/channels were left untouched."
        else:
            message = "No stored configuration found for this guild."
        await interaction.response.send_message(message, ephemeral=True)

    @setup.command(name="sync", description="Force slash-command sync for this guild.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_sync(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild_obj = discord.Object(id=interaction.guild.id)
        try:
            self.bot.tree.copy_global_to(guild=guild_obj)
            commands_synced = await self.bot.tree.sync(guild=guild_obj)
            message = f"Synced {len(commands_synced)} slash commands to this guild."
        except Exception as exc:
            message = f"Failed to sync commands: {exc}"

        await interaction.followup.send(message, ephemeral=True)

    @setup.command(
        name="refresh",
        description="Reload members and update cached user data for this guild.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_refresh(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        settings = guild_settings_store.fetch_settings(guild.id) or {}
        server_tag_enabled = bool(settings.get("server_tag_enabled"))
        server_tag_role_id = (
            self._coerce_int(settings.get("server_tag_role_id"))
            if server_tag_enabled
            else None
        )
        server_tag_pattern = (
            settings.get("server_tag_pattern") if server_tag_enabled else None
        )

        processed = 0
        created = 0
        updated = 0
        tagged = 0

        try:
            async for member in guild.fetch_members(limit=None):
                processed += 1
                has_tag = self._member_has_server_tag(
                    member, server_tag_role_id, server_tag_pattern
                )
                if has_tag:
                    tagged += 1

                existing_user = await self.users_repo.get_by_discord_id(
                    guild.id, str(member.id)
                )
                if existing_user is None:
                    user = User.from_member(member)
                    created += 1
                else:
                    user = existing_user
                    updated += 1
                user.guild_id = guild.id
                user.discord_id = str(member.id)
                user.has_server_tag = has_tag
                if member.joined_at:
                    user.joined_at = member.joined_at

                await asyncio.to_thread(upsert_user_sync, db_client, guild.id, user)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.followup.send(
                f"Failed to fetch members: {exc}", ephemeral=True
            )
            return
        except PyMongoError as exc:
            logging.exception(
                "Failed to refresh guild cache for guild %s due to database error: %s",
                guild.id,
                exc,
            )
            await interaction.followup.send(
                "Unable to connect to the database while refreshing members. "
                "Verify the MongoDB service is reachable and try again.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Member refresh complete",
            colour=discord.Colour.green(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Processed members", value=str(processed))
        embed.add_field(name="Created users", value=str(created))
        embed.add_field(name="Updated users", value=str(updated))
        embed.add_field(name="Server-tagged", value=str(tagged))

        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup.command(
        name="quest",
        description="Configure quest announcement channel and optional ping role.",
    )
    @app_commands.describe(
        announcement_channel="Channel where quest announcements are posted.",
        pings="Role to mention when announcing quests (optional).",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_quest(
        self,
        interaction: discord.Interaction,
        announcement_channel: discord.TextChannel,
        pings: Optional[discord.Role] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        error = self._ensure_bot_permissions(announcement_channel, require_send=True)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        config = self._save_settings(
            interaction.guild,
            interaction.user.id,
            {
                "quest_commands_channel_id": announcement_channel.id,
                "quest_commands_channel_name": announcement_channel.name,
                "quest_ping_role_id": pings.id if pings else None,
                "quest_ping_role_name": pings.name if pings else None,
            },
        )

        embed = discord.Embed(
            title="Quest settings updated",
            colour=discord.Colour.blurple(),
            timestamp=config.get("updated_at"),
        )
        embed.add_field(
            name="Announcement channel",
            value=announcement_channel.mention,
            inline=False,
        )
        embed.add_field(
            name="Ping role",
            value=pings.mention if pings else "None",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup.command(
        name="summary", description="Configure the channel used for quest summaries."
    )
    @app_commands.describe(summary_channel="Channel where summaries should be posted.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_summary(
        self,
        interaction: discord.Interaction,
        summary_channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        error = self._ensure_bot_permissions(summary_channel, require_send=True)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        config = self._save_settings(
            interaction.guild,
            interaction.user.id,
            {
                "summary_channel_id": summary_channel.id,
                "summary_channel_name": summary_channel.name,
            },
        )
        embed = discord.Embed(
            title="Summary channel updated",
            colour=discord.Colour.blurple(),
            timestamp=config.get("updated_at"),
            description=f"Summaries will be posted in {summary_channel.mention}.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup.command(
        name="character",
        description="Configure the channel where character announcements are posted.",
    )
    @app_commands.describe(
        character_channel="Channel used by /character create to post announcements."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_character(
        self,
        interaction: discord.Interaction,
        character_channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        error = self._ensure_bot_permissions(
            character_channel,
            require_send=True,
            require_private_threads=True,
        )
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        config = self._save_settings(
            interaction.guild,
            interaction.user.id,
            {
                "character_commands_channel_id": character_channel.id,
                "character_commands_channel_name": character_channel.name,
            },
        )
        embed = discord.Embed(
            title="Character channel updated",
            colour=discord.Colour.blurple(),
            timestamp=config.get("updated_at"),
            description=(
                f"New characters will be announced in {character_channel.mention}. "
                "Ensure I keep **Create Private Threads** permission in this channel."
            ),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup.command(
        name="logging", description="Choose where Nonagon should send diagnostic logs."
    )
    @app_commands.describe(log_channel="Channel that will receive diagnostic logs.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_logging(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        error = self._ensure_bot_permissions(log_channel, require_send=True)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        config = self._save_settings(
            interaction.guild,
            interaction.user.id,
            {
                "log_channel_id": log_channel.id,
                "log_channel_name": log_channel.name,
            },
        )
        embed = discord.Embed(
            title="Logging channel updated",
            colour=discord.Colour.blurple(),
            timestamp=config.get("updated_at"),
            description=f"Diagnostics will be sent to {log_channel.mention}.",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup.command(
        name="server_tag",
        description="Enable or disable server-tag tracking and optional mention role.",
    )
    @app_commands.describe(
        enabled="Set to False to disable server-tag tracking entirely.",
        ask_to_select_role="Set True to be reminded to choose a role if none is provided.",
        role="Role that marks server-tagged members (optional).",
        pattern="Fallback text searched in nicknames/display names (optional).",
        mention_role="Role to mention when referencing server-tagged members (optional).",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_server_tag(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        ask_to_select_role: Optional[bool] = False,
        role: Optional[discord.Role] = None,
        pattern: Optional[str] = None,
        mention_role: Optional[discord.Role] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        if not enabled:
            config = self._save_settings(
                interaction.guild,
                interaction.user.id,
                {
                    "server_tag_enabled": False,
                    "server_tag_role_id": None,
                    "server_tag_role_name": None,
                    "server_tag_pattern": None,
                    "server_tag_mention_role_id": None,
                    "server_tag_mention_role_name": None,
                },
            )
            await interaction.followup.send(
                "Server-tag tracking disabled and related fields cleared.",
                ephemeral=True,
            )
            return

        if role is None and ask_to_select_role:
            await interaction.followup.send(
                "Please rerun `/setup server_tag` and choose a role to mark server-tagged members.",
                ephemeral=True,
            )
            return

        config = self._save_settings(
            interaction.guild,
            interaction.user.id,
            {
                "server_tag_enabled": True,
                "server_tag_role_id": role.id if role else None,
                "server_tag_role_name": role.name if role else None,
                "server_tag_pattern": (pattern or "").strip() or None,
                "server_tag_mention_role_id": mention_role.id if mention_role else None,
                "server_tag_mention_role_name": mention_role.name if mention_role else None,
            },
        )

        embed = discord.Embed(
            title="Server-tag settings updated",
            colour=discord.Colour.blurple(),
            timestamp=config.get("updated_at"),
        )
        embed.add_field(
            name="Tag role",
            value=role.mention if role else "Not set",
            inline=False,
        )
        embed.add_field(
            name="Pattern",
            value=f"`{pattern}`" if pattern else "Not set",
            inline=False,
        )
        embed.add_field(
            name="Mention role",
            value=mention_role.mention if mention_role else "Not set",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @setup.command(
        name="boosters",
        description="Enable or disable booster tracking and optional booster role.",
    )
    @app_commands.describe(
        enabled="Set to False to disable booster tracking.",
        ask_to_select_role="Set True to be reminded to choose a booster role if none is provided.",
        role="Role assigned to Nitro boosters (optional).",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_boosters(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        ask_to_select_role: Optional[bool] = False,
        role: Optional[discord.Role] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        if not enabled:
            config = self._save_settings(
                interaction.guild,
                interaction.user.id,
                {
                    "boosters_enabled": False,
                    "boosters_role_id": None,
                    "boosters_role_name": None,
                },
            )
            await interaction.followup.send(
                "Booster tracking disabled. Stored booster role cleared.", ephemeral=True
            )
            return

        if role is None and ask_to_select_role:
            await interaction.followup.send(
                "Please rerun `/setup boosters` and choose a role to assign boosters.",
                ephemeral=True,
            )
            return

        config = self._save_settings(
            interaction.guild,
            interaction.user.id,
            {
                "boosters_enabled": True,
                "boosters_role_id": role.id if role else None,
                "boosters_role_name": role.name if role else None,
            },
        )
        embed = discord.Embed(
            title="Booster settings updated",
            colour=discord.Colour.blurple(),
            timestamp=config.get("updated_at"),
            description=(
                f"Booster tracking enabled. Using role: {role.mention if role else 'None'}."
            ),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCommandsCog(bot))
