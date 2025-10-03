from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Literal, Mapping, Sequence, cast
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

TITLE_PATTERN = re.compile(
    r"^#\s*(?:<:gw:\d+>|:gw:)\s*(?P<title>.+)$",
    re.MULTILINE,
)
GENERIC_TITLE_PATTERN = re.compile(r"^#\s*(?P<title>.+)$", re.MULTILINE)
REGION_PATTERN = re.compile(
    r"^\*\*Region:\*\*\s*(?P<name>[^\n,]+?)(?:,\s*(?P<hex>\S+))?$",
    re.MULTILINE,
)
TAGS_PATTERN = re.compile(r"^\*\*Tags:\*\*\s*(?P<tags>.+)$", re.MULTILINE)
STRICT_SCHED_PATTERN = re.compile(
    r"^\*\*Scheduling\s*&\s*Duration:\*\*\s*(?P<start>[^-]+?)\s*UTC\s*-\s*(?P<end>.+?)UTC",
    re.MULTILINE,
)
FLEX_SCHED_PATTERN = re.compile(
    r"^\*\*Scheduling\s*&\s*Duration:\*\*\s*(?P<body>.+)$",
    re.MULTILINE,
)
TABLE_PATTERN = re.compile(r"^\*\*My table:\*\*\s*(?P<url>\S+)$", re.MULTILINE)
LINKED_HEADER_PATTERN = re.compile(r"^\*\*Linked Quests:\*\*.*$", re.MULTILINE)
EVENT_PATTERN = re.compile(r"^\*\*Link to event:\*\*\s*(?P<url>\S+)$", re.MULTILINE)
DISCORD_LINK_PATTERN = re.compile(
    r"https://discord(?:app)?\\.com/channels/(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)",
    re.IGNORECASE,
)
IMAGE_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
DISCORD_TIMESTAMP_PATTERN = re.compile(r"<t:(?P<ts>\d+)(?::[a-zA-Z])?>")
HOUR_RANGE_PATTERN = re.compile(
    r"(?P<min>\d+)(?:\s*[-–]\s*(?P<max>\d+))?\s*(?:hour|hr)",
    re.IGNORECASE,
)
GENERIC_URL_PATTERN = re.compile(r"https?://[^\s>]+")

MIN_DURATION_MIN = 15
MAX_DURATION_MIN = 24 * 60
TITLE_MAX_LEN = 140
TAGS_MAX = 12


class ParseError(Exception):
    """Raised when the quest message cannot be parsed."""

    def __init__(self, errors: Sequence[str]):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


@dataclass(slots=True)
class ValidationIssue:
    field: str
    message: str


class ValidationError(Exception):
    """Raised when quest validation fails."""

    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = list(issues)
        message = ", ".join(f"{issue.field}: {issue.message}" for issue in self.issues)
        super().__init__(message)


@dataclass(slots=True)
class ParsedQuest:
    title: str
    description_md: str
    region_name: str
    region_hex: str
    tags: list[str]
    starts_at_utc: datetime
    ends_at_utc: datetime
    duration_minutes: int
    my_table_url: str
    linked_messages: list[tuple[str, str, str]]
    event_url: str
    image_url: str | None
    referee_discord_id: str
    discord_guild_id: str
    discord_channel_id: str
    discord_message_id: str
    raw: str


class LinkedQuestRecord(BaseModel):
    guild_id: str
    channel_id: str
    message_id: str
    quest_id: str | None = None

    class Config:
        allow_mutation = False
        extra = "ignore"


class QuestRecord(BaseModel):
    quest_id: str = Field(..., description="Human-readable quest identifier")
    title: str
    description_md: str
    region_name: str
    region_hex: str
    tags: list[str]
    starts_at_utc: datetime
    ends_at_utc: datetime
    duration_minutes: int
    my_table_url: HttpUrl
    linked_quests: list[LinkedQuestRecord]
    event_url: HttpUrl
    image_url: str | None = None
    referee_discord_id: str
    referee_user_id: str | None = None
    discord_guild_id: str
    discord_channel_id: str
    discord_message_id: str
    status: Literal["ACTIVE", "CANCELLED"] = Field(default="ACTIVE")
    raw: str
    created_at: datetime
    updated_at: datetime

    class Config:
        anystr_strip_whitespace = True
        allow_mutation = False
        extra = "ignore"


