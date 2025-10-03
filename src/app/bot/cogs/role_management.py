from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import discord
from discord.ext import commands

from app.bot.config import DiscordBotConfig
from app.bot.services.guild_logging import GuildLoggingService
from app.bot.services.role_management import (
    PlayerRoleResult,
    PlayerRoleStatus,
    RefereeRoleResult,
    RefereeRoleStatus,
    RoleManagementService,
)
from app.domain.models.user.UserModel import User


@dataclass(slots=True)
class DiscordRoleSync:
    """Outcome of attempting to align a Discord role with domain expectations."""

    applied: bool
    message: str | None = None
    error: bool = False


class RoleManagementCog(commands.Cog):
    """Administrative commands for player and referee roles."""

    def __init__(
        self,
        *,
        service: RoleManagementService,
        config: DiscordBotConfig,
        logging_service: GuildLoggingService,
    ) -> None:
        """Store the role management service and Discord configuration."""
        self._service = service
        self._config = config
        self._logging = logging_service
        self._log = logging.getLogger(__name__)

    @commands.hybrid_command(
        name="player-grant", description="Grant the player role to a member."
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def player_grant(
        self, ctx: commands.Context[commands.Bot], member: discord.Member
    ) -> None:
        """Hybrid command entrypoint for granting the player role."""
        await self._handle_player_command(ctx, member, grant=True)

    @commands.hybrid_command(
        name="player-revoke", description="Remove the player role from a member."
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def player_revoke(
        self, ctx: commands.Context[commands.Bot], member: discord.Member
    ) -> None:
        """Hybrid command entrypoint for revoking the player role."""
        await self._handle_player_command(ctx, member, grant=False)

    @commands.hybrid_command(
        name="referee-grant", description="Grant the referee role to a member."
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def referee_grant(
        self, ctx: commands.Context[commands.Bot], member: discord.Member
    ) -> None:
        """Hybrid command entrypoint for granting the referee role."""
        await self._handle_referee_command(ctx, member, grant=True)

    @commands.hybrid_command(
        name="referee-revoke", description="Remove the referee role from a member."
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def referee_revoke(
        self, ctx: commands.Context[commands.Bot], member: discord.Member
    ) -> None:
        """Hybrid command entrypoint for revoking the referee role."""
        await self._handle_referee_command(ctx, member, grant=False)

    async def _handle_player_command(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        *,
        grant: bool,
    ) -> None:
        """Resolve the player role command, syncing Discord state and building feedback embeds."""
        guild = ctx.guild
        command_name = "player-grant" if grant else "player-revoke"
        if guild is None:
            embed = self._error_embed(
                "Guild only", "This command can only be used in a server."
            )
            await self._send_embed(ctx, embed)
            return

        result: PlayerRoleResult | None = None
        sync: DiscordRoleSync | None = None

        if member.bot:
            embed = self._error_embed(
                "Unsupported member", "Bots cannot be managed by this command."
            )
            await self._send_embed_with_log(
                ctx,
                embed,
                guild=guild,
                command_name=command_name,
                actor=ctx.author,
                target=member,
                extra_fields=[("Result", "Blocked: bot member")],
            )
            return

        player_role = self._resolve_role(guild, self._config.player_role_id)
        if player_role is None:
            embed = self._error_embed(
                "Missing player role",
                f"Could not find a Discord role with ID `{self._config.player_role_id}`.",
            )
            await self._send_embed_with_log(
                ctx,
                embed,
                guild=guild,
                command_name=command_name,
                actor=ctx.author,
                target=member,
                extra_fields=[("Result", "Configuration error")],
            )
            return

        try:
            if grant:
                result = await self._service.grant_player(member)
                sync = await self._ensure_role_state(
                    member,
                    player_role,
                    should_have=True,
                    reason=f"Player grant requested by {ctx.author}",
                )
                embed = self._player_grant_embed(result, ctx.author, member, sync)
            else:
                result = await self._service.revoke_player(member)
                if result.status is PlayerRoleStatus.BLOCKED_REFEREE:
                    embed = self._player_blocked_embed(result, ctx.author, member)
                    await self._send_embed_with_log(
                        ctx,
                        embed,
                        guild=guild,
                        command_name=command_name,
                        actor=ctx.author,
                        target=member,
                        extra_fields=[
                            ("Result", self._format_status(result.status)),
                            (
                                "Domain roles",
                                self._domain_roles_summary(result.user),
                            ),
                        ],
                    )
                    return
                sync = await self._ensure_role_state(
                    member,
                    player_role,
                    should_have=False,
                    reason=f"Player revoke requested by {ctx.author}",
                )
                embed = self._player_revoke_embed(result, ctx.author, member, sync)
        except ValueError as exc:
            self._log.warning("Player command failed", exc_info=exc)
            embed = self._error_embed(
                "Provisioning failed", "Unable to provision member for role management."
            )

        status_label = (
            self._format_status(result.status)
            if result is not None
            else "Provisioning error"
        )
        log_fields: list[tuple[str, str]] = [("Result", status_label)]
        if result is not None:
            log_fields.append(("Domain roles", self._domain_roles_summary(result.user)))
        if sync is not None:
            log_fields.append(
                (
                    "Discord sync",
                    self._format_sync(
                        "Player role",
                        sync,
                        should_have=grant,
                    ),
                )
            )

        await self._send_embed_with_log(
            ctx,
            embed,
            guild=guild,
            command_name=command_name,
            actor=ctx.author,
            target=member,
            extra_fields=log_fields,
        )

    async def _handle_referee_command(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        *,
        grant: bool,
    ) -> None:
        """Resolve the referee role command, ensuring both player/referee roles align with domain state."""
        guild = ctx.guild
        command_name = "referee-grant" if grant else "referee-revoke"
        if guild is None:
            embed = self._error_embed(
                "Guild only", "This command can only be used in a server."
            )
            await self._send_embed(ctx, embed)
            return

        result: RefereeRoleResult | None = None
        sync_player: DiscordRoleSync | None = None
        sync_referee: DiscordRoleSync | None = None

        if member.bot:
            embed = self._error_embed(
                "Unsupported member", "Bots cannot be managed by this command."
            )
            await self._send_embed_with_log(
                ctx,
                embed,
                guild=guild,
                command_name=command_name,
                actor=ctx.author,
                target=member,
                extra_fields=[("Result", "Blocked: bot member")],
            )
            return

        player_role = self._resolve_role(guild, self._config.player_role_id)
        referee_role = self._resolve_role(guild, self._config.referee_role_id)
        if player_role is None or referee_role is None:
            missing: list[str] = []
            if player_role is None:
                missing.append(f"player (`{self._config.player_role_id}`)")
            if referee_role is None:
                missing.append(f"referee (`{self._config.referee_role_id}`)")
            embed = self._error_embed(
                "Missing roles",
                "Unable to locate Discord roles: " + ", ".join(missing) + ".",
            )
            await self._send_embed_with_log(
                ctx,
                embed,
                guild=guild,
                command_name=command_name,
                actor=ctx.author,
                target=member,
                extra_fields=[("Result", "Configuration error")],
            )
            return

        try:
            if grant:
                result = await self._service.grant_referee(member)
                sync_player = await self._ensure_role_state(
                    member,
                    player_role,
                    should_have=True,
                    reason=f"Player role ensured by referee grant ({ctx.author})",
                )
                sync_referee = await self._ensure_role_state(
                    member,
                    referee_role,
                    should_have=True,
                    reason=f"Referee grant requested by {ctx.author}",
                )
                embed = self._referee_grant_embed(
                    result, ctx.author, member, sync_player, sync_referee
                )
            else:
                result = await self._service.revoke_referee(member)
                sync_referee = await self._ensure_role_state(
                    member,
                    referee_role,
                    should_have=False,
                    reason=f"Referee revoke requested by {ctx.author}",
                )
                embed = self._referee_revoke_embed(
                    result, ctx.author, member, sync_referee
                )
        except ValueError as exc:
            self._log.warning("Referee command failed", exc_info=exc)
            embed = self._error_embed(
                "Provisioning failed", "Unable to provision member for role management."
            )

        status_label = (
            self._format_status(result.status)
            if result is not None
            else "Provisioning error"
        )
        log_fields: list[tuple[str, str]] = [("Result", status_label)]
        if result is not None:
            log_fields.append(("Domain roles", self._domain_roles_summary(result.user)))
        if sync_player is not None:
            log_fields.append(
                (
                    "Player sync",
                    self._format_sync(
                        "Player role",
                        sync_player,
                        should_have=True,
                    ),
                )
            )
        if sync_referee is not None:
            log_fields.append(
                (
                    "Referee sync",
                    self._format_sync(
                        "Referee role",
                        sync_referee,
                        should_have=grant,
                    ),
                )
            )

        await self._send_embed_with_log(
            ctx,
            embed,
            guild=guild,
            command_name=command_name,
            actor=ctx.author,
            target=member,
            extra_fields=log_fields,
        )

    async def _ensure_role_state(
        self,
        member: discord.Member,
        role: discord.Role,
        *,
        should_have: bool,
        reason: str,
    ) -> DiscordRoleSync:
        """Ensure a member's Discord role matches the desired state and report the action."""
        has_role = role in member.roles
        if should_have and has_role:
            return DiscordRoleSync(applied=False, message="Role already present")
        if not should_have and not has_role:
            return DiscordRoleSync(applied=False, message="Role already absent")
        try:
            if should_have:
                await member.add_roles(role, reason=reason)
            else:
                await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            return DiscordRoleSync(
                applied=False,
                message="Bot lacks permission to modify roles.",
                error=True,
            )
        except discord.HTTPException as exc:
            return DiscordRoleSync(
                applied=False, message=f"Discord error: {exc}", error=True
            )
        return DiscordRoleSync(applied=True)

    async def _send_embed_with_log(
        self,
        ctx: commands.Context[commands.Bot],
        embed: discord.Embed,
        *,
        guild: discord.Guild,
        command_name: str,
        actor: discord.abc.User,
        target: discord.abc.User,
        extra_fields: list[tuple[str, str]] | None = None,
    ) -> None:
        await self._send_embed(ctx, embed)
        channel = getattr(ctx, "channel", None)
        fields: list[tuple[str, str]] = [("Outcome", embed.title or "Command result")]
        if embed.description:
            fields.append(("Description", self._truncate_field(embed.description)))
        if extra_fields:
            fields.extend(
                (name, self._truncate_field(value)) for name, value in extra_fields
            )
        await self._log_role_action(
            guild=guild,
            channel=channel,
            actor=actor,
            command=command_name,
            target=target,
            fields=fields,
        )

    async def _log_role_action(
        self,
        *,
        guild: discord.Guild,
        channel: object | None,
        actor: discord.abc.User,
        command: str,
        target: discord.abc.User,
        fields: list[tuple[str, str]],
    ) -> None:
        base_fields: list[tuple[str, str]] = [
            ("Command", command),
            ("Actor", getattr(actor, "mention", str(actor))),
            ("Target", getattr(target, "mention", str(target))),
        ]
        if channel and getattr(channel, "guild", None) is guild:
            channel_repr = getattr(channel, "mention", str(channel))
            base_fields.append(("Channel", channel_repr))
        base_fields.extend(fields)
        await self._logging.log_event(
            guild.id,
            title="Role command executed",
            fields=tuple(base_fields),
            extra={"command": command},
        )

    @staticmethod
    def _format_status(status: Enum) -> str:
        return status.name.replace("_", " ").title()

    @staticmethod
    def _domain_roles_summary(user: User) -> str:
        roles = ", ".join(role.value for role in user.roles)
        return roles or "None"

    @staticmethod
    def _truncate_field(value: str) -> str:
        return value if len(value) <= 1024 else value[:1021] + "…"

    def _player_grant_embed(
        self,
        result: PlayerRoleResult,
        actor: discord.abc.User,
        member: discord.Member,
        sync: DiscordRoleSync,
    ) -> discord.Embed:
        """Build an embed summarizing the outcome of a player-role grant."""
        if result.status is PlayerRoleStatus.PROMOTED:
            title = "Player access granted"
            description = f"{member.mention} can now create characters."
            color = discord.Color.green()
        else:
            title = "No change"
            description = f"{member.mention} already had player access."
            color = discord.Color.blurple()
        return self._build_embed(
            title=title,
            description=description,
            color=color,
            domain_user=result.user,
            actor=actor,
            member=member,
            discord_summary=self._format_sync("Player role", sync, should_have=True),
        )

    def _player_revoke_embed(
        self,
        result: PlayerRoleResult,
        actor: discord.abc.User,
        member: discord.Member,
        sync: DiscordRoleSync,
    ) -> discord.Embed:
        """Build an embed summarizing the outcome of a player-role revocation."""
        if result.status is PlayerRoleStatus.DEMOTED:
            title = "Player access revoked"
            description = f"{member.mention} has been returned to member status."
            color = discord.Color.orange()
        else:
            title = "No change"
            description = f"{member.mention} was not a player."
            color = discord.Color.blurple()
        return self._build_embed(
            title=title,
            description=description,
            color=color,
            domain_user=result.user,
            actor=actor,
            member=member,
            discord_summary=self._format_sync("Player role", sync, should_have=False),
        )

    def _player_blocked_embed(
        self,
        result: PlayerRoleResult,
        actor: discord.abc.User,
        member: discord.Member,
    ) -> discord.Embed:
        """Explain why a player revoke was blocked due to lingering referee permissions."""
        description = f"{member.mention} still has the referee role. Remove it before revoking player access."
        return self._build_embed(
            title="Player revoke blocked",
            description=description,
            color=discord.Color.red(),
            domain_user=result.user,
            actor=actor,
            member=member,
            discord_summary="• Player role: ℹ️ Not changed\n• Referee role: ⚠️ Still assigned",
        )

    def _referee_grant_embed(
        self,
        result: RefereeRoleResult,
        actor: discord.abc.User,
        member: discord.Member,
        sync_player: DiscordRoleSync,
        sync_referee: DiscordRoleSync,
    ) -> discord.Embed:
        """Build an embed summarizing the outcome of a referee-role grant."""
        if result.status is RefereeRoleStatus.PROMOTED:
            title = "Referee privileges granted"
            description = f"{member.mention} can now post quests and summaries."
            color = discord.Color.green()
        else:
            title = "No change"
            description = f"{member.mention} already had referee privileges."
            color = discord.Color.blurple()
        summary = "\n".join(
            [
                self._format_sync("Player role", sync_player, should_have=True),
                self._format_sync("Referee role", sync_referee, should_have=True),
            ]
        )
        return self._build_embed(
            title=title,
            description=description,
            color=color,
            domain_user=result.user,
            actor=actor,
            member=member,
            discord_summary=summary,
        )

    def _referee_revoke_embed(
        self,
        result: RefereeRoleResult,
        actor: discord.abc.User,
        member: discord.Member,
        sync_referee: DiscordRoleSync,
    ) -> discord.Embed:
        """Build an embed summarizing the outcome of a referee-role revocation."""
        if result.status is RefereeRoleStatus.DEMOTED:
            title = "Referee privileges revoked"
            description = f"{member.mention} can no longer post quests or summaries."
            color = discord.Color.orange()
        else:
            title = "No change"
            description = f"{member.mention} was not a referee."
            color = discord.Color.blurple()
        return self._build_embed(
            title=title,
            description=description,
            color=color,
            domain_user=result.user,
            actor=actor,
            member=member,
            discord_summary=self._format_sync(
                "Referee role", sync_referee, should_have=False
            ),
        )

    def _format_sync(
        self,
        label: str,
        sync: DiscordRoleSync,
        *,
        should_have: bool,
    ) -> str:
        """Summarize how a role sync operation behaved for display in embeds."""
        if sync.error:
            return f"• {label}: ⚠️ {sync.message or 'Discord error'}"
        if sync.applied:
            action = "assigned" if should_have else "removed"
            return f"• {label}: ✅ {action}"
        note = sync.message or ("already assigned" if should_have else "already absent")
        return f"• {label}: ℹ️ {note}"

    def _build_embed(
        self,
        *,
        title: str,
        description: str,
        color: discord.Color,
        domain_user: User,
        actor: discord.abc.User,
        member: discord.Member,
        discord_summary: str,
    ) -> discord.Embed:
        """Create a standardized role management embed with domain and Discord context."""
        embed = discord.Embed(title=title, description=description, color=color)
        embed.add_field(name="User ID", value=str(domain_user.user_id), inline=False)
        roles = ", ".join(role.value for role in domain_user.roles) or "None"
        embed.add_field(name="Domain roles", value=roles, inline=False)
        embed.add_field(name="Discord sync", value=discord_summary, inline=False)
        embed.set_footer(text=f"Requested by {actor}")
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        return embed

    def _error_embed(self, title: str, description: str) -> discord.Embed:
        """Return a red embed conveying an administrative error."""
        return discord.Embed(
            title=title, description=description, color=discord.Color.red()
        )

    async def _send_embed(
        self, ctx: commands.Context[commands.Bot], embed: discord.Embed
    ) -> None:
        """Send an embed to the invoking context, logging failures defensively."""
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException as exc:  # pragma: no cover - defensive
            self._log.error("Failed to send embed", exc_info=exc)

    def _resolve_role(
        self, guild: discord.Guild, role_id: int | None
    ) -> discord.Role | None:
        """Look up a configured Discord role, tolerating missing IDs."""
        if role_id is None:
            return None
        return guild.get_role(role_id)
