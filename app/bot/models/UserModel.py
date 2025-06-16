from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime
from typing import Dict, Optional, Any
from discord import Member

@dataclass
class User:
  # ─── Identity ─────────────────────────────────────────────────
  user_id: int | None = None
  dm_channel_id: int | None = None

  # ─── Timestamps / basic stats ────────────────────────────────
  joined_at: datetime | None = None
  last_active_at: datetime | None = None

  # ─── Engagement telemetry ────────────────────────────────────
  messages_count_total:   int = 0
  reactions_given:        int = 0
  reactions_received:     int = 0
  voice_total_time_spent: int = 0
  events_attended:        int = 0
  events_organized:       int = 0

  # ─── Fun counters ────────────────────────────────────────────
  fun_count_banned:   int = 0
  fun_count_liked:    int = 0
  fun_count_disliked: int = 0
  fun_count_kek:      int = 0
  fun_count_true:     int = 0
  fun_count_heart:    int = 0

  # ─── Dict fields need default_factory ────────────────────────
  messages_count_by_category: Dict[int, int] = field(default_factory=dict)
  voice_time_by_channel:      Dict[str, float] = field(default_factory=dict)

  # ---------- factory constructors -----------------------------
  @classmethod
  def from_member(cls, m: Member) -> User:
    return cls(
      user_id        = m.id,
      dm_channel_id  = m.dm_channel.id if m.dm_channel else None,
      joined_at      = m.joined_at or datetime.utcnow(),
      last_active_at = datetime.utcnow(),
    )

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> User:
    empty = cls()
    valid = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(empty, **filtered)

  # ---------- update helper ------------------------------------
  def update_from_dict(self, data: dict[str, Any]) -> None:
    for key, val in data.items():
      if key in self.__dataclass_fields__:
        setattr(self, key, val)
