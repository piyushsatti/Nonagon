# src/app/infra/quests_repo.py
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.usecases.ports import QuestsRepo, NotFoundError
from app.domain.models.QuestModel import Quest, QuestStatus

def _enum_to_value(x: Any) -> Any:
    return x.value if isinstance(x, Enum) else x

def _walk_to_bson(obj: Any) -> Any:
    if is_dataclass(obj):
        obj = asdict(obj)
    if isinstance(obj, dict):
        return {k: _walk_to_bson(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_to_bson(v) for v in obj]
    return _enum_to_value(obj)

def _from_bson_to_quest(doc: Dict[str, Any]) -> Quest:
    d = dict(doc)
    if "status" in d and not isinstance(d["status"], QuestStatus):
        d["status"] = QuestStatus(d["status"])
    # Prefer Quest.from_dict if present
    if hasattr(Quest, "from_dict"):
        return Quest.from_dict(d)  # type: ignore[attr-defined]
    return Quest(**d)

class MongoQuestsRepo(QuestsRepo):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["quests"]

    async def get(self, quest_id: str) -> Quest:
        doc = await self.col.find_one({"quest_id": quest_id})
        if not doc:
            raise NotFoundError(f"quest {quest_id} not found")
        return _from_bson_to_quest(doc)

    async def upsert(self, quest: Quest) -> None:
        payload = _walk_to_bson(quest)
        payload["_id"] = payload.get("quest_id")
        await self.col.update_one(
            {"quest_id": quest.quest_id}, {"$set": payload}, upsert=True
        )

    async def next_id(self) -> str:
        return uuid4().hex

    async def list_for_dm(
        self,
        dm_id: str,
        *,
        status: Optional[QuestStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Iterable[Quest]:
        q: Dict[str, Any] = {"dm_id": dm_id}
        if status:
            q["status"] = status.value
        cursor = self.col.find(q).sort("scheduled_at", 1).skip(skip).limit(limit)
        out: List[Quest] = []
        async for doc in cursor:
            out.append(_from_bson_to_quest(doc))
        return out
