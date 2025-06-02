from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

from .UserModel import UserModel
from .PlayerModel import Player
from .QuestModel import QuestModel, QuestSummaryModel

@dataclass
class DungeonMaster(UserModel):
  count_quests_dmed: int = 0
  quests_dmed: List[QuestModel] = field(default_factory=list) 
  dm_summaries_written: List[QuestSummaryModel] = field(default_factory=list) 
  current_count_sp: int = 0
  highest_count_sp: int = 0
  count_villains_run: int = 0
  quest_hooks_pickedup: str
  games_run_by_region: str
  dms_collabedd_with: List[DungeonMaster] = field(default_factory=list)
  dmed_for: Dict[Player, int] = field(default_factory=dict)
  sessions_cancelled: int = 0
  # avg_session_rating: Optional[float] = None  # 1.0–5.0 scale
  last_dmed_at: datetime
