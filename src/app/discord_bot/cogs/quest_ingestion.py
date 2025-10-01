from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ..services import QuestIngestionService


class QuestIngestionCog(commands.Cog):
    """Discord Cog that forwards relevant events to the ingestion service."""

    def __init__(self, *, service: QuestIngestionService) -> None:
        self._service = service
        self._log = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self) -> None:  # pragma: no cover - simple log
        self._log.info("Quest ingestion cog ready")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._service.ingest_new_message(message)

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        await self._service.ingest_edited_message(before, after)

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        if payload.guild_id is None:
            return
        await self._service.cancel_from_delete(
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
        )
