from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ..services import QuestIngestionService


class QuestIngestionCog(commands.Cog):
    """Discord Cog that forwards relevant events to the ingestion service."""

    def __init__(self, *, service: QuestIngestionService) -> None:
        """Keep a reference to the quest ingestion service."""
        self._service = service
        self._log = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self) -> None:  # pragma: no cover - simple log
        """Log when the cog is ready to ingest quest messages."""
        self._log.info("Quest ingestion cog ready")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Pass through any new message to the ingestion service."""
        await self._service.ingest_new_message(message)

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Update the stored quest record when a message changes."""
        await self._service.ingest_edited_message(before, after)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        """Remove quest data if the originating Discord message was deleted."""
        if payload.guild_id is None:
            return
        await self._service.cancel_from_delete(
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
        )
