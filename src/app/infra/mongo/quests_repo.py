from __future__ import annotations

from app.domain.models.EntityIDModel import QuestID
from app.domain.models.QuestModel import Quest
from app.infra.db import get_guild_db
from app.infra.serialization import from_bson, to_bson


def COLL(guild_id: int | str):
    return get_guild_db(guild_id)["quests"]


class QuestsRepoMongo:
    async def upsert(self, guild_id: int, quest: Quest) -> bool:
        doc = to_bson(quest)
        doc["guild_id"] = doc.get("guild_id") or int(guild_id)
        filt = {"guild_id": doc["guild_id"], "quest_id.value": doc["quest_id"]["value"]}
        await COLL(guild_id).replace_one(filt, doc, upsert=True)
        return True

    async def get(self, guild_id: int, quest_id: str) -> Quest | None:
        qid = QuestID.parse(quest_id)
        doc = await COLL(guild_id).find_one(
            {"guild_id": int(guild_id), "quest_id.value": qid.value}
        )
        return from_bson(Quest, doc) if doc else None

    async def delete(self, guild_id: int, quest_id: str) -> bool:
        qid = QuestID.parse(quest_id)
        res = await COLL(guild_id).delete_one(
            {"guild_id": int(guild_id), "quest_id.value": qid.value}
        )
        return res.deleted_count == 1

    async def exists(self, guild_id: int, quest_id: str) -> bool:
        qid = QuestID.parse(quest_id)
        count = await COLL(guild_id).count_documents(
            {"guild_id": int(guild_id), "quest_id.value": qid.value}, limit=1
        )
        return count > 0

    async def next_id(self, guild_id: int) -> str:
        while True:
            candidate = QuestID.generate()
            exists = await COLL(guild_id).count_documents(
                {"guild_id": int(guild_id), "quest_id.value": candidate.value},
                limit=1,
            )
            if not exists:
                return str(candidate)
