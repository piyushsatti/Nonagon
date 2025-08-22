from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List

class SummaryKind(str, Enum):
    PLAYER = "player"
    DM = "dm"  # dungeon master / referee

@dataclass
class QuestSummary:
    # identity / linkage
    summary_id: str
    quest_id: str
    author_user_id: str           # who wrote it (user id)
    kind: SummaryKind             # "player" or "dm"  ← discriminator

    # content
    summary_text: str
    posted_at: datetime

    # visibility / policy
    is_private: bool = False      # DM summaries default True if you want
    audience_roles: List[str] = field(default_factory=list)  # e.g., ["admin","referee"]

    # optional extras (safe defaults keep the schema stable)
    tags: List[str] = field(default_factory=list)
    reactions: Dict[str, int] = field(default_factory=dict)  # "like"->3, "star"->1
    edited_at: Optional[datetime] = None
    edited_by: Optional[str] = None