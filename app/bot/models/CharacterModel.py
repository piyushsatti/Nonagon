from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Character:
  """Represents one player character."""
  character_id: str
  name: str
  ddb_link: str
  character_thread_link: str
  token_link: str
  art_link: str
  status: str
  
  # Telemetry
  created_at: datetime
  last_played_at: datetime
  quests_played: int
  summaries_written: int

  # Insights
  tags: Optional[List[str]] = field(default_factory=list) # tags could be species and class related
  description: str