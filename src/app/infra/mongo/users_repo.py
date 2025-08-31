from __future__ import annotations
from app.infra.db import get_db, next_id
from app.domain.models.UserModel import User
from app.domain.models.EntityIDModel import UserID
from app.infra.serialization import to_bson, from_bson

def COLL():
    return get_db()["users"]

class UsersRepoMongo:
    async def upsert(self, user: User) -> bool:
        doc = to_bson(user)
        # Use your domain id as the natural key, NOT Mongo _id
        filt = {"user_id.number": doc["user_id"]["number"]}
        await COLL().replace_one(filt, doc, upsert=True)
        return True

    async def get(self, user_id: str) -> User | None:
        uid = UserID.parse(user_id)
        doc = await COLL().find_one({"user_id.number": uid.number})
        return from_bson(User, doc) if doc else None

    async def delete(self, user_id: str) -> bool:
        uid = UserID.parse(user_id)
        res = await COLL().delete_one({"user_id.number": uid.number})
        return res.deleted_count == 1

    async def exists(self, user_id: str) -> bool:
        uid = UserID.parse(user_id)
        count = await COLL().count_documents({"user_id.number": uid.number}, limit=1)
        return count > 0

    async def next_id(self) -> str:
        return str(await next_id(UserID))
