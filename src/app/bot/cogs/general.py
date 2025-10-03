from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt

from app.bot.ingestion import QuestRecord
from app.bot.ingestion.summaries_pipeline import (
    AdventureSummaryRecord,
    SummaryParticipantRecord,
)
from app.bot.services.guild_logging import GuildLoggingService
from app.bot.services.quest_lookup import (
    QuestLookupResult,
    QuestLookupService,
    SummaryLookupResult,
)


@runtime_checkable
class SupportsBotStatus(Protocol):
    """Protocol covering the attributes used by the general commands cog."""

    @property
    def latency(self) -> float: ...

    def is_ready(self) -> bool: ...

    @property
    def user(self) -> object | None: ...


class GeneralCog(commands.Cog):
    quest_info = app_commands.Group(
        name="quest-info",
        description="Look up quest announcements and summaries.",
    )
    """General utility commands for quickly checking bot health."""

    def __init__(
        self,
        bot: SupportsBotStatus,
        *,
        logging_service: GuildLoggingService,
        lookup_service: QuestLookupService,
    ) -> None:
        """Attach the Discord bot instance used for health checks."""
        super().__init__()
        self.bot = bot
        self._logging = logging_service
        self._lookup = lookup_service
        self._log = logging.getLogger(__name__)
        self._quest_info_guild: discord.abc.Snowflake | None = None

        if isinstance(bot, commands.Bot):
            guild_id = getattr(getattr(bot, "_config", None), "guild_id", None)
            if guild_id is not None:
                self._quest_info_guild = discord.Object(id=guild_id)
            bot.tree.add_command(
                self.quest_info,
                guild=self._quest_info_guild,
                override=True,
            )
            self._log.debug(
                "Registered quest-info slash command group",
                extra={"guild_id": getattr(self._quest_info_guild, "id", None)},
            )
        else:  # pragma: no cover - used by lightweight test doubles
            self._log.debug(
                "Quest-info command group not registered; bot lacks command tree",
                extra={"bot_type": type(bot).__name__},
            )

    def build_latency_message(self) -> str:
        """Return a human-readable websocket latency string."""
        latency_ms = round(self.bot.latency * 1000)
        return f"Pong! Websocket latency: {latency_ms} ms"

    def build_status_embed(self) -> discord.Embed:
        """Construct an embed describing latency and ready state."""
        latency_ms = round(self.bot.latency * 1000)
        try:
            ready = self.bot.is_ready()
        except Exception:  # pragma: no cover - defensive
            ready = False
        colour = discord.Color.green() if ready else discord.Color.orange()
        description = "Basic health information for the Nonagon Discord bot."
        embed = discord.Embed(
            title="Bot status", description=description, colour=colour
        )
        embed.add_field(name="Websocket latency", value=f"{latency_ms} ms", inline=True)
        embed.add_field(
            name="Ready state",
            value="Ready ✅" if ready else "Starting ⏳",
            inline=True,
        )
        user = getattr(self.bot, "user", None)
        if user is not None:
            embed.set_footer(text=f"Logged in as {user}")
        return embed

    def build_quest_lookup_embed(
        self,
        quest: QuestRecord,
        summaries: Sequence[AdventureSummaryRecord],
    ) -> discord.Embed:
        """Render quest metadata along with linked summaries."""

        description = quest.description_md.strip() if quest.description_md else ""
        embed = discord.Embed(
            title=quest.title,
            description=self._truncate(description or "(no description provided)"),
            colour=discord.Color.blurple(),
            url=str(quest.event_url),
        )
        embed.add_field(name="Quest ID", value=quest.quest_id, inline=True)
        embed.add_field(
            name="Channel", value=f"<#{quest.discord_channel_id}>", inline=True
        )
        embed.add_field(
            name="Message",
            value=self._quest_message_link(quest),
            inline=False,
        )
        embed.add_field(
            name="Referee",
            value=self._format_discord_id(quest.referee_discord_id),
            inline=True,
        )
        embed.add_field(
            name="Starts",
            value=self._format_schedule(quest.starts_at_utc),
            inline=True,
        )
        embed.add_field(
            name="Duration",
            value=f"{quest.duration_minutes} minutes",
            inline=True,
        )
        embed.add_field(
            name="Tags",
            value=self._format_tags(quest.tags),
            inline=False,
        )
        embed.add_field(
            name="My Table",
            value=str(quest.my_table_url),
            inline=False,
        )
        summaries_value = self._format_summary_links(summaries)
        embed.add_field(name="Summaries", value=summaries_value, inline=False)
        if quest.image_url:
            embed.set_thumbnail(url=quest.image_url)
        embed.set_footer(text=f"Channel ID {quest.discord_channel_id}")
        return embed

    def build_summary_lookup_embed(
        self,
        summary: AdventureSummaryRecord,
        quest: QuestRecord | None,
        siblings: Sequence[AdventureSummaryRecord],
    ) -> discord.Embed:
        """Render summary details with quest linkage context."""

        primary_text = summary.short_summary_md or summary.content_md
        embed = discord.Embed(
            title=summary.title or "Adventure Summary",
            description=self._truncate(primary_text or "(summary content missing)"),
            colour=discord.Color.dark_teal(),
            url=self._summary_message_link(summary),
        )
        embed.add_field(name="Summary ID", value=summary.summary_id, inline=True)
        embed.add_field(
            name="Kind",
            value=f"{summary.kind} — {'IC' if summary.in_character else 'OOC'}",
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=self._format_schedule(summary.created_at),
            inline=True,
        )
        if summary.updated_at and summary.updated_at != summary.created_at:
            embed.add_field(
                name="Updated",
                value=self._format_schedule(summary.updated_at),
                inline=True,
            )

        quest_field = "(quest unresolved)"
        if quest is not None:
            quest_field = f"[{quest.quest_id}]({self._quest_message_link(quest)})"
        elif summary.quest_id:
            quest_field = summary.quest_id
        embed.add_field(name="Quest", value=quest_field, inline=False)

        embed.add_field(
            name="Summary Message",
            value=self._summary_message_link(summary),
            inline=False,
        )

        embed.add_field(
            name="Author",
            value=self._format_discord_id(summary.author_discord_id),
            inline=True,
        )
        embed.add_field(
            name="DM",
            value=self._format_discord_id(summary.dm_discord_id),
            inline=True,
        )

        embed.add_field(
            name="Participants",
            value=self._format_participants(summary.players),
            inline=False,
        )

        if summary.related_links:
            links_text = "\n".join(summary.related_links[:5])
            if len(summary.related_links) > 5:
                links_text += f"\n… {len(summary.related_links) - 5} more"
            embed.add_field(name="Related Links", value=links_text, inline=False)

        siblings_text = self._format_sibling_summaries(summary.summary_id, siblings)
        if siblings_text:
            embed.add_field(
                name="Other Summaries for this Quest",
                value=siblings_text,
                inline=False,
            )

        embed.set_footer(text=f"Channel ID {summary.discord_channel_id}")
        return embed

    def _truncate(self, text: str, limit: int = 1024) -> str:
        cleaned = text.strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"

    def _quest_message_link(self, quest: QuestRecord) -> str:
        if not (
            quest.discord_guild_id
            and quest.discord_channel_id
            and quest.discord_message_id
        ):
            return "(link unavailable)"
        url = (
            f"https://discord.com/channels/{quest.discord_guild_id}/"
            f"{quest.discord_channel_id}/{quest.discord_message_id}"
        )
        return f"[View post]({url})"

    def _summary_message_link(self, summary: AdventureSummaryRecord) -> str:
        message_id = None
        if summary.summary_message_ids:
            message_id = summary.summary_message_ids[0]
        elif summary.parent_message_id:
            message_id = summary.parent_message_id
        if not (summary.discord_guild_id and summary.discord_channel_id and message_id):
            return "(link unavailable)"
        url = (
            f"https://discord.com/channels/{summary.discord_guild_id}/"
            f"{summary.discord_channel_id}/{message_id}"
        )
        return f"[View summary]({url})"

    def _format_schedule(self, timestamp: datetime | None) -> str:
        if timestamp is None:
            return "(unknown)"
        try:
            return f"{format_dt(timestamp, 'F')} ({format_dt(timestamp, 'R')})"
        except Exception:  # pragma: no cover - defensive formatting
            return timestamp.isoformat()

    def _format_discord_id(self, discord_id: str | None) -> str:
        if not discord_id:
            return "(not provided)"
        if discord_id.isdigit():
            return f"<@{discord_id}>"
        return discord_id

    def _format_tags(self, tags: Sequence[str]) -> str:
        if not tags:
            return "(none)"
        formatted = ", ".join(f"`{tag}`" for tag in tags[:10])
        if len(tags) > 10:
            formatted += f" +{len(tags) - 10} more"
        return formatted

    def _format_summary_links(self, summaries: Sequence[AdventureSummaryRecord]) -> str:
        if not summaries:
            return "No summaries recorded yet."
        lines: list[str] = []
        for summary in summaries[:5]:
            title = summary.title or "Untitled summary"
            snippet = self._truncate(title, limit=80)
            lines.append(
                f"[{summary.summary_id}]({self._summary_message_link(summary)}) — {snippet}"
            )
        if len(summaries) > 5:
            lines.append(f"… {len(summaries) - 5} more")
        return "\n".join(lines)

    def _format_participants(
        self, participants: Sequence[SummaryParticipantRecord]
    ) -> str:
        if not participants:
            return "(not provided)"
        lines: list[str] = []
        for participant in participants[:5]:
            mention = self._format_discord_id(participant.discord_id)
            display = participant.display_name or mention
            if participant.display_name and participant.discord_id:
                lines.append(f"{mention} ({participant.display_name})")
            else:
                lines.append(display)
        if len(participants) > 5:
            lines.append(f"… {len(participants) - 5} more")
        return "\n".join(lines)

    def _format_sibling_summaries(
        self,
        summary_id: str,
        siblings: Sequence[AdventureSummaryRecord],
    ) -> str | None:
        lines: list[str] = []
        for sibling in siblings:
            if sibling.summary_id == summary_id:
                continue
            lines.append(
                f"[{sibling.summary_id}]({self._summary_message_link(sibling)})"
            )
        if not lines:
            return None
        rendered = lines[:5]
        output = "\n".join(rendered)
        if len(lines) > 5:
            output += f"\n… {len(lines) - 5} more"
        return output

    @commands.command(name="ping")
    async def command_ping_prefix(self, ctx: commands.Context[commands.Bot]) -> None:
        """Prefix command to check websocket latency."""
        message = self.build_latency_message()
        await ctx.reply(message)
        await self._log_command_usage(
            guild=getattr(ctx, "guild", None),
            channel=getattr(ctx, "channel", None),
            actor=getattr(ctx, "author", None),
            command="!ping",
            detail=message,
        )

    @app_commands.command(
        name="ping",
        description="Check that the Nonagon bot is responding and view latency.",
    )
    async def command_ping_slash(self, interaction: discord.Interaction) -> None:
        """Slash command variant of ping that responds ephemerally."""
        message = self.build_latency_message()
        await interaction.response.send_message(message, ephemeral=True)
        await self._log_command_usage(
            guild=interaction.guild,
            channel=interaction.channel,
            actor=interaction.user,
            command="/ping",
            detail=message,
        )

    @commands.command(name="pingstatus")
    async def command_pingstatus_prefix(
        self, ctx: commands.Context[commands.Bot]
    ) -> None:
        """Prefix command returning a richer status embed."""
        embed = self.build_status_embed()
        await ctx.reply(embed=embed)
        await self._log_command_usage(
            guild=getattr(ctx, "guild", None),
            channel=getattr(ctx, "channel", None),
            actor=getattr(ctx, "author", None),
            command="!pingstatus",
            detail="Status embed sent",
        )

    @app_commands.command(
        name="pingstatus",
        description="Show the bot's readiness state and websocket latency.",
    )
    async def command_pingstatus_slash(self, interaction: discord.Interaction) -> None:
        """Slash command that provides a richer status embed."""
        embed = self.build_status_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._log_command_usage(
            guild=interaction.guild,
            channel=interaction.channel,
            actor=interaction.user,
            command="/pingstatus",
            detail="Status embed sent",
        )

    @quest_info.command(name="quest")
    @app_commands.describe(
        identifier="Quest ID (e.g. QUES1234) or quest message link",
    )
    @app_commands.guild_only()
    async def command_quest_lookup(
        self, interaction: discord.Interaction, identifier: str
    ) -> None:
        """Provide quest metadata and linked summaries for moderators."""

        await interaction.response.defer(ephemeral=True, thinking=True)
        normalized = identifier.strip()
        if not normalized:
            message = (
                "Please supply a quest ID (e.g. QUES1234) or a quest message link."
            )
            await interaction.followup.send(message, ephemeral=True)
            await self._log_command_usage(
                guild=interaction.guild,
                channel=interaction.channel,
                actor=interaction.user,
                command="/quest-info quest",
                detail="Quest lookup missing identifier",
            )
            return

        try:
            result: QuestLookupResult | None = await self._lookup.fetch_quest(
                normalized
            )
        except Exception:  # pragma: no cover - defensive logging
            self._log.exception("Quest lookup failed", extra={"identifier": normalized})
            await interaction.followup.send(
                "Sorry, something went wrong while looking up that quest.",
                ephemeral=True,
            )
            await self._log_command_usage(
                guild=interaction.guild,
                channel=interaction.channel,
                actor=interaction.user,
                command="/quest-info quest",
                detail=f"Quest lookup error: {normalized}",
            )
            return

        if result is None:
            await interaction.followup.send(
                "Couldn't find a quest for that identifier. Double-check the quest ID or link.",
                ephemeral=True,
            )
            await self._log_command_usage(
                guild=interaction.guild,
                channel=interaction.channel,
                actor=interaction.user,
                command="/quest-info quest",
                detail=f"Quest not found: {normalized}",
            )
            return

        embed = self.build_quest_lookup_embed(result.quest, result.summaries)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await self._log_command_usage(
            guild=interaction.guild,
            channel=interaction.channel,
            actor=interaction.user,
            command="/quest-info quest",
            detail=f"Quest {result.quest.quest_id}",
        )

    @quest_info.command(name="summary")
    @app_commands.describe(
        identifier="Summary ID (e.g. SUMM1234) or summary message link",
    )
    @app_commands.guild_only()
    async def command_summary_lookup(
        self, interaction: discord.Interaction, identifier: str
    ) -> None:
        """Display summary details plus quest context."""

        await interaction.response.defer(ephemeral=True, thinking=True)
        normalized = identifier.strip()
        if not normalized:
            message = (
                "Please supply a summary ID (e.g. SUMM1234) or a summary message link."
            )
            await interaction.followup.send(message, ephemeral=True)
            await self._log_command_usage(
                guild=interaction.guild,
                channel=interaction.channel,
                actor=interaction.user,
                command="/quest-info summary",
                detail="Summary lookup missing identifier",
            )
            return

        try:
            result_summary: SummaryLookupResult | None = (
                await self._lookup.fetch_summary(normalized)
            )
        except Exception:  # pragma: no cover - defensive logging
            self._log.exception(
                "Summary lookup failed", extra={"identifier": normalized}
            )
            await interaction.followup.send(
                "Sorry, something went wrong while looking up that summary.",
                ephemeral=True,
            )
            await self._log_command_usage(
                guild=interaction.guild,
                channel=interaction.channel,
                actor=interaction.user,
                command="/quest-info summary",
                detail=f"Summary lookup error: {normalized}",
            )
            return

        if result_summary is None:
            await interaction.followup.send(
                "Couldn't find a summary for that identifier. Double-check the summary ID or link.",
                ephemeral=True,
            )
            await self._log_command_usage(
                guild=interaction.guild,
                channel=interaction.channel,
                actor=interaction.user,
                command="/quest-info summary",
                detail=f"Summary not found: {normalized}",
            )
            return

        embed = self.build_summary_lookup_embed(
            result_summary.summary,
            result_summary.quest,
            result_summary.related_summaries,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        await self._log_command_usage(
            guild=interaction.guild,
            channel=interaction.channel,
            actor=interaction.user,
            command="/quest-info summary",
            detail=f"Summary {result_summary.summary.summary_id}",
        )

    async def _log_command_usage(
        self,
        *,
        guild: discord.Guild | None,
        channel: object | None,
        actor: discord.abc.User | None,
        command: str,
        detail: str | None = None,
    ) -> None:
        if guild is None or actor is None:
            return
        fields: list[tuple[str, str]] = [
            ("Command", command),
            ("Actor", getattr(actor, "mention", str(actor))),
        ]
        if channel and getattr(channel, "guild", None) is guild:
            channel_repr = getattr(channel, "mention", str(channel))
            fields.append(("Channel", channel_repr))
        if detail:
            trimmed = detail if len(detail) <= 1024 else detail[:1021] + "…"
            fields.append(("Detail", trimmed))
        await self._logging.log_event(
            guild.id,
            title="Command executed",
            fields=fields,
            extra={"command": command},
        )

    async def cog_unload(self) -> None:
        if not isinstance(
            self.bot, commands.Bot
        ):  # pragma: no cover - defensive for tests
            return
        try:
            self.bot.tree.remove_command(
                self.quest_info.name,
                type=discord.AppCommandType.chat_input,
                guild=self._quest_info_guild,
            )
        except KeyError:  # pragma: no cover - defensive cleanup
            pass
