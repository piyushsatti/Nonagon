from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any

from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID

from app.domain.models.user.UserModel import User

@dataclass
class Player(User):

  user_id: UserID
  characters: List[CharacterID] = field(default_factory=list)
  
  # Telemetry
  joined_on: datetime
  created_first_character_on: datetime = None
  last_played_on: datetime = None
  quests_applied: List[QuestID] = field(default_factory=list)
  quests_played: List[QuestID] = field(default_factory=list)
  summaries_written: List[SummaryID] = field(default_factory=list)
  played_with_character: Dict[CharacterID, (int, int)] = field(default_factory=dict) # quests shared, hours played