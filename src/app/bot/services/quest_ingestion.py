from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..ingestion import (
    DiscordMessageKey,
    ParsedQuest,
    ParseError,
    ValidationError,
    map_parsed_to_record,
    parse_message,
    validate,
)
from ..ingestion.failures import IngestFailureRecord

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from app.infra.ids.service import IdService
    from app.infra.mongo.ingest_failures_repo import IngestFailureRepository
    from app.infra.mongo.quest_records_repo import QuestRecordsRepository

from .guild_logging import GuildLoggingService


class QuestIngestionService:
    """Coordinates Discord quest events with parsing, validation, and persistence."""

    def __init__(
        self,
        *,
        repo: "QuestRecordsRepository",
        id_service: "IdService",
        quest_channel_id: int | None,
        referee_role_id: int | None,
        logger: logging.Logger | None = None,
        logging_service: GuildLoggingService | None = None,
        failure_repo: IngestFailureRepository | None = None,
    ) -> None:
        self._repo = repo
        self._id_service = id_service
        self._quest_channel_id = quest_channel_id
        self._referee_role_id = referee_role_id
        self._log = logger or logging.getLogger(__name__)
        self._logging_service = logging_service
        self._failure_repo = failure_repo

    def update_configuration(
        self,
        *,
        quest_channel_id: int | None = None,
        referee_role_id: int | None = None,
    ) -> None:
        if quest_channel_id is not None:
            self._quest_channel_id = quest_channel_id
        if referee_role_id is not None:
            self._referee_role_id = referee_role_id

    async def ingest_new_message(self, message: discord.Message) -> None:
        if not self._should_process(message):
            return

        guild = message.guild
        assert guild is not None
        key = DiscordMessageKey.from_ids(guild.id, message.channel.id, message.id)
        self._log.info(
            "Quest message detected",
            extra={
                "guild_id": key.guild_id,
                "channel_id": key.channel_id,
                "message_id": key.message_id,
                "author_id": message.author.id,
            },
        )
        parsed: ParsedQuest | None = None
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
            if self._failure_repo:
                await self._failure_repo.record_failure(
                    IngestFailureRecord(
                        kind="quest",
                        guild_id=key.guild_id,
                        channel_id=key.channel_id,
                        message_id=key.message_id,
                        author_id=str(message.author.id),
                        raw_content=message.content,
                        reason="parse_error",
                        errors=exc.errors,
                    )
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
            if self._failure_repo and parsed is not None:
                metadata = {
                    "title": parsed.title,
                    "region_name": parsed.region_name,
                    "event_url": parsed.event_url,
                    "my_table_url": parsed.my_table_url,
                }
                await self._failure_repo.record_failure(
                    IngestFailureRecord(
                        kind="quest",
                        guild_id=key.guild_id,
                        channel_id=key.channel_id,
                        message_id=key.message_id,
                        author_id=str(message.author.id),
                        raw_content=message.content,
                        reason="validation_error",
                        errors=[issue.message for issue in exc.issues],
                        metadata=metadata,
                    )
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
        if message.guild and self._logging_service:
            await self._logging_service.log_event(
                message.guild.id,
                title=f"Quest {action}",
                description=record.title,
                fields=[
                    ("Quest ID", record.quest_id),
                    ("Channel", f"<#{key.channel_id}>"),
                    (
                        "Message",
                        f"https://discord.com/channels/{key.guild_id}/{key.channel_id}/{key.message_id}",
                    ),
                ],
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
            if self._logging_service:
                await self._logging_service.log_event(
                    guild_id,
                    title="Quest cancelled",
                    fields=[
                        ("Channel", f"<#{key.channel_id}>"),
                        (
                            "Message",
                            f"https://discord.com/channels/{guild_id}/{key.channel_id}/{key.message_id}",
                        ),
                    ],
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
        if self._quest_channel_id is None:
            return False
        if message.channel.id != self._quest_channel_id:
            return False
        return True
