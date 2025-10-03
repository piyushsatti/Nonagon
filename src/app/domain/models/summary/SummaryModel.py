from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Optional

from app.domain.models.EntityIDModel import (
    CharacterID,
    QuestID,
    SummaryID,
    UserID,
)

from .IGTModel import InGameTime
from .SummaryAttachmentModel import SummaryAttachment


class SummaryKind(str, Enum):
    PLAYER = "PLAYER"
    REFEREE = "REFEREE"


def _new_user_id_list() -> list[UserID]:
    return []


def _new_character_id_list() -> list[CharacterID]:
    return []


def _new_quest_id_list() -> list[QuestID]:
    return []


def _new_summary_id_list() -> list[SummaryID]:
    return []


@dataclass
class QuestSummary:

    summary_id: SummaryID
    kind: SummaryKind
    author_id: UserID
    character_id: CharacterID
    quest_id: QuestID

    # Content
    raw: str
    title: str
    description: str

    # Telemetry
    created_on: datetime
    last_edited_at: Optional[datetime] = None
    players: list[UserID] = field(default_factory=_new_user_id_list)
    characters: list[CharacterID] = field(default_factory=_new_character_id_list)

    # Links
    linked_quests: list[QuestID] = field(default_factory=_new_quest_id_list)
    linked_summaries: list[SummaryID] = field(default_factory=_new_summary_id_list)

    # ---------- Helpers ----------
    def from_dict(self, data: Dict[str, Any]) -> QuestSummary:
        valid = {f.name for f in fields(self)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # ---------- Validation ----------
    def validate_summary(self) -> None:
        if self.kind not in (SummaryKind.PLAYER, SummaryKind.REFEREE):
            raise ValueError(f"Invalid summary kind: {self.kind}")

        if not self.title or not self.title.strip():
            raise ValueError("Summary title cannot be empty")

        if not self.description or not self.description.strip():
            raise ValueError("Summary description cannot be empty")

        if not self.raw or not self.raw.strip():
            raise ValueError("Summary content cannot be empty")

        if not self.players or len(self.players) == 0:
            raise ValueError("At least one player must be associated with the summary")

        if not self.characters or len(self.characters) == 0:
            raise ValueError(
                "At least one character must be associated with the summary"
            )

        if self.last_edited_at is not None and self.last_edited_at < self.created_on:
            raise ValueError("last_edited_at cannot be before created_on")


class SummaryStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class ContentFormatQuality(str, Enum):
    STRICT = "STRICT"
    LAX = "LAX"
    BROKEN = "BROKEN"


class AutoSummaryStatus(str, Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(slots=True)
class SummaryParticipant:
    user_id: Optional[UserID] = None
    character_id: Optional[CharacterID] = None
    display_name: Optional[str] = None
    discord_id: Optional[str] = None


def _new_attachment_list() -> list[SummaryAttachment]:
    return []


def _new_participant_list() -> list["SummaryParticipant"]:
    return []


def _new_str_list() -> list[str]:
    return []


@dataclass(slots=True)
class AdventureSummary:
    summary_id: SummaryID
    quest_id: QuestID

    kind: SummaryKind = SummaryKind.PLAYER
    author_user_id: Optional[UserID] = None
    author_discord_id: Optional[str] = None
    author_character_id: Optional[CharacterID] = None
    in_character: bool = True

    title: Optional[str] = None
    short_summary_md: str = ""
    content_md: str = ""
    attachments: list[SummaryAttachment] = field(default_factory=_new_attachment_list)

    region_text: Optional[str] = None
    igt: Optional[InGameTime] = None
    dm_discord_id: Optional[str] = None
    players: list[SummaryParticipant] = field(default_factory=_new_participant_list)

    related_links: list[str] = field(default_factory=_new_str_list)

    discord_guild_id: str = ""
    discord_channel_id: str = ""
    parent_message_id: Optional[str] = None
    summary_message_ids: list[str] = field(default_factory=_new_str_list)

    auto_summary_status: AutoSummaryStatus = AutoSummaryStatus.NONE
    auto_summary_md: Optional[str] = None
    auto_summary_model: Optional[str] = None
    auto_summary_version: Optional[str] = None
    auto_summary_created_at: Optional[datetime] = None

    format_quality: ContentFormatQuality = ContentFormatQuality.LAX
    status: SummaryStatus = SummaryStatus.PUBLISHED

    created_on: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_edited_at: Optional[datetime] = None
    raw_markdown: str = ""

    def __post_init__(self) -> None:
        self.summary_message_ids = _dedupe_preserve_order(self.summary_message_ids)
        self._validate_required_fields()
        self._enforce_player_participation()
        self._validate_igt()
        self._validate_auto_summary()
        self.format_quality = determine_format_quality(
            raw=self.raw_markdown,
            short_summary=self.short_summary_md,
            content=self.content_md,
        )

    # ---------- validation helpers ----------
    def _validate_required_fields(self) -> None:
        if not (self.content_md.strip() or self.attachments):
            raise ValueError(
                "AdventureSummary requires either content_md or attachments"
            )

        if not self.discord_guild_id:
            raise ValueError("discord_guild_id is required")

        if not self.discord_channel_id:
            raise ValueError("discord_channel_id is required")

        if not self.summary_message_ids:
            raise ValueError("summary_message_ids must include at least one id")

        if any(not msg_id.strip() for msg_id in self.summary_message_ids):
            raise ValueError("summary_message_ids must be non-empty strings")

    def _enforce_player_participation(self) -> None:
        if self.kind == SummaryKind.PLAYER and not self.players:
            raise ValueError(
                "PLAYER summaries must include at least one SummaryParticipant"
            )

    def _validate_igt(self) -> None:
        if self.igt and self.igt.week is not None and self.igt.week < 1:
            raise ValueError("In-game time week must be >= 1 when provided")

    def _validate_auto_summary(self) -> None:
        if self.auto_summary_status == AutoSummaryStatus.NONE:
            if any(
                value
                for value in (
                    self.auto_summary_md,
                    self.auto_summary_model,
                    self.auto_summary_version,
                    self.auto_summary_created_at,
                )
            ):
                raise ValueError(
                    "Auto-summary fields must be empty when status is NONE"
                )

        if self.auto_summary_status == AutoSummaryStatus.COMPLETE and not (
            self.auto_summary_md and self.auto_summary_created_at
        ):
            raise ValueError(
                "Completed auto summaries must include content and timestamp"
            )


@dataclass(slots=True)
class AdventureSummaryIssue:
    code: str
    message: str


def _dedupe_preserve_order(ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in ids:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def determine_format_quality(
    *, raw: str, short_summary: str, content: str
) -> ContentFormatQuality:
    canonical_labels = {"## summary", "## players", "## region", "## in-game time"}
    lax_aliases = {
        "## recap",
        "## cast",
        "## area",
        "## ig-time",
        "## ingame time",
    }

    text = "\n".join(
        part for part in (raw, short_summary, content) if part and part.strip()
    ).lower()
    if not text:
        return ContentFormatQuality.BROKEN

    if all(label in text for label in canonical_labels):
        return ContentFormatQuality.STRICT

    if any(label in text for label in canonical_labels.union(lax_aliases)):
        return ContentFormatQuality.LAX

    return ContentFormatQuality.BROKEN


def validate_adventure_summary(
    summary: AdventureSummary,
) -> list[AdventureSummaryIssue]:
    issues: list[AdventureSummaryIssue] = []

    def add_issue(code: str, message: str) -> None:
        issues.append(AdventureSummaryIssue(code=code, message=message))

    if not (summary.content_md.strip() or summary.attachments):
        add_issue(
            "SUMMARY0001",
            "AdventureSummary requires either content markdown or attachments",
        )

    if not summary.discord_guild_id:
        add_issue("SUMMARY0002", "Discord guild ID is required")

    if not summary.discord_channel_id:
        add_issue("SUMMARY0003", "Discord channel ID is required")

    if not summary.summary_message_ids:
        add_issue("SUMMARY0004", "At least one summary message ID is required")

    if any(not msg_id.strip() for msg_id in summary.summary_message_ids):
        add_issue("SUMMARY0005", "Summary message IDs must be non-empty")

    if summary.kind == SummaryKind.PLAYER and not summary.players:
        add_issue("SUMMARY0002", "PLAYER summaries must include participants")

    if summary.igt and summary.igt.week is not None and summary.igt.week < 1:
        add_issue("SUMMARY0003", "In-game week must be >= 1")

    msg_ids = summary.summary_message_ids
    if any(not msg_id for msg_id in msg_ids):
        add_issue("SUMMARY0004", "Summary message IDs must be non-empty")

    if len(set(msg_ids)) != len(msg_ids):
        add_issue("SUMMARY0005", "Summary message IDs must be unique")

    if summary.auto_summary_status == AutoSummaryStatus.NONE:
        if any(
            value
            for value in (
                summary.auto_summary_md,
                summary.auto_summary_model,
                summary.auto_summary_version,
                summary.auto_summary_created_at,
            )
        ):
            add_issue(
                "SUMMARY0006",
                "Auto-summary fields must be empty when status is NONE",
            )

    if summary.auto_summary_status == AutoSummaryStatus.COMPLETE:
        if not summary.auto_summary_md:
            add_issue(
                "SUMMARY0007",
                "Completed auto summaries must include generated markdown",
            )
        if not summary.auto_summary_created_at:
            add_issue(
                "SUMMARY0008",
                "Completed auto summaries must include a timestamp",
            )

    return issues


# Backwards compatibility exports
QuestSummaryModel = QuestSummary
