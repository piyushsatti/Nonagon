from typing import Type, TypeVar
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.domain.models.EntityIDModel import EntityID

T = TypeVar("T", bound=EntityID)

async def _next_number(db: AsyncIOMotorDatabase, prefix: str) -> int:
  doc = await db["counters"].find_one_and_update(
    {"_id": prefix},
    {"$inc": {"seq": 1}},
    upsert=True,
    return_document=ReturnDocument.AFTER,
  )
  return int(doc["seq"])

async def next_id(db: AsyncIOMotorDatabase, id_cls: Type[T]) -> T:
  n = await _next_number(db, id_cls.prefix)
  return id_cls(number=n)