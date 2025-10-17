from __future__ import annotations

import logging
from typing import Optional

import discord

from app.bot.config import DEMO_LOG_CHANNEL_ID


async def send_demo_log(bot: discord.Client, guild: discord.Guild, message: str) -> None:
    """Send a log message to the configured demo log channel, if any."""

    if not DEMO_LOG_CHANNEL_ID:
        return

    try:
        channel_id = int(DEMO_LOG_CHANNEL_ID)
    except (TypeError, ValueError):
        logging.warning("Invalid DEMO_LOG_CHANNEL_ID configured: %s", DEMO_LOG_CHANNEL_ID)
        return

    channel: Optional[discord.abc.Messageable] = guild.get_channel(channel_id)  # type: ignore[assignment]

    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except Exception as exc:  # pragma: no cover - best effort logging
            logging.warning(
                "Failed to fetch demo log channel %s in guild %s: %s",
                channel_id,
                guild.id,
                exc,
            )
            return

    try:
        await channel.send(message)
    except Exception as exc:  # pragma: no cover - best effort logging
        logging.warning(
            "Failed to send demo log message to channel %s in guild %s: %s",
            channel_id,
            guild.id,
            exc,
        )
