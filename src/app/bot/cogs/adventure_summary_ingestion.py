from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ..services.adventure_summary_ingestion import AdventureSummaryIngestionService


class AdventureSummaryIngestionCog(commands.Cog):
    """Cog that forwards summary-related events to the ingestion service."""

    def __init__(self, *, service: AdventureSummaryIngestionService) -> None:
        """Store the ingestion service used to persist summary updates."""
        self._service = service
        self._log = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self) -> None:  # pragma: no cover - log only
        """Log a confirmation when the cog is ready to receive events."""
        self._log.info("Adventure summary ingestion cog ready")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Forward new Discord messages to the ingestion service."""
        await self._service.ingest_new_message(message)

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Notify the service that a previously ingested message was edited."""
        await self._service.ingest_edited_message(before, after)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        """Reverse any ingestion side effects when a message is deleted."""
        if payload.guild_id is None:
            return
        await self._service.cancel_from_delete(
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
        )
