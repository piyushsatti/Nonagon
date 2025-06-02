from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional

@dataclass
class QuestSummary:
  quest_id: str
  summary_text: str
  posted_at: datetime

