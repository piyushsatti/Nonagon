from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.bot.settings import GuildBotSettings


class BotSettingsRepository:
    """Persistence layer for Discord bot guild settings."""

    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self._collection: AsyncIOMotorCollection[Any] = db["bot_settings"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [("quest_channel_id", ASCENDING)],
            name="ix_bot_settings_quest_channel",
            partialFilterExpression={
                "quest_channel_id": {"$exists": True, "$ne": None}
            },
        )
        await self._collection.create_index(
            [("summary_channel_id", ASCENDING)],
            name="ix_bot_settings_summary_channel",
            partialFilterExpression={
                "summary_channel_id": {"$exists": True, "$ne": None}
            },
        )
        await self._collection.create_index(
            [("player_role_id", ASCENDING)],
            name="ix_bot_settings_player_role",
            partialFilterExpression={"player_role_id": {"$exists": True, "$ne": None}},
        )
        await self._collection.create_index(
            [("referee_role_id", ASCENDING)],
            name="ix_bot_settings_referee_role",
            partialFilterExpression={"referee_role_id": {"$exists": True, "$ne": None}},
        )

    async def get(self, guild_id: int) -> GuildBotSettings | None:
        doc = await self._collection.find_one({"_id": guild_id})
        if doc is None:
            return None
        return self._decode(doc)

    async def upsert(self, settings: GuildBotSettings) -> GuildBotSettings:
        payload = self._encode(settings)
        await self._collection.replace_one(
            {"_id": settings.guild_id}, payload, upsert=True
        )
        return settings

    @staticmethod
    def _encode(settings: GuildBotSettings) -> dict[str, Any]:
        return {
            "_id": settings.guild_id,
            "quest_channel_id": settings.quest_channel_id,
            "summary_channel_id": settings.summary_channel_id,
            "player_role_id": settings.player_role_id,
            "referee_role_id": settings.referee_role_id,
        }

    @staticmethod
    def _decode(doc: dict[str, Any]) -> GuildBotSettings:
        return GuildBotSettings(
            guild_id=int(doc["_id"]),
            quest_channel_id=_maybe_int(doc.get("quest_channel_id")),
            summary_channel_id=_maybe_int(doc.get("summary_channel_id")),
            player_role_id=_maybe_int(doc.get("player_role_id")),
            referee_role_id=_maybe_int(doc.get("referee_role_id")),
        )


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None
