from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID


class CharacterRole(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


def _default_tags() -> list[str]:
    return []


def _default_character_ids() -> list[CharacterID]:
    return []


def _default_quest_ids() -> list[QuestID]:
    return []


def _default_summary_ids() -> list[SummaryID]:
    return []


@dataclass(slots=True)
class Character:
    owner_id: UserID
    character_id: str
    name: str
    ddb_link: str
    character_thread_link: str
    token_link: str
    art_link: str
    status: CharacterRole = CharacterRole.ACTIVE
    created_at: datetime | None = None
    last_played_at: datetime | None = None
    description: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=_default_tags)
    played_with: list[CharacterID] = field(default_factory=_default_character_ids)
    played_in: list[QuestID] = field(default_factory=_default_quest_ids)
    mentioned_in: list[SummaryID] = field(default_factory=_default_summary_ids)

    quests_played: int = 0
    summaries_written: int = 0

    # ---------- Helpers ----------

    def from_dict(self, data: Dict[str, Any]) -> "Character":
        valid = {f.name for f in fields(self)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # ---------- Tag Management ----------
    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        if tag in self.tags:
            self.tags.remove(tag)

    # ------- Active Management -------
    def is_active(self) -> bool:
        return self.status is CharacterRole.ACTIVE

    def activate(self) -> None:
        self.status = CharacterRole.ACTIVE

    def deactivate(self) -> None:
        self.status = CharacterRole.INACTIVE

    # ---------- Data ----------
    def change_attributes(
        self,
        name: str | None = None,
        ddb_link: str | None = None,
        character_thread_link: str | None = None,
        token_link: str | None = None,
        art_link: str | None = None,
        description: str | None = None,
        notes: str | None = None,
    ) -> None:

        if name is not None:
            self.name = name

        if ddb_link is not None:
            self.ddb_link = ddb_link

        if character_thread_link is not None:
            self.character_thread_link = character_thread_link

        if token_link is not None:
            self.token_link = token_link

        if art_link is not None:
            self.art_link = art_link

        if description is not None:
            self.description = description

        if notes is not None:
            self.notes = notes

    # ---------- Telemetry ----------
    def set_created_at(self, created_at: datetime, override: bool = False) -> None:

        if self.created_at is not None and not override:
            raise ValueError(
                "created_at is already set. Use override=True to force change."
            )

        self.created_at = created_at

    def update_last_played(self, played_at: datetime) -> None:

        if self.created_at is None:
            raise ValueError("created_at must be set before setting last_played_at")

        if played_at < self.created_at:
            raise ValueError("last_played_at cannot be before created_at")

        self.last_played_at = played_at

    def set_quests_played(self, count: int) -> None:

        if count < 0:
            raise ValueError("quests_played cannot be negative")

        self.quests_played = count

    def set_summaries_written(self, count: int) -> None:

        if count < 0:
            raise ValueError("summaries_written cannot be negative")

        self.summaries_written = count

    def increment_quests_played(self) -> None:
        self.quests_played += 1

    def increment_summaries_written(self) -> None:
        self.summaries_written += 1

    # ---------- Links ----------
    def add_played_with(self, other_char_id: CharacterID) -> None:

        if other_char_id not in self.played_with:
            self.played_with.append(other_char_id)

    def add_played_in(self, quest_id: QuestID) -> None:

        if quest_id not in self.played_in:
            self.played_in.append(quest_id)

    def add_mentioned_in(self, summary_id: SummaryID) -> None:

        if summary_id not in self.mentioned_in:
            self.mentioned_in.append(summary_id)

    def remove_played_with(self, other_char_id: CharacterID) -> None:

        if other_char_id in self.played_with:
            self.played_with.remove(other_char_id)

    def remove_played_in(self, quest_id: QuestID) -> None:

        if quest_id in self.played_in:
            self.played_in.remove(quest_id)

    def remove_mentioned_in(self, summary_id: SummaryID) -> None:

        if summary_id in self.mentioned_in:
            self.mentioned_in.remove(summary_id)

    # ---------- Validation ----------
    def validate_character(self) -> None:

        if not self.name or not self.name.strip():
            raise ValueError("Character name cannot be empty")

        if not self.ddb_link or not self.ddb_link.strip():
            raise ValueError("DDB link cannot be empty")

        if not self.character_thread_link or not self.character_thread_link.strip():
            raise ValueError("Character thread link cannot be empty")

        if not self.token_link or not self.token_link.strip():
            raise ValueError("Token link cannot be empty")

        if not self.art_link or not self.art_link.strip():
            raise ValueError("Art link cannot be empty")

        if self.status not in (CharacterRole.ACTIVE, CharacterRole.INACTIVE):
            raise ValueError(f"Invalid character status: {self.status}")

        if self.created_at is None:
            raise ValueError("created_at must be set")
