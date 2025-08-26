from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from app.domain.models.EntityIDModel import UserID, QuestID, SummaryID

class SummaryKind(str, Enum):
  PLAYER = "PLAYER"
  REFEREE = "REFEREE"

@dataclass
class QuestSummary:

  author_list: UserID
  summary_id: SummaryID
  quest_id: QuestID
  kind: SummaryKind
  
  title: str
  description: str
  created_on: datetime

  # Telemetry
  last_edited_at: datetime = None
  last_edited_by: str = None
  
  # Optional
  player_id: Optional[UserID] = None
  referee_id: Optional[UserID] = None