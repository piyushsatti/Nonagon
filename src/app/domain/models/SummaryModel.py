from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID


class SummaryKind(str, Enum):
	PLAYER = "PLAYER"
	REFEREE = "REFEREE"


class SummaryStatus(str, Enum):
	POSTED = "POSTED"
	CANCELLED = "CANCELLED"


@dataclass
class QuestSummary:

	summary_id: SummaryID
	kind: SummaryKind = SummaryKind.PLAYER
	author_id: Optional[UserID] = None
	character_id: Optional[CharacterID] = None
	quest_id: Optional[QuestID] = None
	guild_id: int = 0

	# Content
	raw: Optional[str] = None
	title: Optional[str] = None
	description: Optional[str] = None
	created_on: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

	# Telemetry
	last_edited_at: Optional[datetime] = None
	players: List[UserID] = field(default_factory=list)
	characters: List[CharacterID] = field(default_factory=list)

	# Links
	linked_quests: List[QuestID] = field(default_factory=list)
	linked_summaries: List[SummaryID] = field(default_factory=list)

	# Announcement metadata
	channel_id: Optional[str] = None
	message_id: Optional[str] = None
	thread_id: Optional[str] = None
	status: SummaryStatus = SummaryStatus.POSTED

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

		if not self.title or not str(self.title).strip():
			raise ValueError("Summary title cannot be empty")

		if not self.description or not str(self.description).strip():
			raise ValueError("Summary description cannot be empty")

		if self.created_on is None:
			raise ValueError("created_on must be set")

		if self.author_id is None:
			raise ValueError("author_id must be set")

		self.raw = self.raw or ""

		if not self.characters or len(self.characters) == 0:
			raise ValueError(
				"At least one character must be associated with the summary"
			)

		if self.last_edited_at is not None and self.last_edited_at < self.created_on:
			raise ValueError("last_edited_at cannot be before created_on")

		if self.status not in (SummaryStatus.POSTED, SummaryStatus.CANCELLED):
			raise ValueError(f"Invalid summary status: {self.status}")

		# Ensure players list always contains the author if provided
		if self.author_id is not None:
			if self.players is None:
				self.players = [self.author_id]
			elif self.author_id not in self.players:
				self.players.append(self.author_id)

	def set_cancelled(self) -> None:
		self.status = SummaryStatus.CANCELLED
