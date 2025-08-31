from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from datetime import timedelta

from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID

class Role(Enum):
  MEMBER = "MEMBER"
  PLAYER = "PLAYER"
  REFEREE = "REFEREE"


@dataclass
class User:
  # Identity
  user_id: UserID
  discord_id: Optional[str] = None
  dm_channel_id: Optional[str] = None

  # Roles
  roles: List[Role] = field(default_factory=lambda: [Role.MEMBER])

  # Timestamps / activity
  joined_at: Optional[datetime] = None
  last_active_at: Optional[datetime] = None

  # Engagement telemetry
  messages_count_total: int = 0
  reactions_given: int = 0
  reactions_received: int = 0
  voice_total_time_spent: int = 0  # hours

  # Optional role profiles
  player: Optional[Player] = None
  referee: Optional[Referee] = None

  # ---------- helpers ----------
  def add_role(self, role: Role) -> None:
    if role not in self.roles:
      self.roles.append(role)

  def enable_player(self) -> None:
    self.add_role(Role.PLAYER)
    if self.player is None:
      self.player = Player()
      self.player.from_dict()

  def enable_referee(self) -> None:
    if Role.PLAYER not in self.roles:
      self.enable_player(self)
      self.player.from_dict()

    self.add_role(Role.REFEREE)
    if self.referee is None:
      self.referee = Referee()
      self.referee.from_dict()

  def from_dict(self, data: Dict[str, Any]) -> User:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)


@dataclass
class Player():

  characters: List[CharacterID] = field(default_factory=list)
  
  # Telemetry
  joined_on: datetime = None
  created_first_character_on: datetime = None
  last_played_on: datetime = None
  quests_applied: List[QuestID] = field(default_factory=list)
  quests_played: List[QuestID] = field(default_factory=list)
  summaries_written: List[SummaryID] = field(default_factory=list)
  played_with_character: Dict[CharacterID, Tuple] = field(default_factory=dict) # {CharID: (Freq, Hours)}

  # ---------- helpers ----------
  def from_dict(self, data: Dict[str, Any]) -> Player:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)

@dataclass
class Referee():
  
  quests_hosted: List[QuestID] = field(default_factory=list)
  summaries_written: List[SummaryID] = field(default_factory=list)

  # Telemetry
  first_dmed_on: datetime = None
  last_dmed_on: datetime = None
  collabed_with: Dict[UserID, Tuple] = field(default_factory=dict)  # {user_id: (collab_count, collab_hours)
  hosted_for: Dict[UserID, int] = field(default_factory=dict)    # {user_id: count_sessions}

  # ---------- helpers ----------
  def from_dict(self, data: Dict[str, Any]) -> Referee:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)