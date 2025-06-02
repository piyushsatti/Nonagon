from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional


@dataclass
class Quest:
  quest_id: str
  name: str
  dm_id: str
  scheduled_at: datetime
  attendees: List[Tuple[str, str]] = field(default_factory=list)
  status: str = "scheduled"
  xp_reward: Optional[int] = None
  gp_reward: Optional[int] = None
  duration_minutes: Optional[int] = None  # added telemetry
  category: Optional[str] = None
  summary_needed: bool = False

