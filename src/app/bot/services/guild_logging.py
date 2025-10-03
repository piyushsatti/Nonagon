from __future__ import annotations

import logging
from typing import Iterable, Mapping, Sequence

import discord
from discord.ext import commands


class GuildLoggingService:
    """Dispatch structured bot events to configured per-guild log channels."""

    def __init__(self) -> None:
        self._bot: commands.Bot | None = None
        self._guild_channels: dict[int, int | None] = {}
        self._log = logging.getLogger(__name__)

    def attach_bot(self, bot: commands.Bot) -> None:
        """Store a bot instance for later message dispatch."""
        self._bot = bot

    def update_configuration(
        self, guild_id: int, *, log_channel_id: int | None
    ) -> None:
        self._guild_channels[guild_id] = log_channel_id

    async def log_event(
        self,
        guild_id: int,
        *,
        title: str,
        description: str | None = None,
        fields: Sequence[tuple[str, str]] | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """Send an embed describing an event to the configured logging channel."""
        channel_id = self._guild_channels.get(guild_id)
        if not channel_id:
            return
        bot = self._bot
        if bot is None:
            self._log.debug(
                "Skipping guild log: bot not attached",
                extra={"guild_id": guild_id, **(extra or {})},
            )
            return
        channel = self._resolve_channel(bot, channel_id)
        if not isinstance(channel, discord.TextChannel):
            self._log.debug(
                "Skipping guild log: channel unavailable",
                extra={
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    **(extra or {}),
                },
            )
            return
        embed = discord.Embed(
            title=title, description=description, color=discord.Color.blurple()
        )
        for name, value in self._iter_fields(fields):
            embed.add_field(name=name, value=value, inline=False)
        try:
            await channel.send(embed=embed)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log.warning(
                "Failed to publish guild log",
                exc_info=exc,
                extra={
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    **(extra or {}),
                },
            )

    def _resolve_channel(
        self, bot: commands.Bot, channel_id: int
    ) -> discord.TextChannel | None:
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        for guild in bot.guilds:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
        return None

    def _iter_fields(
        self, fields: Sequence[tuple[str, str]] | None
    ) -> Iterable[tuple[str, str]]:
        if not fields:
            return ()
        return fields
