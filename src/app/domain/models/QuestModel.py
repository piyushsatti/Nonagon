from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID


class QuestStatus(Enum):
	DRAFT = "DRAFT"
	ANNOUNCED = "ANNOUNCED"
	SIGNUP_CLOSED = "SIGNUP_CLOSED"
	COMPLETED = "COMPLETED"
	CANCELLED = "CANCELLED"


class PlayerStatus(Enum):
	APPLIED = "APPLIED"
	SELECTED = "SELECTED"


@dataclass
class Quest:
	# Identity / owner
	quest_id: QuestID
	guild_id: int
	referee_id: UserID  # Referee responsible
	channel_id: str | None = None
	message_id: str | None = None

	# Metadata
	raw: str  # raw markdown input
	title: str = None
	description: str = None
	starting_at: datetime = None
	duration: timedelta = None
	image_url: str = None

	# Links
	linked_quests: List[QuestID] = field(default_factory=list)
	linked_summaries: List[SummaryID] = field(default_factory=list)

	# Lifecycle
	status: QuestStatus = QuestStatus.DRAFT
	announce_at: datetime | None = None
	started_at: datetime = None
	ended_at: datetime = None
	signups: List[PlayerSignUp] = field(default_factory=list)
	last_nudged_at: datetime = None

	# ------- Status Helpers -------
	def set_completed(self) -> None:
		self.status = QuestStatus.COMPLETED

	def set_cancelled(self) -> None:
		self.status = QuestStatus.CANCELLED

	def set_announced(self) -> None:
		self.status = QuestStatus.ANNOUNCED

	def set_draft(self) -> None:
		self.status = QuestStatus.DRAFT

	def close_signups(self) -> None:
		self.status = QuestStatus.SIGNUP_CLOSED

	# ------- Property Helpers -------

	@property
	def is_summary_needed(self) -> bool:
		return self.status is QuestStatus.COMPLETED and len(self.linked_summaries) == 0

	@property
	def is_signup_open(self) -> bool:
		return self.status is QuestStatus.ANNOUNCED

	# ------- Signup Helpers -------

	def add_signup(self, user_id: UserID, character_id: CharacterID) -> None:
		for s in self.signups:
			if s.user_id == user_id:
				raise ValueError(f"User {user_id} already signed up")

		self.signups.append(PlayerSignUp(user_id=user_id, character_id=character_id))

	def remove_signup(self, user_id: UserID) -> None:
		for s in self.signups:
			if s.user_id == user_id:
				self.signups.remove(s)
				return

		raise ValueError(f"User {user_id} not signed up")

	def select_signup(self, user_id: UserID) -> None:
		for s in self.signups:
			if s.user_id == user_id:
				s.status = PlayerStatus.SELECTED
				return

		raise ValueError(f"User {user_id} not signed up")

	# ---------- Helpers ----------

	def validate_quest(self) -> None:

		if self.starting_at and self.duration:
			if self.duration < timedelta(minutes=60):
				raise ValueError("Duration must be at least 60 minutes.")

		if self.starting_at and self.starting_at < datetime.now():
			raise ValueError("Starting time must be in the future.")

		if self.duration and self.duration < timedelta(minutes=15):
			raise ValueError("Duration must be at least 15 minutes.")

		if self.image_url and not (
			self.image_url.startswith("http://")
			or self.image_url.startswith("https://")
		):
			raise ValueError("Image URL must start with http:// or https://")

	def from_dict(self, data: Dict[str, any]) -> Quest:
		valid = {f.name for f in fields(self.__dict__)}
		filtered = {k: v for k, v in data.items() if k in valid}
		return replace(self, **filtered)

	def to_dict(self) -> Dict[str, any]:
		return asdict(self)


@dataclass
class PlayerSignUp:
	user_id: UserID
	character_id: CharacterID
	status: PlayerStatus = PlayerStatus.APPLIED
