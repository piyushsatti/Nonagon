from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Character:
  """Represents a player character."""
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

  # Optional fields
  tags: Optional[List[str]] = field(default_factory=list) # tags for filtering
  description: Optional[str] = None  # character description
  resources: Optional[List[str]] = field(default_factory=list)  # e.g., "healing potion", "gold coins"
  notes: Optional[str] = None  # additional notes about the character