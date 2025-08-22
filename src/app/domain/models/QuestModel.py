from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Tuple


# ─────────────────────────────────────────────────────────────
# Lifecycle & sign-up enums (stable, importable across modules)
# ─────────────────────────────────────────────────────────────
class QuestStatus(str, Enum):
    DRAFT = "draft"                  # created, not announced
    ANNOUNCED = "announced"          # sign-up post published
    SIGNUP_OPEN = "signup_open"      # collecting sign-ups
    ROSTER_SELECTED = "roster_selected"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SignupStatus(str, Enum):
    APPLIED = "applied"      # player applied for the quest
    SELECTED = "selected"    # chosen by referee
    WAITLISTED = "waitlisted"
    DECLINED = "declined"    # explicitly not selected (optional use)
    WITHDRAWN = "withdrawn"  # player withdrew
    NO_SHOW = "no_show"      # did not attend (post-session hygiene)


# ─────────────────────────────────────────────────────────────
# Value objects used inside Quest
# ─────────────────────────────────────────────────────────────
@dataclass
class Signup:
    user_id: str
    character_id: str
    status: SignupStatus = SignupStatus.APPLIED
    applied_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    note: Optional[str] = None  # e.g., availability, lines/veils summary


@dataclass
class RosterEntry:
    user_id: str
    character_id: str
    selected_at: datetime = field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# Quest model
# ─────────────────────────────────────────────────────────────
@dataclass
class Quest:
    # identity & core
    quest_id: str
    name: str
    dm_id: str                              # referee user id
    description: Optional[str] = None
    category: Optional[str] = None          # e.g., "one-shot", "campaign", "event"
    tags: List[str] = field(default_factory=list)  # free-form discoverability

    # scheduling
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    timezone: Optional[str] = None          # if you need per-quest TZ

    # capacity & constraints
    max_players: int = 5
    min_players: int = 3
    level_min: Optional[int] = None
    level_max: Optional[int] = None
    region: Optional[str] = None            # for your “games_run_by_region” analytics

    # Discord linkage (lets automation edit/update the original post & controls)
    guild_id: Optional[int] = None
    channel_id: Optional[int] = None
    signup_message_id: Optional[int] = None   # message with buttons/select menus
    thread_id: Optional[int] = None           # if you spin up a thread for Q&A

    # lifecycle
    status: QuestStatus = QuestStatus.DRAFT
    status_updated_at: datetime = field(default_factory=datetime.utcnow)
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    # sign-ups & roster
    signups: List[Signup] = field(default_factory=list)      # all applicants (history preserved)
    roster: List[RosterEntry] = field(default_factory=list)  # final selected players
    waitlist: List[RosterEntry] = field(default_factory=list)

    # rewards / outcomes
    xp_reward: Optional[int] = None
    gp_reward: Optional[int] = None
    summary_needed: bool = False

    # summaries (unified summary ids; the Summary object carries kind=player|dm)
    summary_ids: List[str] = field(default_factory=list)

    # telemetry (for PRD analytics)
    attendees: List[Tuple[str, str]] = field(default_factory=list)  # (user_id, character_id) who actually played
    sessions_cancelled_count: int = 0

    # housekeeping
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    last_updated_by: Optional[str] = None

    # ────── helpers / invariants you can enforce in services ──────
    def open_signups(self) -> None:
        self.status = QuestStatus.SIGNUP_OPEN
        self.status_updated_at = datetime.utcnow()
        self.updated_at = self.status_updated_at

    def select_roster(self, selected: List[Tuple[str, str]], waitlisted: List[Tuple[str, str]] = None) -> None:
        """selected/waitlisted are lists of (user_id, character_id)."""
        now = datetime.utcnow()
        self.roster = [RosterEntry(u, c, now) for (u, c) in selected]
        self.waitlist = [RosterEntry(u, c, now) for (u, c) in (waitlisted or [])]
        self.status = QuestStatus.ROSTER_SELECTED
        self.status_updated_at = now
        self.updated_at = now

        # update corresponding signup statuses
        by_key = {(s.user_id, s.character_id): s for s in self.signups}
        for u, c in selected:
            if (u, c) in by_key:
                by_key[(u, c)].status = SignupStatus.SELECTED
                by_key[(u, c)].updated_at = now
        for u, c in (waitlisted or []):
            if (u, c) in by_key:
                by_key[(u, c)].status = SignupStatus.WAITLISTED
                by_key[(u, c)].updated_at = now

    def mark_running(self) -> None:
        now = datetime.utcnow()
        self.status = QuestStatus.RUNNING
        self.started_at = now
        self.status_updated_at = now
        self.updated_at = now

    def mark_completed(self) -> None:
        now = datetime.utcnow()
        self.status = QuestStatus.COMPLETED
        self.ended_at = now
        self.status_updated_at = now
        self.updated_at = now
        self.summary_needed = True  # nudge automation/workflows

    def cancel(self, reason: str) -> None:
        now = datetime.utcnow()
        self.status = QuestStatus.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = now
        self.status_updated_at = now
        self.updated_at = now
        self.sessions_cancelled_count += 1

    def capacity_remaining(self) -> int:
        return max(0, self.max_players - len(self.roster))

    def is_signup_open(self) -> bool:
        return self.status == QuestStatus.SIGNUP_OPEN

    def add_signup(self, user_id: str, character_id: str, note: Optional[str] = None) -> None:
        now = datetime.utcnow()
        self.signups.append(Signup(user_id=user_id, character_id=character_id, note=note, applied_at=now, updated_at=now))
        self.updated_at = now
