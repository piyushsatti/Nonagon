from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum, auto

class Role(Enum):
  ACTIVE = auto()
  INACTIVE = auto()

@dataclass
class Character:
  character_id: str
  name: str
  ddb_link: str
  character_thread_link: str
  token_link: str
  art_link: str
  status: Role
  
  # Telemetry
  created_at: datetime
  last_played_at: datetime
  quests_played: int
  summaries_written: int

  # Optional fields
  tags: Optional[List[str]] = field(default_factory=list) # custom tags
  description: Optional[str] = None  # character description
  resources: Optional[List[str]] = field(default_factory=list)  # custome tracker
  notes: Optional[str] = None