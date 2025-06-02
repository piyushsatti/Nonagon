from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

from .UserModel import UserModel
from .CharacterModel import CharacterModel
from .QuestModel import QuestSummaryModel

@dataclass
class Player(UserModel):
  active_characters: List[CharacterModel] = field(default_factory=list)
  retired_characters: List[CharacterModel] = field(default_factory=list)
  
  first_quest_delay_days: Optional[int] = None  # from join to first quest

  quests_applied: int = 0
  quests_accepted: int = 0
  
  quest_summaries_written: List[QuestSummaryModel] = field(default_factory=list)
  last_played_at: datetime
  played_with: Dict[Player, int] = field(default_factory=dict)