def parse_message(
    *,
    raw: str,
    referee_discord_id: str,
    guild_id: int,
    channel_id: int,
    message_id: int,
) -> ParsedQuest:
    """Parse a quest announcement into a structured representation."""

    errors: list[str] = []
    title_match = TITLE_PATTERN.search(raw)
    if not title_match:
        title_match = GENERIC_TITLE_PATTERN.search(raw)
    if not title_match:
        errors.append("Missing quest title heading '# :gw:'")
        title = ""
    else:
        title = title_match.group("title").strip()

    description_md = _extract_description(raw)
    if not description_md:
        errors.append("Missing description body after title")

    region_match = REGION_PATTERN.search(raw)
    if not region_match:
        errors.append("Missing '**Region:**' section")
        region_name = ""
        region_hex = ""
    else:
        region_name = region_match.group("name").strip()
        region_hex = (region_match.group("hex") or "").strip()

    tags = _extract_tags(raw)
    if not tags:
        errors.append("Missing or malformed '**Tags:**' section")

    starts_at = ends_at = None
    duration_minutes = 0
    sched_match = STRICT_SCHED_PATTERN.search(raw)
    if sched_match:
        try:
            starts_at, ends_at, duration_minutes = _parse_schedule(
                sched_match.group("start"), sched_match.group("end")
            )
        except ValueError as exc:
            errors.append(str(exc))
    else:
        flex_match = FLEX_SCHED_PATTERN.search(raw)
        if flex_match:
            try:
                starts_at, ends_at, duration_minutes = _parse_schedule_flexible(
                    flex_match.group("body")
                )
            except ValueError as exc:
                errors.append(str(exc))
        else:
            errors.append("Missing '**Scheduling & Duration:**' section")

    table_match = TABLE_PATTERN.search(raw)
    if not table_match:
        errors.append("Missing '**My table:**' URL")
        table_url = ""
    else:
        table_url = table_match.group("url").strip()
    _, table_channel_id, _ = _split_discord_channel_path(table_url)

    event_url = _extract_event_url(raw)
    if not event_url:
        event_url = table_url
        if not event_url:
            errors.append("Missing event URL")

    linked_messages = _extract_linked_messages(raw, fallback_channel=table_channel_id)
    if not linked_messages:
        errors.append("Missing linked quest URLs under '**Linked Quests:**'")

    image_url = _extract_first_image_url(raw)

    if errors:
        raise ParseError(errors)

    return ParsedQuest(
        title=title,
        description_md=description_md,
        region_name=region_name,
        region_hex=region_hex,
        tags=tags,
        starts_at_utc=starts_at or datetime.now(timezone.utc),
        ends_at_utc=ends_at or datetime.now(timezone.utc),
        duration_minutes=duration_minutes,
        my_table_url=table_url,
        linked_messages=linked_messages,
        event_url=event_url,
        image_url=image_url,
        referee_discord_id=str(referee_discord_id),
        discord_guild_id=str(guild_id),
        discord_channel_id=str(channel_id),
        discord_message_id=str(message_id),
        raw=raw,
    )


def validate(parsed: ParsedQuest) -> None:
    issues: list[ValidationIssue] = []

    if not parsed.title or len(parsed.title) > TITLE_MAX_LEN:
        issues.append(
            ValidationIssue(
                field="title",
                message=f"must be present and <= {TITLE_MAX_LEN} characters",
            )
        )

    if parsed.starts_at_utc >= parsed.ends_at_utc:
        issues.append(
            ValidationIssue(
                field="schedule",
                message="start time must be before end time",
            )
        )

    duration = parsed.duration_minutes
    if duration < MIN_DURATION_MIN or duration > MAX_DURATION_MIN:
        issues.append(
            ValidationIssue(
                field="duration_minutes",
                message=f"must be between {MIN_DURATION_MIN} and {MAX_DURATION_MIN}",
            )
        )

    if not parsed.tags:
        issues.append(
            ValidationIssue(field="tags", message="must include at least one tag")
        )
    if len(parsed.tags) > TAGS_MAX:
        issues.append(
            ValidationIssue(
                field="tags",
                message=f"must not exceed {TAGS_MAX} unique tags",
            )
        )

    if not parsed.linked_messages:
        issues.append(
            ValidationIssue(
                field="linked_messages",
                message="must include at least one linked quest",
            )
        )

    for field_name, url in ("my_table_url", parsed.my_table_url), (
        "event_url",
        parsed.event_url,
    ):
        if not _is_http_url(url):
            issues.append(
                ValidationIssue(
                    field=field_name,
                    message="must be a valid http(s) URL",
                )
            )

    if issues:
        raise ValidationError(issues)


