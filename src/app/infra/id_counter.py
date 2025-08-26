from typing import Type, TypeVar
from pymongo import ReturnDocument
from app.domain.models.EntityIDModel import EntityID
from app.infra.db import get_db

T = TypeVar("T", bound=EntityID)

async def next_id(id_cls: Type[T]) -> T:
  db = get_db()
  doc = await db["counters"].find_one_and_update(
    {"_id": id_cls.prefix},
    {"$inc": {"seq": 1}},
    upsert=True,
    return_document=ReturnDocument.AFTER,
  )
  return id_cls(number=int(doc["seq"]))