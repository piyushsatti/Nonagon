from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Sequence

__all__ = [
    "DraftQuest",
    "build_discord_time_tokens",
    "build_hammertime_url",
    "format_duration_text",
]


DEFAULT_TIME_STYLES: Sequence[str] = ("F", "f", "R")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_discord_time_tokens(
    dt: datetime, styles: Sequence[str] = DEFAULT_TIME_STYLES
) -> List[Dict[str, Any]]:
    dt_utc = _ensure_utc(dt)
    if dt_utc is None:
        raise ValueError("datetime is required to build discord time tokens")
    epoch = int(dt_utc.timestamp())
    tokens: List[Dict[str, Any]] = []
    for style in styles:
        tokens.append({"epoch": epoch, "style": style})
    return tokens


def build_hammertime_url(dt: datetime) -> str:
    dt_utc = _ensure_utc(dt)
    if dt_utc is None:
        raise ValueError("datetime is required to build hammertime url")
    epoch = int(dt_utc.timestamp())
    return f"https://hammertime.cyou/#{epoch}"


def format_duration_text(minutes: int) -> str:
    if minutes <= 0:
        return "0m"
    hours, mins = divmod(minutes, 60)
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    return " ".join(parts) if parts else "0m"


@dataclass
class DraftQuest:
    draft_id: str
    referee_discord_id: str

    title: str
    description_md: str

    region_text: str
    region_primary: Optional[str] = None
    region_secondary: Optional[str] = None
    region_hex: Optional[str] = None

    tags_input: List[str] = field(default_factory=lambda: [])

    start_input_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_input_minutes: int = 0

    my_table_url: str = ""
    linked_messages: List[Dict[str, Optional[str]]] = field(default_factory=lambda: [])
    image_url: Optional[str] = None

    discord_time_tokens: List[Dict[str, Any]] = field(default_factory=lambda: [])
    hammertime_url: Optional[str] = None
    duration_text: Optional[str] = None

    validation_status: Literal["PASS", "FAIL"] = "FAIL"
    validation_issues: List[Dict[str, str]] = field(default_factory=lambda: [])

    parse_version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.start_input_utc = _ensure_utc(self.start_input_utc) or datetime.now(
            timezone.utc
        )
        if self.duration_input_minutes < 0:
            raise ValueError("duration_input_minutes cannot be negative")
        self._refresh_derived_fields()

    def _refresh_derived_fields(self) -> None:
        if self.start_input_utc:
            self.discord_time_tokens = build_discord_time_tokens(self.start_input_utc)
            self.hammertime_url = build_hammertime_url(self.start_input_utc)
        self.duration_text = format_duration_text(self.duration_input_minutes)

    def refresh_preview(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self._refresh_derived_fields()

    def mark_passed_validation(self) -> None:
        self.validation_status = "PASS"
        self.validation_issues.clear()

    def mark_failed_validation(self, issues: Sequence[Dict[str, str]]) -> None:
        self.validation_status = "FAIL"
        self.validation_issues = list(issues)
        self.updated_at = datetime.now(timezone.utc)