def map_parsed_to_record(
    parsed: ParsedQuest,
    quest_id: str,
    *,
    referee_user_id: str | None,
    existing: QuestRecord | None = None,
) -> QuestRecord:
    now = datetime.now(timezone.utc)
    created_at = existing.created_at if existing else now
    status = existing.status if existing else "ACTIVE"

    preserved_links: dict[tuple[str, str, str], str | None] = {}
    if existing:
        preserved_links = {
            (entry.guild_id, entry.channel_id, entry.message_id): entry.quest_id
            for entry in existing.linked_quests
        }

    linked_quests = [
        LinkedQuestRecord(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            quest_id=preserved_links.get((guild_id, channel_id, message_id)),
        )
        for guild_id, channel_id, message_id in parsed.linked_messages
    ]

    return QuestRecord(
        quest_id=quest_id,
        title=parsed.title,
        description_md=parsed.description_md,
        region_name=parsed.region_name,
        region_hex=parsed.region_hex,
        tags=list(parsed.tags),
        starts_at_utc=parsed.starts_at_utc,
        ends_at_utc=parsed.ends_at_utc,
        duration_minutes=parsed.duration_minutes,
        my_table_url=cast(HttpUrl, parsed.my_table_url),
        linked_quests=linked_quests,
        event_url=cast(HttpUrl, parsed.event_url),
        image_url=parsed.image_url,
        referee_discord_id=parsed.referee_discord_id,
        referee_user_id=referee_user_id,
        discord_guild_id=parsed.discord_guild_id,
        discord_channel_id=parsed.discord_channel_id,
        discord_message_id=parsed.discord_message_id,
        status=status,
        raw=parsed.raw,
        created_at=created_at,
        updated_at=now,
    )


def record_to_document(record: QuestRecord) -> Dict[str, Any]:
    payload = record.model_dump(mode="python")
    payload["my_table_url"] = str(record.my_table_url)
    payload["event_url"] = str(record.event_url)
    return payload


def document_to_record(doc: Mapping[str, Any]) -> QuestRecord:
    data = dict(doc)
    data.pop("_id", None)
    return QuestRecord(**data)


def _extract_description(raw: str) -> str:
    lines = raw.splitlines()
    title_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if TITLE_PATTERN.match(stripped) or GENERIC_TITLE_PATTERN.match(stripped):
            title_idx = i
            break
    if title_idx is None:
        return ""

    desc_lines: list[str] = []
    for line in lines[title_idx + 1 :]:
        if line.strip().startswith("## "):
            break
        desc_lines.append(line)
    while desc_lines and not desc_lines[-1].strip():
        desc_lines.pop()
    return "\n".join(desc_lines).strip()


def _extract_tags(raw: str) -> list[str]:
    match = TAGS_PATTERN.search(raw)
    if not match:
        return []
    tag_text = match.group("tags")
    tags = re.findall(r"`([^`]+)`", tag_text)
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        token = tag.strip().lower()
        if token and token not in seen:
            seen.add(token)
            normalized.append(token)
    return normalized


