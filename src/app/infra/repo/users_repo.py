from __future__ import annotations

from typing import Any, Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.domain.usecase.ports import UsersRepo, NotFoundError
from app.domain.models.UserModel import User, Role

class MongoUsersRepo(UsersRepo):
  def __init__(self, db: AsyncIOMotorDatabase):
    self.col: AsyncIOMotorCollection = db["users"]

  @classmethod
  async def create(cls, db: AsyncIOMotorDatabase) -> MongoUsersRepo:
    self = cls(db)
    await self.col.create_index("user_id", unique=True)
    return self

  # ---------- mapping helpers ----------
  def _hydrate(self, doc: Dict[str, Any]) -> User:
    d = dict(doc)
    d.pop("_id", None)
    roles = d.get("roles")
    if roles is not None:
      fixed: List[Role] = []
      for r in roles:
        if isinstance(r, Role):
          fixed.append(r)
        else:
          try:
            fixed.append(Role(r))
          except Exception:
            pass
      d["roles"] = fixed

    return User(**d)

  def _dehydrate(self, user: User) -> Dict[str, Any]:
    data = user.to_dict()
    data["roles"] = [
      (r.value if isinstance(r, Role) else r) for r in data.get("roles", [])
    ]
    return {k: v for k, v in data.items() if v is not None}

  # ---------- repo API ----------

  async def get(self, user_id: str) -> User:
    doc = await self.col.find_one({"user_id": user_id})
    if not doc:
      raise NotFoundError(f"user {user_id} not found")
    return self._hydrate(doc)

  async def upsert(self, user: User) -> None:
    payload = self._dehydrate(user)
    await self.col.update_one(
      {"user_id": user.user_id},
      {"$set": payload},
      upsert=True,
    )

  async def exists(self, user_id: str) -> bool:
    doc = await self.col.find_one({"user_id": user_id}, {"_id": 1})
    return doc is not None
