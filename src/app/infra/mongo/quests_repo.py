from __future__ import annotations
from app.infra.db import get_db, next_id
from app.domain.models.QuestModel import Quest
from app.domain.models.EntityIDModel import QuestID
from app.infra.serialization import to_bson, from_bson

def COLL():
    return get_db()["quests"]

class QuestsRepoMongo:
    async def upsert(self, quest: Quest) -> bool:
        doc = to_bson(quest)
        filt = {"quest_id.number": doc["quest_id"]["number"]}
        await COLL().replace_one(filt, doc, upsert=True)
        return True

    async def get(self, quest_id: str) -> Quest | None:
        qid = QuestID.parse(quest_id)
        doc = await COLL().find_one({"quest_id.number": qid.number})
        return from_bson(Quest, doc) if doc else None

    async def delete(self, quest_id: str) -> bool:
        qid = QuestID.parse(quest_id)
        res = await COLL().delete_one({"quest_id.number": qid.number})
        return res.deleted_count == 1

    async def exists(self, quest_id: str) -> bool:
        qid = QuestID.parse(quest_id)
        count = await COLL().count_documents({"quest_id.number": qid.number}, limit=1)
        return count > 0

    async def next_id(self) -> str:
        return str(await next_id(QuestID))
