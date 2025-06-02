from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

@dataclass
class DungeonMasterSummary:
  quest_id: str
  summary_text: str
  posted_at: datetime