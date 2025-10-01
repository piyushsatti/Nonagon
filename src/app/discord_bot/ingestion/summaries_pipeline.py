from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, Field

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.summary.IGTModel import InGameTime, parse_in_game_time
from app.domain.models.summary.SummaryAttachmentModel import SummaryAttachment
from app.domain.models.summary.SummaryModel import (
    AdventureSummary,
    AdventureSummaryIssue,
    AutoSummaryStatus,
    SummaryKind,
    SummaryParticipant,
    SummaryStatus,
    validate_adventure_summary,
)

TITLE_PATTERN = re.compile(r"^#\s*(?P<title>.+)$", re.MULTILINE)
FIELD_PATTERN = re.compile(r"^\*\*(?P<field>[^*]+)\*\*:\s*(?P<value>.+)$", re.MULTILINE)
SECTION_PATTERN = re.compile(
    r"^##\s*(?P<title>[^\n]+)\n(?P<body>.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
MENTION_PATTERN = re.compile(r"<@!?(?P<id>\d+)>")
URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
QUEST_ID_PATTERN = re.compile(r"QUES\d{4,}")
SUMMARY_KIND_PATTERN = re.compile(r"player|referee", re.IGNORECASE)
BOOLEAN_TRUE = {"yes", "y", "true", "1"}


class SummaryParseError(Exception):
    """Raised when the adventure summary message cannot be parsed."""

    def __init__(self, errors: Sequence[str]):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


class SummaryValidationError(Exception):
    """Raised when validation of an adventure summary fails."""

    def __init__(self, issues: Iterable[AdventureSummaryIssue]):
        self.issues = list(issues)
        message = ", ".join(f"{issue.code}: {issue.message}" for issue in self.issues)
        super().__init__(message)


@dataclass(slots=True)
class ParsedParticipant:
    discord_id: str | None = None
    display_name: str | None = None


@dataclass(slots=True)
class ParsedAdventureSummary:
    quest_id: str
    guild_id: str
    channel_id: str
    message_id: str
    author_discord_id: str
    author_display_name: str
    parent_message_id: str | None
    title: str | None
    short_summary_md: str
    content_md: str
    raw_markdown: str
    region_text: str | None
    igt_text: str | None
    dm_discord_id: str | None
    players: list[ParsedParticipant]
    related_links: list[str]
    kind_hint: SummaryKind | None
    in_character: bool
    created_at: datetime
    edited_at: datetime | None


@dataclass(slots=True)
class ParsedAttachments:
    files: Sequence[SummaryAttachment]


class SummaryParticipantRecord(BaseModel):
    user_id: str | None = None
    character_id: str | None = None
    display_name: str | None = None
    discord_id: str | None = None

    class Config:
        anystr_strip_whitespace = True
        allow_mutation = False
        extra = "ignore"


class SummaryAttachmentRecord(BaseModel):
    kind: str
    url: str
    title: str | None = None
    width: int | None = None
    height: int | None = None

    class Config:
        anystr_strip_whitespace = True
        allow_mutation = False
        extra = "ignore"


def _new_attachment_record_list() -> list["SummaryAttachmentRecord"]:
    return []


def _new_participant_record_list() -> list["SummaryParticipantRecord"]:
    return []


class AdventureSummaryRecord(BaseModel):
    summary_id: str = Field(..., description="Human-readable summary identifier")
    quest_id: str
    kind: SummaryKind
    author_user_id: str | None = None
    author_discord_id: str | None = None
    author_character_id: str | None = None
    in_character: bool = True
    title: str | None = None
    short_summary_md: str = ""
    content_md: str = ""
    attachments: list[SummaryAttachmentRecord] = Field(
        default_factory=_new_attachment_record_list
    )
    region_text: str | None = None
    igt: dict[str, Any] | None = None
    dm_discord_id: str | None = None
    players: list[SummaryParticipantRecord] = Field(
        default_factory=_new_participant_record_list
    )
    related_links: list[str] = Field(default_factory=list)
    discord_guild_id: str
    discord_channel_id: str
    parent_message_id: str | None = None
    summary_message_ids: list[str] = Field(default_factory=list)
    auto_summary_status: AutoSummaryStatus = AutoSummaryStatus.NONE
    auto_summary_md: str | None = None
    auto_summary_model: str | None = None
    auto_summary_version: str | None = None
    auto_summary_created_at: datetime | None = None
    format_quality: str = ""
    status: SummaryStatus = SummaryStatus.PUBLISHED
    created_at: datetime
    updated_at: datetime
    raw_markdown: str = ""

    class Config:
        anystr_strip_whitespace = False
        allow_mutation = False
        use_enum_values = True
        extra = "ignore"


def parse_message(
    *,
    raw: str,
    author_discord_id: str,
    author_display_name: str,
    guild_id: int | str,
    channel_id: int | str,
    message_id: int | str,
    created_at: datetime,
    edited_at: datetime | None,
    parent_message_id: int | str | None,
) -> ParsedAdventureSummary:
    metadata = _parse_metadata(raw)
    sections = _parse_sections(raw)

    quest_id_value = metadata.get("quest id") or _search_first(QUEST_ID_PATTERN, raw)
    errors: list[str] = []
    if not quest_id_value:
        errors.append("Missing quest identifier (expected '**Quest ID:** QUES1234')")
    else:
        quest_id_value = quest_id_value.strip().upper()

    title_match = TITLE_PATTERN.search(raw)
    title = title_match.group("title").strip() if title_match else None

    summary_section = sections.get("summary", "").strip()
    if not summary_section:
        # fall back to entire message minus metadata lines
        summary_section = _strip_metadata_lines(raw).strip()

    players_section = sections.get("players", "")
    parsed_players = _parse_players(players_section)

    if not parsed_players:
        parsed_players = [
            ParsedParticipant(
                discord_id=author_discord_id, display_name=author_display_name
            )
        ]

    related_links = _extract_links(raw)

    kind_hint = _parse_kind(metadata.get("summary type"))
    region_text = metadata.get("region") or sections.get("region")
    igt_text = metadata.get("in-game time") or metadata.get("in game time")
    if not igt_text:
        igt_text = sections.get("in-game time") or sections.get("in game time")

    dm_discord_id = _extract_first_mention(metadata.get("dm"))
    in_character_text = metadata.get("in character") or metadata.get("in-character")
    in_character = True
    if in_character_text:
        in_character = in_character_text.strip().lower() in BOOLEAN_TRUE

    if errors:
        raise SummaryParseError(errors)

    return ParsedAdventureSummary(
        quest_id=quest_id_value or "",
        guild_id=str(guild_id),
        channel_id=str(channel_id),
        message_id=str(message_id),
        author_discord_id=author_discord_id,
        author_display_name=author_display_name,
        parent_message_id=(
            str(parent_message_id) if parent_message_id is not None else None
        ),
        title=title,
        short_summary_md=_shorten(summary_section),
        content_md=summary_section,
        raw_markdown=raw,
        region_text=region_text.strip() if region_text else None,
        igt_text=igt_text.strip() if igt_text else None,
        dm_discord_id=dm_discord_id,
        players=parsed_players,
        related_links=related_links,
        kind_hint=kind_hint,
        in_character=in_character,
        created_at=_ensure_timezone(created_at),
        edited_at=_ensure_timezone(edited_at) if edited_at else None,
    )


def map_parsed_to_domain(
    parsed: ParsedAdventureSummary,
    *,
    summary_id: str,
    author_user_id: str | None,
    attachments: Sequence[SummaryAttachment],
    summary_kind: SummaryKind,
    author_character_id: str | None = None,
    existing: AdventureSummaryRecord | None = None,
) -> AdventureSummary:
    quest_id = QuestID.parse(parsed.quest_id)
    summary_id_obj = SummaryID.parse(summary_id)

    author_user = UserID.parse(author_user_id) if author_user_id else None
    character_id_obj = (
        CharacterID.parse(author_character_id)
        if author_character_id and author_character_id.strip()
        else None
    )

    participants = [
        SummaryParticipant(
            discord_id=participant.discord_id,
            display_name=participant.display_name,
        )
        for participant in parsed.players
    ]

    if not participants:
        participants = [
            SummaryParticipant(
                discord_id=parsed.author_discord_id,
                display_name=parsed.author_display_name,
            )
        ]

    igt: InGameTime | None = None
    if parsed.igt_text:
        igt = parse_in_game_time(parsed.igt_text)

    summary_message_ids = list(existing.summary_message_ids) if existing else []
    if parsed.message_id not in summary_message_ids:
        summary_message_ids.append(parsed.message_id)

    domain_summary = AdventureSummary(
        summary_id=summary_id_obj,
        quest_id=quest_id,
        kind=summary_kind,
        author_user_id=author_user,
        author_discord_id=parsed.author_discord_id,
        author_character_id=character_id_obj,
        in_character=parsed.in_character,
        title=parsed.title,
        short_summary_md=parsed.short_summary_md,
        content_md=parsed.content_md,
        attachments=list(attachments),
        region_text=parsed.region_text,
        igt=igt,
        dm_discord_id=parsed.dm_discord_id,
        players=participants,
        related_links=parsed.related_links,
        discord_guild_id=parsed.guild_id,
        discord_channel_id=parsed.channel_id,
        parent_message_id=parsed.parent_message_id,
        summary_message_ids=summary_message_ids,
        created_on=parsed.created_at,
        last_edited_at=parsed.edited_at,
        raw_markdown=parsed.raw_markdown,
    )
    return domain_summary


def validate(summary: AdventureSummary) -> None:
    issues = validate_adventure_summary(summary)
    if issues:
        raise SummaryValidationError(issues)


def map_summary_to_record(
    summary: AdventureSummary,
    *,
    existing: AdventureSummaryRecord | None = None,
) -> AdventureSummaryRecord:
    created_at = existing.created_at if existing else summary.created_on
    updated_at = datetime.now(timezone.utc)

    attachments = [
        SummaryAttachmentRecord(
            kind=attachment.kind,
            url=attachment.url,
            title=attachment.title,
            width=attachment.width,
            height=attachment.height,
        )
        for attachment in summary.attachments
    ]

    participants = [
        SummaryParticipantRecord(
            user_id=(
                str(participant.user_id)
                if getattr(participant, "user_id", None)
                else None
            ),
            character_id=(
                str(participant.character_id)
                if getattr(participant, "character_id", None)
                else None
            ),
            display_name=participant.display_name,
            discord_id=participant.discord_id,
        )
        for participant in summary.players
    ]

    igt_payload: dict[str, Any] | None = None
    if summary.igt is not None:
        igt_payload = {
            "raw": summary.igt.raw,
            "season": summary.igt.season,
            "week": summary.igt.week,
        }

    record = AdventureSummaryRecord(
        summary_id=str(summary.summary_id),
        quest_id=str(summary.quest_id),
        kind=summary.kind,
        author_user_id=(
            str(summary.author_user_id) if summary.author_user_id is not None else None
        ),
        author_discord_id=summary.author_discord_id,
        author_character_id=(
            str(summary.author_character_id)
            if summary.author_character_id is not None
            else None
        ),
        in_character=summary.in_character,
        title=summary.title,
        short_summary_md=summary.short_summary_md,
        content_md=summary.content_md,
        attachments=attachments,
        region_text=summary.region_text,
        igt=igt_payload,
        dm_discord_id=summary.dm_discord_id,
        players=participants,
        related_links=list(summary.related_links),
        discord_guild_id=summary.discord_guild_id,
        discord_channel_id=summary.discord_channel_id,
        parent_message_id=summary.parent_message_id,
        summary_message_ids=list(summary.summary_message_ids),
        auto_summary_status=summary.auto_summary_status,
        auto_summary_md=summary.auto_summary_md,
        auto_summary_model=summary.auto_summary_model,
        auto_summary_version=summary.auto_summary_version,
        auto_summary_created_at=summary.auto_summary_created_at,
        format_quality=summary.format_quality,
        status=summary.status,
        created_at=created_at,
        updated_at=updated_at,
        raw_markdown=summary.raw_markdown,
    )
    return record


def record_to_document(record: AdventureSummaryRecord) -> dict[str, Any]:
    payload = record.model_dump(mode="python")
    payload["discord_message_id"] = record.summary_message_ids[0]
    payload.setdefault("summary_message_ids", list(record.summary_message_ids))
    return payload


def document_to_record(doc: Mapping[str, Any]) -> AdventureSummaryRecord:
    data = dict(doc)
    data.pop("_id", None)
    return AdventureSummaryRecord(**data)


def _parse_metadata(raw: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for match in FIELD_PATTERN.finditer(raw):
        field = match.group("field").strip().lower()
        value = match.group("value").strip()
        metadata[field] = value
    return metadata


def _parse_sections(raw: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for match in SECTION_PATTERN.finditer(raw):
        title = match.group("title").strip().lower()
        body = match.group("body").strip()
        sections[title] = body
    return sections


def _parse_players(section: str) -> list[ParsedParticipant]:
    participants: list[ParsedParticipant] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            stripped = stripped[1:].strip()
        discord_id = _extract_first_mention(stripped)
        display_name = stripped
        participants.append(
            ParsedParticipant(
                discord_id=discord_id,
                display_name=display_name if discord_id is None else None,
            )
        )
    return participants


def _extract_links(raw: str) -> list[str]:
    links = URL_PATTERN.findall(raw)
    seen: set[str] = set()
    deduped: list[str] = []
    for link in links:
        normalized = link.rstrip(".,)")
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _extract_first_mention(value: str | None) -> str | None:
    if not value:
        return None
    match = MENTION_PATTERN.search(value)
    if match:
        return match.group("id")
    cleaned = value.strip()
    if cleaned.isdigit():
        return cleaned
    return None


def _search_first(pattern: re.Pattern[str], raw: str) -> str | None:
    match = pattern.search(raw)
    return match.group(0) if match else None


def _parse_kind(value: str | None) -> SummaryKind | None:
    if not value:
        return None
    match = SUMMARY_KIND_PATTERN.search(value)
    if not match:
        return None
    token = match.group(0).upper()
    try:
        return SummaryKind[token]
    except KeyError:
        return None


def _strip_metadata_lines(raw: str) -> str:
    lines: list[str] = []
    for line in raw.splitlines():
        if FIELD_PATTERN.match(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _shorten(text: str, limit: int = 280) -> str:
    trimmed = text.strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[: limit - 3].rstrip() + "..."


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
