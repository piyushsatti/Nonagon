from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

import discord

@dataclass
class User:

  user_id: int
  
  # statistics
  joined_at: datetime
  last_active_at: datetime

  # engagement telemetry
  messages_count_total: int = 0
  messages_count_by_category: Dict[int, int] = field(default_factory=dict)

  # Reactions
  reactions_given: int = 0
  reactions_received: int = 0

  # Voice Call - hours
  voice_total_time_spent: int = 0
  voice_time_by_channel: Dict[str, float] = field(default_factory=dict)

  # Event
  events_attended: int = 0
  events_organized: int = 0

  # Fun
  fun_count_banned: int = 0
  fun_count_liked: int = 0
  fun_count_disliked: int = 0
  fun_count_kek: int = 0
  fun_count_true: int = 0
  fun_count_heart: int = 0