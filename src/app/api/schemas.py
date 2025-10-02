from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# --- Shared Types ---


class UserRole(str, Enum):
    MEMBER = "MEMBER"
    PLAYER = "PLAYER"
    REFEREE = "REFEREE"


class CharacterStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class QuestStatus(str, Enum):
    ANNOUNCED = "ANNOUNCED"
    SIGNUP_CLOSED = "SIGNUP_CLOSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SummaryKind(str, Enum):
    PLAYER = "PLAYER"
    REFEREE = "REFEREE"


# --- Helpers ---


def _empty_roles() -> List[UserRole]:
    return []


def _empty_signups() -> List[QuestSignup]:  # type: ignore[name-defined]
    return []


def _empty_members() -> List["GuildMemberSnapshot"]:  # type: ignore[name-defined]
    return []


# --- Users ---


class InteractionMetrics(BaseModel):
    occurrences: int = 0
    total_seconds: int = 0
    total_hours: float = 0.0


class PlayerProfile(BaseModel):
    characters: list[str] = Field(default_factory=list)
    quests_applied: list[str] = Field(default_factory=list)
    quests_played: list[str] = Field(default_factory=list)
    summaries_written: list[str] = Field(default_factory=list)
    joined_on: Optional[datetime] = None
    created_first_character_on: Optional[datetime] = None
    last_played_on: Optional[datetime] = None
    played_with_character: Dict[str, InteractionMetrics] | None = None


class RefereeProfile(BaseModel):
    quests_hosted: list[str] = Field(default_factory=list)
    summaries_written: list[str] = Field(default_factory=list)
    first_dmed_on: Optional[datetime] = None
    last_dmed_on: Optional[datetime] = None
    collabed_with: Dict[str, InteractionMetrics] | None = None
    hosted_for: Dict[str, int] | None = None


class UserCreate(BaseModel):
    discord_id: Optional[str] = None
    dm_channel_id: Optional[str] = None
    roles: list[UserRole] | None = None
    joined_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    discord_id: Optional[str] = None
    dm_channel_id: Optional[str] = None
    joined_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    roles: list[UserRole] | None = None


class User(BaseModel):
    user_id: str
    discord_id: Optional[str] = None
    dm_channel_id: Optional[str] = None
    roles: List[UserRole] = Field(default_factory=_empty_roles)
    joined_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    is_member: bool = False
    is_player: bool = False
    is_referee: bool = False
    messages_count_total: int = 0
    reactions_given: int = 0
    reactions_received: int = 0
    voice_total_hours: float = 0.0
    player: Optional[PlayerProfile] = None
    referee: Optional[RefereeProfile] = None


class ActivityPing(BaseModel):
    active_at: Optional[datetime] = None


class SyncStats(BaseModel):
    processed: int
    created: int


class GuildMemberSnapshot(BaseModel):
    discord_id: str
    joined_at: Optional[datetime] = None
    is_bot: bool = False


class GuildSyncRequest(BaseModel):
    guild_id: str
    members: List[GuildMemberSnapshot] = Field(default_factory=_empty_members)


# --- Characters ---


class CharacterCreate(BaseModel):
    owner_id: str
    name: str
    ddb_link: str
    character_thread_link: str
    token_link: str
    art_link: str
    description: Optional[str] = None
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    ddb_link: Optional[str] = None
    character_thread_link: Optional[str] = None
    token_link: Optional[str] = None
    art_link: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[CharacterStatus] = None
    tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    last_played_at: Optional[datetime] = None


class Character(BaseModel):
    character_id: str
    owner_id: str
    name: str
    ddb_link: str
    character_thread_link: str
    token_link: str
    art_link: str
    description: str
    notes: str
    tags: list[str] = Field(default_factory=list)
    status: CharacterStatus = CharacterStatus.ACTIVE
    created_at: datetime
    last_played_at: Optional[datetime] = None
    quests_played: int = 0
    summaries_written: int = 0
    played_with: list[str] = Field(default_factory=list)
    played_in: list[str] = Field(default_factory=list)
    mentioned_in: list[str] = Field(default_factory=list)


# --- Quests ---


class QuestCreate(BaseModel):
    referee_id: str
    channel_id: str
    message_id: str
    raw: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration_hours: Optional[int] = None
    image_url: Optional[str] = None


class QuestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration_hours: Optional[int] = None
    image_url: Optional[str] = None
    status: Optional[QuestStatus] = None


class QuestSignup(BaseModel):
    user_id: str
    character_id: str
    selected: bool = False


class Quest(BaseModel):
    quest_id: str
    referee_id: str
    channel_id: str
    message_id: str
    raw: Optional[str] = None
    title: str
    description: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration_hours: Optional[int] = None
    image_url: Optional[str] = None
    status: QuestStatus = QuestStatus.ANNOUNCED
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    signups_open: bool = True
    signups: List[QuestSignup] = Field(default_factory=_empty_signups)
    linked_quests: list[str] = Field(default_factory=list)
    linked_summaries: list[str] = Field(default_factory=list)


# --- Summaries ---


class SummaryCreate(BaseModel):
    kind: SummaryKind
    author_id: str
    character_id: str
    quest_id: str
    raw: str
    title: str
    description: str
    created_on: Optional[datetime] = None
    players: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    linked_quests: list[str] = Field(default_factory=list)
    linked_summaries: list[str] = Field(default_factory=list)


class SummaryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    raw: Optional[str] = None
    players: Optional[list[str]] = None
    characters: Optional[list[str]] = None
    linked_quests: Optional[list[str]] = None
    linked_summaries: Optional[list[str]] = None
    last_edited_at: Optional[datetime] = None


class Summary(BaseModel):
    summary_id: str
    kind: SummaryKind
    author_id: str
    character_id: str
    quest_id: str
    title: str
    description: str
    raw: str
    created_on: datetime
    last_edited_at: Optional[datetime] = None
    players: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    linked_quests: list[str] = Field(default_factory=list)
    linked_summaries: list[str] = Field(default_factory=list)
