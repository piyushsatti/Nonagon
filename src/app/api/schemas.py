from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# --- Shared Types ---
UserRole = Literal["MEMBER", "PLAYER", "REFEREE"]
CharacterStatus = Literal["ACTIVE", "RETIRED"]
QuestStatus = Literal["ANNOUNCED", "COMPLETED", "CANCELLED"]
SummaryKind = Literal["PLAYER", "REFEREE"]
LeaderboardMetric = Literal[
    "messages",
    "reactions_given",
    "reactions_received",
    "voice",
]


# --- Users ---
class UserIn(BaseModel):
    discord_id: Optional[str] = None
    dm_channel_id: Optional[str] = None
    dm_opt_in: Optional[bool] = True
    roles: List[UserRole] = Field(default_factory=list)


class User(UserIn):
    user_id: str
    guild_id: int
    joined_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    messages_count_total: int = 0
    reactions_given: int = 0
    reactions_received: int = 0
    voice_total_time_spent: float = 0.0

    player: Optional[dict] = None
    referee: Optional[dict] = None


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
    tags: List[str] = []


class Character(CharacterIn):
    status: CharacterStatus = "ACTIVE"
    created_at: datetime
    last_played_at: Optional[datetime] = None
    quests_played: int = 0
    summaries_written: int = 0
    played_with: List[str] = []
    played_in: List[str] = []
    mentioned_in: List[str] = []


# --- Quests ---
class QuestIn(BaseModel):
    quest_id: str = None
    referee_id: Optional[str] = None
    raw: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration_hours: Optional[int] = None
    image_url: Optional[str] = None
    linked_quests: Optional[List[str]] = None
    linked_summaries: Optional[List[str]] = None


class Quest(QuestIn):
    channel_id: Optional[str] = None
    message_id: Optional[str] = None
    status: QuestStatus = "ANNOUNCED"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    signups_open: bool = True
    signups: List[dict] = []
    last_nudged_at: Optional[datetime] = None


# --- Summaries ---
class SummaryIn(BaseModel):
    summary_id: str
    character_id: Optional[str] = None
    quest_id: Optional[str] = None
    raw: Optional[str] = None
    title: Optional[str] = None
    descroption: Optional[str] = None
    players: List[str] = None
    characters: List[str] = None
    linked_quests: List[str] = []
    linked_summaries: List[str] = []


class Summary(SummaryIn):
    kind: Optional[SummaryKind] = None
    author_id: Optional[str] = None
    created_on: Optional[datetime] = None
    last_edited_at: Optional[datetime] = None


class LeaderboardEntry(BaseModel):
    guild_id: str
    discord_id: Optional[str] = None
    metric: LeaderboardMetric
    value: float


class LeaderboardResponse(BaseModel):
    metric: LeaderboardMetric
    entries: List[LeaderboardEntry]


class UpcomingQuest(BaseModel):
    guild_id: str
    quest_id: str
    title: Optional[str] = None
    starting_at: Optional[datetime] = None
    status: Optional[QuestStatus] = None
    referee_id: Optional[str] = None


class UpcomingQuestsResponse(BaseModel):
    quests: List[UpcomingQuest]
