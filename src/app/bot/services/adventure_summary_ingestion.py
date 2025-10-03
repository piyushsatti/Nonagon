from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterable, Literal, Sequence

import discord

from app.domain.models.summary.SummaryAttachmentModel import SummaryAttachment
from app.domain.models.summary.SummaryModel import (
    AutoSummaryStatus,
    SummaryKind,
    SummaryStatus,
)

from ..ingestion import DiscordMessageKey
from ..ingestion.failures import IngestFailureRecord
from ..ingestion.summaries_pipeline import (
    AdventureSummaryRecord,
    ParsedAdventureSummary,
    SummaryAttachmentRecord,
    SummaryParseError,
    SummaryParticipantRecord,
    SummaryValidationError,
    map_parsed_to_domain,
    map_summary_to_record,
    parse_message,
    validate,
)

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from app.infra.ids.service import IdService
    from app.infra.mongo.ingest_failures_repo import IngestFailureRepository
    from app.infra.mongo.quest_records_repo import QuestRecordsRepository
    from app.infra.mongo.summary_records_repo import SummaryRecordsRepository

from .guild_logging import GuildLoggingService


class AdventureSummaryIngestionService:
    """Orchestrates ingestion of adventure summaries posted to Discord."""

    def __init__(
        self,
        *,
        repo: "SummaryRecordsRepository",
        id_service: "IdService",
        summary_channel_id: int | None,
        referee_role_id: int | None,
        logger: logging.Logger | None = None,
        logging_service: GuildLoggingService | None = None,
        quest_repo: QuestRecordsRepository | None = None,
        failure_repo: IngestFailureRepository | None = None,
    ) -> None:
        self._repo = repo
        self._id_service = id_service
        self._summary_channel_id = summary_channel_id
        self._referee_role_id = referee_role_id
        self._log = logger or logging.getLogger(__name__)
        self._logging = logging_service
        self._quest_repo = quest_repo
        self._failure_repo = failure_repo

    def update_configuration(
        self,
        *,
        summary_channel_id: int | None = None,
        referee_role_id: int | None = None,
    ) -> None:
        if summary_channel_id is not None:
            self._summary_channel_id = summary_channel_id
        if referee_role_id is not None:
            self._referee_role_id = referee_role_id

    async def ingest_new_message(self, message: discord.Message) -> None:
        if not self._should_process(message):
            return
        guild = message.guild
        assert guild is not None

        key = DiscordMessageKey.from_ids(guild.id, message.channel.id, message.id)
        self._log.info(
            "Adventure summary detected",
            extra={
                "guild_id": key.guild_id,
                "channel_id": key.channel_id,
                "message_id": key.message_id,
                "author_id": message.author.id,
            },
        )
        existing = await self._repo.get_by_discord_message(key)
        summary_id = (
            existing.summary_id
            if existing
            else await self._id_service.next_summary_id()
        )

        try:
            parsed = parse_message(
                raw=message.content,
                author_discord_id=str(message.author.id),
                author_display_name=getattr(
                    message.author, "display_name", message.author.name
                ),
                guild_id=guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                created_at=message.created_at,
                edited_at=message.edited_at,
                parent_message_id=(
                    message.reference.message_id
                    if message.reference and message.reference.message_id
                    else None
                ),
            )
        except SummaryParseError as exc:
            self._log.warning(
                "Summary parse failed",
                extra={
                    "errors": exc.errors,
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )
            if self._failure_repo:
                await self._failure_repo.record_failure(
                    IngestFailureRecord(
                        kind="summary",
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

        attachments = self._convert_attachments(message.attachments)
        summary_kind = parsed.kind_hint or self._infer_kind(message)

        author_user_id: str | None = None
        try:
            author_user_id = await self._id_service.ensure_user_id(
                str(message.author.id)
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._log.warning("ensure_user_id failed", exc_info=exc)

        if parsed.quest_id is None and parsed.quest_message_ref and self._quest_repo:
            try:
                quest = await self._quest_repo.get_by_discord_key(
                    parsed.quest_message_ref
                )
            except Exception as exc:  # pragma: no cover - defensive
                self._log.warning("Quest lookup failed", exc_info=exc)
            else:
                if quest:
                    parsed = replace(parsed, quest_id=quest.quest_id)
                    self._log.debug(
                        "Resolved summary quest reference",
                        extra={
                            "channel_id": key.channel_id,
                            "message_id": key.message_id,
                            "quest_id": quest.quest_id,
                        },
                    )

        if parsed.quest_id is None:
            partial_record = self._build_partial_record(
                parsed,
                summary_id=summary_id,
                summary_kind=summary_kind,
                attachments=attachments,
                author_user_id=author_user_id,
                existing=existing,
            )
            stored_partial = await self._repo.upsert(partial_record)
            quest_link = (
                f"https://discord.com/channels/{parsed.quest_message_ref.guild_id}/{parsed.quest_message_ref.channel_id}/{parsed.quest_message_ref.message_id}"
                if parsed.quest_message_ref
                else None
            )
            log_extra: dict[str, object] = {
                "summary_id": stored_partial.summary_id,
                "channel_id": key.channel_id,
                "message_id": key.message_id,
                "quest_link": quest_link or "",
            }
            self._log.warning(
                "Adventure summary stored without quest reference",
                extra=log_extra,
            )
            if message.guild and self._logging:
                await self._logging.log_event(
                    message.guild.id,
                    title="Summary stored (quest unresolved)",
                    description=parsed.title,
                    fields=[
                        ("Summary ID", stored_partial.summary_id),
                        (
                            "Quest Link",
                            quest_link or "(not provided)",
                        ),
                        ("Channel", f"<#{key.channel_id}>"),
                    ],
                    extra=log_extra,
                )
            if self._failure_repo:
                await self._failure_repo.record_failure(
                    IngestFailureRecord(
                        kind="summary",
                        guild_id=key.guild_id,
                        channel_id=key.channel_id,
                        message_id=key.message_id,
                        author_id=str(message.author.id),
                        raw_content=message.content,
                        reason="missing_quest_reference",
                        metadata={
                            "quest_id": parsed.quest_id,
                            "quest_link": quest_link,
                        },
                    )
                )
            return

        domain_summary = map_parsed_to_domain(
            parsed,
            summary_id=summary_id,
            author_user_id=author_user_id,
            attachments=attachments,
            summary_kind=summary_kind,
            existing=existing,
        )

        try:
            validate(domain_summary)
        except SummaryValidationError as exc:
            self._log.warning(
                "Summary validation failed",
                extra={
                    "issues": [f"{issue.code}:{issue.message}" for issue in exc.issues],
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )
            if self._failure_repo:
                await self._failure_repo.record_failure(
                    IngestFailureRecord(
                        kind="summary",
                        guild_id=key.guild_id,
                        channel_id=key.channel_id,
                        message_id=key.message_id,
                        author_id=str(message.author.id),
                        raw_content=message.content,
                        reason="validation_error",
                        errors=[
                            f"{issue.code}:{issue.message}" for issue in exc.issues
                        ],
                        metadata={
                            "quest_id": str(domain_summary.quest_id),
                            "summary_id": str(domain_summary.summary_id),
                            "title": domain_summary.title,
                        },
                    )
                )
            return

        record = map_summary_to_record(domain_summary, existing=existing)
        await self._repo.upsert(record)

        action = "updated" if existing else "created"
        self._log.info(
            "Adventure summary %s",
            action,
            extra={
                "summary_id": record.summary_id,
                "quest_id": record.quest_id,
                "channel_id": key.channel_id,
                "message_id": key.message_id,
            },
        )
        if message.guild and self._logging:
            await self._logging.log_event(
                message.guild.id,
                title=f"Summary {action}",
                description=record.title,
                fields=[
                    ("Summary ID", record.summary_id),
                    (
                        "Quest ID",
                        record.quest_id or "(not linked)",
                    ),
                    ("Channel", f"<#{key.channel_id}>"),
                ],
                extra={
                    "summary_id": record.summary_id,
                    "quest_id": record.quest_id,
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )

    def _build_partial_record(
        self,
        parsed: ParsedAdventureSummary,
        *,
        summary_id: str,
        summary_kind: SummaryKind,
        attachments: Sequence[SummaryAttachment],
        author_user_id: str | None,
        existing: AdventureSummaryRecord | None,
    ) -> AdventureSummaryRecord:
        attachment_records = [
            SummaryAttachmentRecord(
                kind=attachment.kind,
                url=attachment.url,
                title=attachment.title,
                width=attachment.width,
                height=attachment.height,
            )
            for attachment in attachments
        ]

        participants = [
            SummaryParticipantRecord(
                discord_id=participant.discord_id,
                display_name=participant.display_name,
            )
            for participant in parsed.players
        ]

        if not participants:
            participants = [
                SummaryParticipantRecord(
                    discord_id=parsed.author_discord_id,
                    display_name=parsed.author_display_name,
                )
            ]

        summary_message_ids = list(existing.summary_message_ids) if existing else []
        if parsed.message_id not in summary_message_ids:
            summary_message_ids.append(parsed.message_id)

        created_at = existing.created_at if existing else parsed.created_at

        return AdventureSummaryRecord(
            summary_id=summary_id,
            quest_id=parsed.quest_id,
            kind=summary_kind,
            author_user_id=author_user_id,
            author_discord_id=parsed.author_discord_id,
            author_character_id=None,
            in_character=parsed.in_character,
            title=parsed.title,
            short_summary_md=parsed.short_summary_md,
            content_md=parsed.content_md,
            attachments=attachment_records,
            region_text=parsed.region_text,
            igt=None,
            dm_discord_id=parsed.dm_discord_id,
            players=participants,
            related_links=parsed.related_links,
            discord_guild_id=parsed.guild_id,
            discord_channel_id=parsed.channel_id,
            parent_message_id=parsed.parent_message_id,
            summary_message_ids=summary_message_ids,
            auto_summary_status=(
                existing.auto_summary_status if existing else AutoSummaryStatus.NONE
            ),
            auto_summary_md=existing.auto_summary_md if existing else None,
            auto_summary_model=existing.auto_summary_model if existing else None,
            auto_summary_version=existing.auto_summary_version if existing else None,
            auto_summary_created_at=(
                existing.auto_summary_created_at if existing else None
            ),
            format_quality=existing.format_quality if existing else "",
            status=existing.status if existing else SummaryStatus.PUBLISHED,
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
            raw_markdown=parsed.raw_markdown,
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
                "Adventure summary cancelled",
                extra={
                    "channel_id": key.channel_id,
                    "message_id": key.message_id,
                },
            )
            if self._logging:
                await self._logging.log_event(
                    guild_id,
                    title="Summary cancelled",
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
        if self._summary_channel_id is None:
            return False
        if message.channel.id != self._summary_channel_id:
            return False
        return True

    def _infer_kind(self, message: discord.Message) -> SummaryKind:
        if self._has_referee_role(message.author):
            return SummaryKind.REFEREE
        return SummaryKind.PLAYER

    def _has_referee_role(self, member: discord.abc.Snowflake) -> bool:
        if self._referee_role_id is None:
            return True
        roles = getattr(member, "roles", [])
        for role in roles:
            if getattr(role, "id", None) == self._referee_role_id:
                return True
        return False

    def _convert_attachments(
        self, attachments: Iterable[discord.Attachment]
    ) -> list[SummaryAttachment]:
        items: list[SummaryAttachment] = []
        for attachment in attachments:
            items.append(
                SummaryAttachment(
                    kind=self._classify_attachment(attachment),
                    url=attachment.url,
                    title=attachment.filename,
                    width=attachment.width,
                    height=attachment.height,
                )
            )
        return items

    def _classify_attachment(
        self, attachment: discord.Attachment
    ) -> Literal["image", "video", "file", "embed", "link"]:
        content_type = (attachment.content_type or "").lower()
        filename = attachment.filename.lower() if attachment.filename else ""
        if content_type.startswith("image/") or filename.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp")
        ):
            return "image"
        if content_type.startswith("video/") or filename.endswith(
            (".mp4", ".mov", ".mkv")
        ):
            return "video"
        if content_type.startswith("text/") or filename.endswith(
            (".txt", ".md", ".pdf")
        ):
            return "file"
        return "file"
