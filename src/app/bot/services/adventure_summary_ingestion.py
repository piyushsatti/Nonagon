from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable, Literal

import discord

from app.domain.models.summary.SummaryAttachmentModel import SummaryAttachment
from app.domain.models.summary.SummaryModel import SummaryKind

from ..ingestion import DiscordMessageKey
from ..ingestion.summaries_pipeline import (
    SummaryParseError,
    SummaryValidationError,
    map_parsed_to_domain,
    map_summary_to_record,
    parse_message,
    validate,
)

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from app.infra.ids.service import IdService
    from app.infra.mongo.summary_records_repo import SummaryRecordsRepository


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
    ) -> None:
        self._repo = repo
        self._id_service = id_service
        self._summary_channel_id = summary_channel_id
        self._referee_role_id = referee_role_id
        self._log = logger or logging.getLogger(__name__)

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
