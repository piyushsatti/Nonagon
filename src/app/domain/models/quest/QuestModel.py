from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.domain.models.quest.DraftQuestModel import (
    DraftQuest,
    build_discord_time_tokens,
    build_hammertime_url,
    format_duration_text,
)
from app.domain.models.EntityIDModel import (
    CharacterID,
    DraftID,
    QuestID,
    SummaryID,
    UserID,
)

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from app.domain.models.quest.TagPolicyModel import TagPolicy


class QuestStatus(Enum):
    ANNOUNCED = "ANNOUNCED"
    SIGNUP_CLOSED = "SIGNUP_CLOSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PlayerStatus(Enum):
    APPLIED = "APPLIED"
    SELECTED = "SELECTED"


class QuestFormatQuality(Enum):
    STRICT = "STRICT"
    LAX = "LAX"


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class Quest:
    # Identity / owner
    quest_id: QuestID
    referee_id: UserID  # Referee responsible
    channel_id: str
    message_id: str

    # Extended provenance
    referee_discord_id: Optional[str] = None
    discord_guild_id: Optional[str] = None
    discord_channel_id: Optional[str] = None
    discord_message_id: Optional[str] = None
    draft_id: Optional[DraftID] = None
    posted_by_bot: bool = False

    # Discord event metadata
    event_id: Optional[str] = None
    event_url: Optional[str] = None

    # Metadata
    raw: Optional[str] = None  # raw markdown input
    title: str = ""
    description: Optional[str] = None
    description_md: Optional[str] = None
    raw_markdown: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration: Optional[timedelta] = None
    region_text: Optional[str] = None
    region_primary: Optional[str] = None
    region_secondary: Optional[str] = None
    region_hex: Optional[str] = None
    starts_at_utc: Optional[datetime] = None
    duration_minutes: int = 0
    image_url: Optional[str] = None
    discord_time_tokens: List[Dict[str, Any]] = field(default_factory=lambda: [])
    hammertime_url: Optional[str] = None
    duration_text: Optional[str] = None
    tags_raw: List[str] = field(default_factory=lambda: [])
    tags_accepted: List[str] = field(default_factory=lambda: [])
    my_table_url: str = ""
    linked_messages: List[Dict[str, Optional[str]]] = field(default_factory=lambda: [])
    linked_quest_ids: List[str] = field(default_factory=lambda: [])
    format_quality: QuestFormatQuality = QuestFormatQuality.LAX
    first_seen_at: Optional[datetime] = None
    last_edited_at: Optional[datetime] = None

    # Links
    linked_quests: List[QuestID] = field(default_factory=lambda: [])
    linked_summaries: List[SummaryID] = field(default_factory=lambda: [])

    # Lifecycle
    status: QuestStatus = QuestStatus.ANNOUNCED
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    signups: List[PlayerSignUp] = field(default_factory=lambda: [])

    def __post_init__(self) -> None:
        if self.description_md is None and self.description is not None:
            self.description_md = self.description
        if self.description is None and self.description_md is not None:
            self.description = self.description_md

        if self.raw_markdown is None and self.raw:
            self.raw_markdown = self.raw
        if self.raw is None and self.raw_markdown:
            self.raw = self.raw_markdown

        if self.discord_channel_id is None:
            self.discord_channel_id = self.channel_id
        if self.discord_message_id is None:
            self.discord_message_id = self.message_id

        self.starts_at_utc = _ensure_utc(self.starts_at_utc or self.starting_at)
        if self.starting_at is None and self.starts_at_utc is not None:
            self.starting_at = self.starts_at_utc

        if self.duration_minutes <= 0 and self.duration is not None:
            self.duration_minutes = int(self.duration.total_seconds() // 60)
        if self.duration is None and self.duration_minutes > 0:
            self.duration = timedelta(minutes=self.duration_minutes)

        if self.starts_at_utc:
            if not self.discord_time_tokens:
                self.discord_time_tokens = build_discord_time_tokens(self.starts_at_utc)
            if not self.hammertime_url:
                self.hammertime_url = build_hammertime_url(self.starts_at_utc)
            if not self.duration_text:
                self.duration_text = format_duration_text(self.duration_minutes)

        self.tags_raw = list(self.tags_raw)
        self.tags_accepted = list(self.tags_accepted)
        self.linked_messages = list(self.linked_messages)
        self.linked_quest_ids = list(self.linked_quest_ids)
        self.linked_quests = list(self.linked_quests)
        self.linked_summaries = list(self.linked_summaries)
        self.signups = list(self.signups)

    # ------- Status Helpers -------
    def set_completed(self) -> None:
        self.status = QuestStatus.COMPLETED

    def set_cancelled(self) -> None:
        self.status = QuestStatus.CANCELLED

    def set_announced(self) -> None:
        self.status = QuestStatus.ANNOUNCED

    def close_signups(self) -> None:
        self.status = QuestStatus.SIGNUP_CLOSED

    # ------- Property Helpers -------

    @property
    def is_summary_needed(self) -> bool:
        return self.status is QuestStatus.COMPLETED and len(self.linked_summaries) == 0

    @property
    def is_signup_open(self) -> bool:
        return self.status is QuestStatus.ANNOUNCED

    # ------- Signup Helpers -------

    def add_signup(self, user_id: UserID, character_id: CharacterID) -> None:
        for s in self.signups:
            if s.user_id == user_id:
                raise ValueError(f"User {user_id} already signed up")

        self.signups.append(PlayerSignUp(user_id=user_id, character_id=character_id))

    def remove_signup(self, user_id: UserID) -> None:
        for s in self.signups:
            if s.user_id == user_id:
                self.signups.remove(s)
                return

        raise ValueError(f"User {user_id} not signed up")

    def select_signup(self, user_id: UserID) -> None:
        for s in self.signups:
            if s.user_id == user_id:
                s.status = PlayerStatus.SELECTED
                return

        raise ValueError(f"User {user_id} not signed up")

    # ---------- Helpers ----------

    def validate_quest(self) -> None:

        if self.starting_at and self.duration:
            if self.duration < timedelta(minutes=60):
                raise ValueError("Duration must be at least 60 minutes.")

        if self.starting_at:
            if self.starting_at.tzinfo:
                now_reference = datetime.now(self.starting_at.tzinfo)
            else:
                now_reference = datetime.now()
            if self.starting_at < now_reference:
                raise ValueError("Starting time must be in the future.")

        if self.duration and self.duration < timedelta(minutes=15):
            raise ValueError("Duration must be at least 15 minutes.")

        if self.image_url and not (
            self.image_url.startswith("http://")
            or self.image_url.startswith("https://")
        ):
            raise ValueError("Image URL must start with http:// or https://")

        if self.starts_at_utc:
            if self.starts_at_utc.tzinfo is None:
                raise ValueError("starts_at_utc must be timezone aware")
            if self.starts_at_utc.utcoffset() != timedelta(0):
                raise ValueError("starts_at_utc must be UTC")
            if not 15 <= max(self.duration_minutes, 0) <= 24 * 60:
                raise ValueError("duration_minutes must be between 15 and 1440")

        if self.linked_messages:
            for link in self.linked_messages:
                if not all(
                    link.get(key) for key in ("guild_id", "channel_id", "message_id")
                ):
                    raise ValueError(
                        "linked_messages entries must include guild_id, channel_id, and message_id"
                    )

        if self.format_quality is QuestFormatQuality.STRICT or self.posted_by_bot:
            required: Dict[str, Any] = {
                "title": self.title,
                "region_text": getattr(self, "region_text", None),
                "tags_accepted": self.tags_accepted,
                "starts_at_utc": self.starts_at_utc,
                "duration_minutes": self.duration_minutes,
                "my_table_url": self.my_table_url,
                "event_id": self.event_id,
                "event_url": self.event_url,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(f"Missing required publish fields: {missing}")

    def from_dict(self, data: Dict[str, Any]) -> Quest:
        valid = {f.name for f in fields(self)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlayerSignUp:
    user_id: UserID
    character_id: CharacterID
    status: PlayerStatus = PlayerStatus.APPLIED


def map_draft_to_quest(
    draft: DraftQuest,
    quest_id: QuestID,
    *,
    message_ids: Dict[str, str],
    event: Dict[str, str],
    tag_policy: "TagPolicy",
    referee_id: UserID,
) -> Quest:
    tags_raw = list(draft.tags_input)
    tags_accepted = tag_policy.normalize(tags_raw)
    start_utc = draft.start_input_utc
    discord_tokens = build_discord_time_tokens(start_utc, styles=("F", "R"))
    hammertime_url = build_hammertime_url(start_utc)
    duration_text = format_duration_text(draft.duration_input_minutes)

    quest = Quest(
        quest_id=quest_id,
        referee_id=referee_id,
        channel_id=message_ids["channel_id"],
        message_id=message_ids["message_id"],
        raw=draft.description_md,
        title=draft.title,
        description=draft.description_md,
        starting_at=start_utc,
        duration=timedelta(minutes=draft.duration_input_minutes),
        image_url=draft.image_url,
        referee_discord_id=draft.referee_discord_id,
        discord_guild_id=message_ids["guild_id"],
        discord_channel_id=message_ids["channel_id"],
        discord_message_id=message_ids["message_id"],
        draft_id=DraftID.parse(draft.draft_id) if draft.draft_id else None,
        posted_by_bot=True,
        event_id=event["event_id"],
        event_url=event["event_url"],
        description_md=draft.description_md,
        raw_markdown=draft.description_md,
        starts_at_utc=start_utc,
        duration_minutes=draft.duration_input_minutes,
        discord_time_tokens=discord_tokens,
        hammertime_url=hammertime_url,
        duration_text=duration_text,
        tags_raw=tags_raw,
        tags_accepted=tags_accepted,
        my_table_url=draft.my_table_url,
        linked_messages=list(draft.linked_messages),
        linked_quest_ids=[],
        format_quality=QuestFormatQuality.STRICT,
        first_seen_at=datetime.now(timezone.utc),
        region_text=draft.region_text,
        region_primary=draft.region_primary,
        region_secondary=draft.region_secondary,
        region_hex=draft.region_hex,
    )

    quest.validate_quest()
    return quest
