from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

@dataclass
class User:
  user_id: str
  user_name: str
  joined_at: datetime
  last_active_at: datetime

  # engagement telemetry
  total_time_spent: float = 0.0  # hours
  messages_total: int = 0
  messages_by_category: Dict[str, int] = field(default_factory=dict)
  reactions_given: int = 0
  reactions_received: int = 0

  # for funsies
  time_spent_not_dnd: int = 0
  count_draw_steel_mentioned: int = 0