def _parse_schedule(start_str: str, end_str: str) -> tuple[datetime, datetime, int]:
    start_str = start_str.strip()
    end_str = end_str.strip()

    def parse_ts(value: str, *, reference: datetime | None = None) -> datetime:
        cleaned = re.sub(r"\s+", " ", value.strip())
        parts = cleaned.split(" ")
        if len(parts) >= 2:
            candidate = " ".join(parts[:2])
            dt = datetime.strptime(candidate, "%Y-%m-%d %H:%M")
        elif reference is not None:
            dt_time = datetime.strptime(parts[0], "%H:%M")
            dt = reference.replace(
                hour=dt_time.hour,
                minute=dt_time.minute,
                second=0,
                microsecond=0,
            )
        else:
            raise ValueError("End time missing date when start reference unavailable")
        return dt.replace(tzinfo=timezone.utc)

    start_dt = parse_ts(start_str)
    try:
        end_dt = parse_ts(end_str, reference=start_dt)
    except ValueError as exc:
        raise ValueError(f"Invalid end time format: {end_str}") from exc

    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    duration = int((end_dt - start_dt).total_seconds() // 60)
    return start_dt, end_dt, duration


def _extract_linked_messages(
    raw: str, *, fallback_channel: str | None = None
) -> list[tuple[str, str, str]]:
    lines = raw.splitlines()
    collecting = False
    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith("**linked quests:**"):
            collecting = True
            remainder = stripped[len("**Linked Quests:**") :].strip()
            for link in _extract_links_from_text(
                remainder, fallback_channel=fallback_channel
            ):
                if link not in seen:
                    seen.add(link)
                    results.append(link)
            continue
        if not collecting:
            continue
        if lowered.startswith("**link to event") or (
            lowered.startswith("**") and not lowered.startswith("**linked quests")
        ):
            break
        for link in _extract_links_from_text(
            stripped, fallback_channel=fallback_channel
        ):
            if link not in seen:
                seen.add(link)
                results.append(link)

    return results


def _parse_schedule_flexible(body: str) -> tuple[datetime, datetime, int]:
    ts_match = DISCORD_TIMESTAMP_PATTERN.search(body)
    if not ts_match:
        raise ValueError("Unable to locate Discord timestamp in schedule")

    start_ts = datetime.fromtimestamp(int(ts_match.group("ts")), tz=timezone.utc)
    duration_minutes = _guess_duration_minutes(body)
    end_ts = start_ts + timedelta(minutes=duration_minutes)
    return start_ts, end_ts, duration_minutes


def _guess_duration_minutes(text: str) -> int:
    match = HOUR_RANGE_PATTERN.search(text)
    if match:
        min_hours = int(match.group("min"))
        max_hours = match.group("max")
        if max_hours:
            duration_hours = (min_hours + int(max_hours)) / 2
        else:
            duration_hours = float(min_hours)
        duration_minutes = int(duration_hours * 60)
    else:
        duration_minutes = 3 * 60

    duration_minutes = max(MIN_DURATION_MIN, duration_minutes)
    duration_minutes = min(MAX_DURATION_MIN, duration_minutes)
    return duration_minutes


def _extract_event_url(raw: str) -> str:
    event_match = EVENT_PATTERN.search(raw)
    if event_match:
        return _clean_url(event_match.group("url"))

    preferred: list[str] = []
    secondary: list[str] = []
    for match in GENERIC_URL_PATTERN.finditer(raw):
        url = _clean_url(match.group(0))
        lowered = url.lower()
        if "event" in lowered or "discord.com/events" in lowered:
            preferred.append(url)
        elif "discord.gg" in lowered or "discord.com/channels" in lowered:
            secondary.append(url)

    if preferred:
        return preferred[0]
    if secondary:
        return secondary[0]
    return ""


def _extract_links_from_text(
    text: str, *, fallback_channel: str | None = None
) -> list[tuple[str, str, str]]:
    matches: list[tuple[str, str, str]] = []
    for url_match in GENERIC_URL_PATTERN.finditer(text):
        url = _clean_url(url_match.group(0))
        guild_id, channel_id, message_id = _split_discord_channel_path(url)
        if guild_id is None:
            continue
        if message_id is None:
            if channel_id is None or fallback_channel is None:
                continue
            channel = fallback_channel
            message = channel_id
        else:
            channel = channel_id or fallback_channel
            if channel is None:
                continue
            message = message_id
        matches.append((guild_id, channel, message))
    return matches


def _clean_url(url: str) -> str:
    return url.rstrip(").,>\n\r")


def _split_discord_channel_path(url: str) -> tuple[str | None, str | None, str | None]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None, None, None
    if parsed.scheme not in {"http", "https"}:
        return None, None, None
    host = parsed.netloc.lower()
    if host not in {"discord.com", "discordapp.com"}:
        return None, None, None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments or segments[0].lower() != "channels":
        return None, None, None
    guild_id = segments[1] if len(segments) > 1 else None
    channel_id = segments[2] if len(segments) > 2 else None
    message_id = segments[3] if len(segments) > 3 else None
    return guild_id, channel_id, message_id


def _extract_first_image_url(raw: str) -> str | None:
    for match in IMAGE_PATTERN.finditer(raw):
        url = match.group(0)
        if any(url.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
            return url
    return None


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
