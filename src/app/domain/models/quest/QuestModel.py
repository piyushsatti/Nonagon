from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional, Tuple, Dict

from app.domain.models.EntityIDModel import UserID, QuestID, CharacterID, SummaryID

class QuestStatus(Enum):
  DRAFT = "DRAFT"
  ANNOUNCED = "ANNOUNCED"
  SIGNUP_OPEN = "SIGNUP_OPEN"
  ROSTER_SELECTED = "ROSTER_SELECTED"
  RUNNING = "RUNNING"
  COMPLETED = "COMPLETED"
  CANCELLED = "CANCELLED"


class SignupStatus(Enum):
  APPLIED = "APPLIED"
  SELECTED = "SELECTED"
  WAITLISTED = "WAITLISTED"


@dataclass
class Signup:
  user_id: UserID
  character_id: CharacterID
  status: SignupStatus = SignupStatus.APPLIED


@dataclass
class RosterEntry:
  user_id: UserID
  player_id: UserID
  character_id: CharacterID
  selected_at: datetime


@dataclass
class Quest:
  # Identity / owner
  quest_id: QuestID
  referee_id: UserID  # DM/Referee responsible

  # Metadata
  title: str
  description: Optional[str] = None
  subtitle: Optional[str] = None
  starting_at: datetime = None
  duration: timedelta = None
  image_url: Optional[str] = None
  tags: Optional[List[str]] = field(default_factory=list)

  # Links
  linked_quests: Optional[List[QuestID]] = field(default_factory=list)
  linked_summaries: Optional[List[SummaryID]] = field(default_factory=list)

  # Discord linkage (domain keeps them as opaque references; adapters set them)
  guild_id: str = None
  channel_id: str = None
  signup_message_id: str = None
  thread_id: str = None

  # Lifecycle
  status: QuestStatus = QuestStatus.DRAFT
  started_at: Optional[datetime] = None
  ended_at: Optional[datetime] = None

  # Rostering & capacity
  signups: List[Signup] = field(default_factory=list)
  roster: List[RosterEntry] = field(default_factory=list)
  waitlist: List[RosterEntry] = field(default_factory=list)

  # Telemetry / follow-ups
  player_summary_needed: bool = True
  referee_summary_needed: bool = True

  # ────── Invariants / Behavior ──────
  def announce(self) -> None:
    """
    Option to reannounce a draft or announced quest.
    """
   
    if self.status not in {QuestStatus.DRAFT, QuestStatus.ANNOUNCED}:
      raise ValueError("Can only announce from DRAFT or ANNOUNCED.")
   
    self.status = QuestStatus.ANNOUNCED

  def open_signups(self) -> None:
   
    if self.status != QuestStatus.ANNOUNCED:
      raise ValueError("Can only open signups from ANNOUNCED.")
   
    self.status = QuestStatus.SIGNUP_OPEN

  def close_signups(self) -> None:
    
    if self.status != QuestStatus.SIGNUP_OPEN:
      raise ValueError("Can only close signups from SIGNUP_OPEN.")
    
    self.status = QuestStatus.ROSTER_SELECTED

  def mark_running(self) -> None:
    if self.status != QuestStatus.ROSTER_SELECTED:
        raise ValueError("Can only start running from ROSTER_SELECTED.")
    self.status = QuestStatus.RUNNING
    now = datetime.now(timezone.utc)
    self.started_at = now

  def mark_completed(self) -> None:
    if self.status != QuestStatus.RUNNING:
      raise ValueError("Can only complete from RUNNING.")
    now = datetime.now(timezone.utc)
    self.status = QuestStatus.COMPLETED
    self.ended_at = now
    # trigger follow-ups
    self.player_summary_needed = True
    self.referee_summary_needed = True

  def cancel(self, reason: str) -> None:
    if self.status in {QuestStatus.DRAFT, QuestStatus.COMPLETED, QuestStatus.CANCELLED}:
      raise ValueError("Quest already completed or cancelled.")
    self.status = QuestStatus.CANCELLED

  def add_signup(
        self, 
        user_id: UserID, 
        character_id: CharacterID
    ) -> None:
    
    if self.status != QuestStatus.SIGNUP_OPEN:
      raise ValueError("Signups are not open.")
    
    key = (str(user_id), str(character_id))
    if any((str(s.user_id), str(s.character_id)) == key for s in self.signups):
      return # already signed up
    
    self.signups.append(Signup(user_id=user_id, character_id=character_id))

  def select_roster(
      self,
      selected: List[Tuple[UserID, CharacterID]],
      waitlisted: Optional[List[Tuple[UserID, CharacterID]]] = None,
  ) -> None:
    if self.status != QuestStatus.SIGNUP_OPEN:
      raise ValueError("Can only select roster when signups are open.")

    self.roster = [RosterEntry(u, c) for (u, c) in selected]
    self.waitlist = [RosterEntry(u, c) for (u, c) in waitlisted]
    self.status = QuestStatus.ROSTER_SELECTED

    # mirror statuses to signups
    by_key: Dict[Tuple[str, str], Signup] = {
      (str(s.user_id), str(s.character_id)): s for s in self.signups
    }
    
    for u, c in selected:
      k = (str(u), str(c))
      if k in by_key:
        by_key[k].status = SignupStatus.SELECTED

    for u, c in (waitlisted or []):
      k = (str(u), str(c))
      if k in by_key:
        by_key[k].status = SignupStatus.WAITLISTED
