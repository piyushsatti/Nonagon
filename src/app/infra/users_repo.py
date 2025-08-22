# src/app/infra/users_repo.py
from __future__ import annotations
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.usecases.ports import UsersRepo, NotFoundError
from app.domain.models.UserModel import User  # <-- domain model

class MongoUsersRepo(UsersRepo):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["users"]

    async def get(self, user_id: str) -> User:
        doc = await self.col.find_one({"user_id": user_id})
        if not doc:
            raise NotFoundError(f"user {user_id} not found")
        return User.from_dict(doc)

    async def upsert(self, user: User) -> None:
        await self.col.update_one(
            {"user_id": user.user_id},
            {"$set": user.to_dict()},
            upsert=True,
        )

    async def exists(self, user_id: str) -> bool:
        doc = await self.col.find_one({"user_id": user_id}, {"_id": 1})
        return doc is not None
