from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

import discord

@dataclass
class User:

  _id: int
  
  # statistics
  joined_at: datetime
  last_active_at: datetime

  # engagement telemetry
  messages_count_total: int = 0
  messages_count_by_category: Dict[int, int] = field(default_factory=dict)
  reactions_given: int = 0
  reactions_received: int = 0
  count_draw_steel_mentioned: int = 0

  # Voice Call - hours
  voice_total_time_spent: int = 0
  voice_time_spent_in_hangout: int = 0
  voice_time_spent_in_game: int = 0

  # Event
  events_attended: int = 0
  events_organized: int = 0