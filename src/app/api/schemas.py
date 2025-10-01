from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

# --- Shared Types ---
UserRole = Literal["MEMBER", "PLAYER", "REFEREE"]
CharacterStatus = Literal["ACTIVE", "RETIRED"]
QuestStatus = Literal["ANNOUNCED", "COMPLETED", "CANCELLED"]
SummaryKind = Literal["PLAYER", "REFEREE"]


# --- Users ---
class UserBase(BaseModel):
    discord_id: Optional[str] = None
    dm_channel_id: Optional[str] = None
    roles: Optional[list[UserRole]] = None
    joined_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None


class UserIn(UserBase):
    pass


class User(UserBase):
    user_id: str
    is_member: bool = False
    is_player: bool = False
    is_referee: bool = False
    message_count_total: Optional[int] = None
    reactions_given: Optional[int] = None
    reactions_received: Optional[int] = None
    voice_time_total_spent: Optional[float] = None  # hours

    player: Optional[Dict[str, Any]] = None
    referee: Optional[Dict[str, Any]] = None


class ActivityPing(BaseModel):
    active_at: Optional[datetime] = None


# --- Characters ---
class CharacterIn(BaseModel):
    character_id: str
    owner_id: Optional[str] = None
    name: Optional[str] = None
    ddb_link: Optional[str] = None
    character_thread_link: Optional[str] = None
    token_link: Optional[str] = None
    art_link: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class Character(CharacterIn):
    status: CharacterStatus = "ACTIVE"
    created_at: datetime
    last_played_at: Optional[datetime] = None
    quests_played: int = 0
    summaries_written: int = 0
    played_with: list[str] = Field(default_factory=list)
    played_in: list[str] = Field(default_factory=list)
    mentioned_in: list[str] = Field(default_factory=list)


# --- Quests ---
class QuestIn(BaseModel):
    quest_id: Optional[str] = None
    referee_id: Optional[str] = None
    raw: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration_hours: Optional[int] = None
    image_url: Optional[str] = None
    linked_quests: Optional[list[str]] = None
    linked_summaries: Optional[list[str]] = None


class Quest(QuestIn):
    channel_id: Optional[str] = None
    message_id: Optional[str] = None
    status: QuestStatus = "ANNOUNCED"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    signups_open: bool = True
    signups: list[Dict[str, Any]] | None = None


# --- Summaries ---
class SummaryIn(BaseModel):
    summary_id: str
    character_id: Optional[str] = None
    quest_id: Optional[str] = None
    raw: Optional[str] = None
    title: Optional[str] = None
    descroption: Optional[str] = None
    players: Optional[list[str]] = None
    characters: Optional[list[str]] = None
    linked_quests: list[str] = Field(default_factory=list)
    linked_summaries: list[str] = Field(default_factory=list)


class Summary(SummaryIn):
    kind: Optional[SummaryKind] = None
    author_id: Optional[str] = None
    created_on: Optional[datetime] = None
    last_edited_at: Optional[datetime] = None
