from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List

from app.domain.models.user.PlayerModel import Player
from app.domain.models.EntityIDModel import EntityID

@dataclass
class Referee():
  
  quests_hosted: List[EntityID] = field(default_factory=list)
  summaries_written: List[EntityID] = field(default_factory=list)

  # Telemetry
  first_dmed_on: datetime = None
  last_dmed_on: datetime = None
  collabed_with: Dict[EntityID, tuple] = field(default_factory=dict)  # user_id -> (collab count, hours)
  hosted_fors: Dict[EntityID, int] = field(default_factory=dict)    # player user_id -> sessions