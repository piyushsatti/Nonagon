from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any

# ─────────────────────────────────────────────────────────────
# Roles (RBAC)
# ─────────────────────────────────────────────────────────────
class Role(Enum):
    MEMBER = auto()
    PLAYER = auto()
    REFEREE = auto()
    ADMIN = auto()

# ─────────────────────────────────────────────────────────────
# Lightweight IDs to avoid object-key pitfalls
# (use IDs for cross-links instead of object keys)
# ─────────────────────────────────────────────────────────────
UserId = str
QuestId = str
CharacterId = str
SummaryId = str

# ─────────────────────────────────────────────────────────────
# Role-specific profiles (embedded; split later if they grow)
# ─────────────────────────────────────────────────────────────
@dataclass
class PlayerProfile:
    active_characters: List[CharacterId] = field(default_factory=list)
    retired_characters: List[CharacterId] = field(default_factory=list)
    first_quest_delay_days: Optional[int] = None
    quests_applied: int = 0
    quests_accepted: int = 0
    quest_summaries_written: List[SummaryId] = field(default_factory=list)
    last_played_at: Optional[datetime] = None
    # map "other user id" -> sessions played together count
    played_with_counts: Dict[UserId, int] = field(default_factory=dict)

@dataclass
class RefereeProfile:  # (Dungeon Master)
    count_quests_dmed: int = 0
    quests_dmed: List[QuestId] = field(default_factory=list)
    dm_summaries_written: List[SummaryId] = field(default_factory=list)
    current_count_sp: int = 0
    highest_count_sp: int = 0
    count_villains_run: int = 0
    # Better structures than bare strings:
    quest_hooks_pickedup: Dict[str, int] = field(default_factory=dict)  # hook -> times picked
    games_run_by_region: Dict[str, int] = field(default_factory=dict)   # region -> sessions
    # collaboration & who you've DMed for (by user id)
    dms_collabed_with: Dict[UserId, int] = field(default_factory=dict)  # user_id -> collab count
    dmed_for_counts: Dict[UserId, int] = field(default_factory=dict)    # player user_id -> sessions
    sessions_cancelled: int = 0
    last_dmed_at: Optional[datetime] = None

# ─────────────────────────────────────────────────────────────
# Unified User model with optional profiles
# ─────────────────────────────────────────────────────────────
@dataclass
class User:
    # Identity
    user_id: Optional[UserId] = None
    discord_id: Optional[int] = None
    dm_channel_id: Optional[int] = None

    # Roles
    roles: List[Role] = field(default_factory=lambda: [Role.MEMBER])

    # Timestamps / activity
    joined_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None

    # Engagement telemetry
    messages_count_total: int = 0
    reactions_given: int = 0
    reactions_received: int = 0
    voice_total_time_spent: int = 0  # seconds
    events_attended: int = 0
    events_organized: int = 0

    # Fun counters
    fun_count_banned: int = 0
    fun_count_liked: int = 0
    fun_count_disliked: int = 0
    fun_count_kek: int = 0
    fun_count_true: int = 0
    fun_count_heart: int = 0

    # Aggregates
    messages_count_by_category: Dict[int, int] = field(default_factory=dict)
    voice_time_by_channel: Dict[str, float] = field(default_factory=dict)

    # Optional role profiles (embed now; split later if they grow)
    player: Optional[PlayerProfile] = None
    referee: Optional[RefereeProfile] = None

    # ---------- factories ----------
    @classmethod
    def from_discord_member(cls, m) -> "User":
        # keep this import local if you use discord.py types
        joined = getattr(m, "joined_at", None) or datetime.utcnow()
        dm_id = getattr(getattr(m, "dm_channel", None), "id", None)
        return cls(
            user_id=str(m.id),
            discord_id=m.id,
            dm_channel_id=dm_id,
            joined_at=joined,
            last_active_at=datetime.utcnow(),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        # conservative loader (only known fields)
        valid = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(cls(), **filtered)

    # ---------- helpers ----------
    def ensure_role(self, role: Role) -> None:
        if role not in self.roles:
            self.roles.append(role)

    def enable_player(self) -> None:
        self.ensure_role(Role.PLAYER)
        if self.player is None:
            self.player = PlayerProfile()

    def enable_referee(self) -> None:
        self.ensure_role(Role.REFEREE)
        if self.referee is None:
            self.referee = RefereeProfile()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
