from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..ingestion import (
    DiscordMessageKey,
    ParseError,
    ValidationError,
    map_parsed_to_record,
    parse_message,
    validate,
)

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from app.infra.ids.service import IdService
    from app.infra.mongo.quest_records_repo import QuestRecordsRepository


class QuestIngestionService:
    """Coordinates Discord quest events with parsing, validation, and persistence."""

    def __init__(
        self,
        *,
        repo: "QuestRecordsRepository",
        id_service: "IdService",
        quest_channel_id: int,
        referee_role_id: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repo
        self._id_service = id_service
        self._quest_channel_id = quest_channel_id
        self._referee_role_id = referee_role_id
        self._log = logger or logging.getLogger(__name__)

    async def ingest_new_message(self, message: discord.Message) -> None:
        if not self._should_process(message):
            return

        guild = message.guild
        assert guild is not None
        key = DiscordMessageKey.from_ids(guild.id, message.channel.id, message.id)
        try:
            parsed = parse_message(
                raw=message.content,
                referee_discord_id=str(message.author.id),
                guild_id=guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
            )
            validate(parsed)
        except ParseError as exc:
            self._log.warning(
                "Quest parse failed",
                extra={
                    "errors": exc.errors,
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )
            return
        except ValidationError as exc:
            self._log.warning(
                "Quest validation failed",
                extra={
                    "issues": [issue.message for issue in exc.issues],
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )
            return

        existing = await self._repo.get_by_discord_message(key)
        quest_id = (
            existing.quest_id if existing else await self._id_service.next_quest_id()
        )
        referee_user_id: str | None = None
        try:
            referee_user_id = await self._id_service.ensure_user_id(
                parsed.referee_discord_id
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log.warning("ensure_user_id failed", exc_info=exc)

        record = map_parsed_to_record(
            parsed,
            quest_id,
            referee_user_id=referee_user_id,
            existing=existing,
        )

        await self._repo.upsert(record)

        action = "updated" if existing else "created"
        self._log.info(
            "Quest %s",
            action,
            extra={
                "quest_id": record.quest_id,
                "channel_id": key.channel_id,
                "message_id": key.message_id,
            },
        )

    async def ingest_edited_message(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        if not self._should_process(after):
            return
        await self.ingest_new_message(after)

    async def cancel_from_delete(
        self, *, guild_id: int, channel_id: int, message_id: int
    ) -> None:
        key = DiscordMessageKey.from_ids(guild_id, channel_id, message_id)
        updated = await self._repo.mark_cancelled(key)
        if updated:
            self._log.info(
                "Quest cancelled",
                extra={
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )

    def _should_process(self, message: discord.Message) -> bool:
        if message.guild is None:
            return False
        if message.author.bot:
            return False
        if message.channel.id != self._quest_channel_id:
            return False
        if not self._has_referee_role(message.author):
            self._log.debug(
                "Skipping message: missing referee role",
                extra={
                    "author_id": message.author.id,
                    "channel_id": message.channel.id,
                    "message_id": message.id,
                },
            )
            return False
        return True

    def _has_referee_role(self, member: discord.abc.Snowflake) -> bool:
        roles = getattr(member, "roles", [])
        for role in roles:
            if getattr(role, "id", None) == self._referee_role_id:
                return True
        return False
