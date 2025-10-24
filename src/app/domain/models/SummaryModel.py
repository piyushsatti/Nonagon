from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from enum import Enum
from typing import Dict, List

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID


class SummaryKind(str, Enum):
    PLAYER = "PLAYER"
    REFEREE = "REFEREE"


@dataclass
class QuestSummary:

    summary_id: SummaryID
    kind: SummaryKind
    author_id: UserID
    character_id: CharacterID
    quest_id: QuestID
    guild_id: int
    # Content
    raw: str
    title: str
    description: str
    created_on: datetime

    # Telemetry
    last_edited_at: datetime | None = None
    players: List[UserID] = field(default_factory=list)
    characters: List[CharacterID] = field(default_factory=list)

    # Links
    linked_quests: List[QuestID] = field(default_factory=list)
    linked_summaries: List[SummaryID] = field(default_factory=list)

    # ---------- Helpers ----------
    def from_dict(self, data: Dict[str, any]) -> QuestSummary:
        valid = {f.name for f in fields(self.__dict__)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, any]:
        return asdict(self)

    # ---------- Validation ----------
    def validate_summary(self) -> None:
        if self.kind not in (SummaryKind.PLAYER, SummaryKind.REFEREE):
            raise ValueError(f"Invalid summary kind: {self.kind}")

        if not self.title or not self.title.strip():
            raise ValueError("Summary title cannot be empty")

        if not self.description or not self.description.strip():
            raise ValueError("Summary description cannot be empty")

        if self.created_on is None:
            raise ValueError("created_on must be set")

        if self.author_id is None:
            raise ValueError("author_id must be set")

        if self.character_id is None:
            raise ValueError("character_id must be set")

        if self.quest_id is None:
            raise ValueError("quest_id must be set")

        if not self.raw or not self.raw.strip():
            raise ValueError("Summary content cannot be empty")

        if not self.players or len(self.players) == 0:
            raise ValueError("At least one player must be associated with the summary")

        if not self.characters or len(self.characters) == 0:
            raise ValueError(
                "At least one character must be associated with the summary"
            )

        if self.last_edited_at is not None and self.last_edited_at < self.created_on:
            raise ValueError("last_edited_at cannot be before created_on")
