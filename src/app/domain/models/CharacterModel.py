from __future__ import annotations
from dataclasses import dataclass, field, fields, replace, asdict
from typing import Dict, Tuple
from datetime import datetime
from typing import List, Optional
from enum import Enum, auto

from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID

class CharacterRole(Enum):
  ACTIVE = "ACTIVE"
  INACTIVE = "INACTIVE"

@dataclass
class Character:
  # Identity
  owner_id: UserID
  character_id: str
  name: str
  ddb_link: str
  character_thread_link: str
  token_link: str
  art_link: str
  status: CharacterRole = CharacterRole.ACTIVE

  # Telemetry
  created_at: datetime
  last_played_at: datetime
  quests_played: int = 0 
  summaries_written: int = 0

  # Optional fields
  description: str = None
  notes: str = None
  tags: Tuple[str] = field(default_factory=Tuple) # custom tags

  # Links
  played_with: List[CharacterID] = field(default_factory=list)
  played_in: List[QuestID] = field(default_factory=list)
  mentioned_in: List[SummaryID] = field(default_factory=list)

  # ---------- Helpers ----------

  def from_dict(self, data: Dict[str, any]) -> Character:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, any]:
    return asdict(self)