from __future__ import annotations

import logging
from typing import Optional

import discord

from app.bot.services import guild_settings_store


async def send_demo_log(bot: discord.Client, guild: discord.Guild, message: str) -> None:
    """Send a log message to the configured demo log channel, if any."""

    settings = guild_settings_store.fetch_settings(guild.id)
    if not settings:
        return

    channel_id = settings.get("log_channel_id")
    if channel_id is None:
        return

    try:
        channel_id_int = int(channel_id)
    except (TypeError, ValueError):
        logging.warning(
            "Invalid log_channel_id stored for guild %s: %s", guild.id, channel_id
        )
        return

    channel: Optional[discord.abc.Messageable] = guild.get_channel(channel_id_int)  # type: ignore[assignment]

    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id_int)
        except Exception as exc:  # pragma: no cover - best effort logging
            logging.warning(
                "Failed to fetch demo log channel %s in guild %s: %s",
                channel_id_int,
                guild.id,
                exc,
            )
            return

    try:
        await channel.send(message)
    except Exception as exc:  # pragma: no cover - best effort logging
        logging.warning(
            "Failed to send demo log message to channel %s in guild %s: %s",
            channel_id_int,
            guild.id,
            exc,
        )
