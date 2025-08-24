from __future__ import annotations
from dataclasses import asdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.domain.usecases.ports import QuestsRepo, NotFoundError
from app.domain.models.quest.QuestModel import (
  Quest,
  QuestStatus,
  Signup,
  RosterEntry,
  SignupStatus,
)

# ─── helpers ───────────────────────────────────────────────────────────────────

def _enum_to_value(x: Any) -> Any:
  return x.value if isinstance(x, Enum) else x

def _walk_enums(obj: Any) -> Any:
  if isinstance(obj, dict):
    return {k: _walk_enums(v) for k, v in obj.items()}
  if isinstance(obj, list):
    return [_walk_enums(v) for v in obj]
  return _enum_to_value(obj)

def _dehydrate(q: Quest) -> Dict[str, Any]:
  d = asdict(q)
  d = _walk_enums(d)
  d["_id"] = d.get("quest_id")
  return d

def _hydrate(d: Dict[str, Any]) -> Quest:
  data = dict(d)
  data.pop("_id", None)

  if "status" in data and not isinstance(data["status"], QuestStatus):
    data["status"] = QuestStatus(data["status"])

  if "signups" in data and isinstance(data["signups"], list):
    fixed_signups: List[Signup] = []
    for s in data["signups"]:
      sd = dict(s)
      if "status" in sd and not isinstance(sd["status"], SignupStatus):
        sd["status"] = SignupStatus(sd["status"])
      fixed_signups.append(Signup(**sd))
    data["signups"] = fixed_signups

  if "roster" in data and isinstance(data["roster"], list):
    data["roster"] = [RosterEntry(**r) for r in data["roster"]]
  if "waitlist" in data and isinstance(data["waitlist"], list):
    data["waitlist"] = [RosterEntry(**r) for r in data["waitlist"]]

  return Quest(**data)

# ─── repo ──────────────────────────────────────────────────────────────────────

class MongoQuestsRepo(QuestsRepo):
  def __init__(self, db: AsyncIOMotorDatabase):
    self.col: AsyncIOMotorCollection = db["quests"]

  @classmethod
  async def create(cls, db: AsyncIOMotorDatabase) -> "MongoQuestsRepo":
    self = cls(db)
    await self.col.create_index("quest_id", unique=True)
    return self

  async def get(self, quest_id: str) -> Quest:
    doc = await self.col.find_one({"quest_id": quest_id})
    if not doc:
      raise NotFoundError(f"quest {quest_id} not found")
    return _hydrate(doc)

  async def upsert(self, quest: Quest) -> None:
    payload = _dehydrate(quest)
    await self.col.update_one(
      {"quest_id": quest.quest_id},
      {"$set": payload},
      upsert=True,
    )

  async def list_for_dm(
    self,
    dm_id: str,
    *,
    status: Optional[QuestStatus] = None,
    skip: int = 0,
    limit: int = 50,
  ) -> Iterable[Quest]:
    # domain uses referee_id; keep method name for compatibility
    q: Dict[str, Any] = {"referee_id": dm_id}
    if status:
      q["status"] = status.value
    cursor = self.col.find(q).sort("starting_at", 1).skip(skip).limit(limit)

    out: List[Quest] = []
    async for doc in cursor:
      out.append(_hydrate(doc))
    return out