from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

from discord import Member

from app.domain.models.user.PlayerModel import Player
from app.domain.models.user.RefereeModel import Referee

from app.domain.models.EntityIDModel import UserID

class Role(Enum):
  USER = "USER"
  PLAYER = "PLAYER"
  REFEREE = "REFEREE"
  ADMIN = "ADMIN"

@dataclass
class User:
  # Identity
  user_id: str
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

  # ---------- factories ----------
  @classmethod
  def from_discord_member(cls, m: Member, _id: UserID) -> User:
    joined = m.joined_at
    dm_id = m.dm_channel.id
    return cls(
      user_id=_id,
      discord_id=str(m.id),
      dm_channel_id=str(dm_id),
      joined_at=str(joined),
      roles=[Role.USER]
    )

  @classmethod
  def from_dict(cls, data: Dict[str, Any]) -> User:
    valid = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(cls(), **filtered)

  # ---------- helpers ----------
  def add_role(self, role: Role) -> None:
    if role not in self.roles:
      self.roles.append(role)

  def enable_player(self) -> None:
    self.add_role(Role.PLAYER)
    if self.player is None:
      self.player = Player()

  def enable_referee(self) -> None:
    if Role.PLAYER not in self.roles:
      self.enable_player(self)

    self.add_role(Role.REFEREE)
    if self.referee is None:
      self.referee = Referee()

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)