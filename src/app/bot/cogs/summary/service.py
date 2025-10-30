from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

import discord

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.SummaryModel import QuestSummary, SummaryKind, SummaryStatus
from app.infra.serialization import to_bson


class SummaryService:
    """Data-layer helpers for summary commands."""

    def __init__(self, bot: discord.Client) -> None:
        self._bot = bot

    async def ensure_guild_cache(self, guild: discord.Guild) -> None:
        if guild.id not in getattr(self._bot, "guild_data", {}):
            load_cache = getattr(self._bot, "load_or_create_guild_cache", None)
            if load_cache is None:
                raise RuntimeError("Bot is missing load_or_create_guild_cache.")
            await load_cache(guild)

    def lookup_user_display(self, guild_id: int, user_id: Optional[UserID]) -> str:
        if user_id is None:
            return "Unknown"
        guild_entry = self._guild_entry(guild_id, default={})
        users = guild_entry.get("users", {})
        for cached in users.values():
            try:
                if cached.user_id == user_id:
                    if cached.discord_id:
                        return f"<@{cached.discord_id}>"
                    return str(cached.user_id)
            except AttributeError:
                continue
        return str(user_id)

    def persist_summary(self, guild_id: int, summary: QuestSummary) -> None:
        summary.guild_id = guild_id
        guild_entry = self._guild_entry(guild_id)
        db = guild_entry["db"]
        payload = self.summary_to_doc(summary)
        db["summaries"].update_one(
            {"guild_id": guild_id, "summary_id.value": str(summary.summary_id)},
            {"$set": payload},
            upsert=True,
        )

    def fetch_summary(
        self, guild_id: int, summary_id: SummaryID
    ) -> Optional[QuestSummary]:
        guild_entry = self._guild_entry(guild_id)
        db = guild_entry["db"]
        doc = db["summaries"].find_one(
            {
                "guild_id": guild_id,
                "$or": [
                    {"summary_id.value": str(summary_id)},
                    {"_id": str(summary_id)},
                ],
            }
        )
        if not doc:
            return None
        return self.summary_from_doc(guild_id, doc)

    async def next_summary_id(self, guild: discord.Guild) -> SummaryID:
        await self.ensure_guild_cache(guild)
        guild_entry = self._guild_entry(guild.id)
        db = guild_entry["db"]
        coll = db["summaries"]
        while True:
            candidate = SummaryID.generate()
            exists = coll.count_documents(
                {"guild_id": guild.id, "summary_id.value": str(candidate)}, limit=1
            )
            if not exists:
                return candidate

    def summary_to_doc(self, summary: QuestSummary) -> dict:
        payload = to_bson(summary)
        payload["summary_id"] = {"value": str(summary.summary_id)}
        payload["guild_id"] = int(summary.guild_id)
        return payload

    def summary_from_doc(self, guild_id: int, doc: dict) -> QuestSummary:
        summary_id = self.parse_entity_id(
            SummaryID, doc.get("summary_id")
        ) or SummaryID.parse(str(doc.get("_id")))
        kind_payload = doc.get("kind") or SummaryKind.PLAYER
        try:
            kind = (
                kind_payload
                if isinstance(kind_payload, SummaryKind)
                else SummaryKind(kind_payload)
            )
        except ValueError:
            kind = SummaryKind.PLAYER

        summary = QuestSummary(
            summary_id=summary_id,
            kind=kind,
            author_id=self.parse_entity_id(UserID, doc.get("author_id")),
            character_id=self.parse_entity_id(CharacterID, doc.get("character_id")),
            quest_id=self.parse_entity_id(QuestID, doc.get("quest_id")),
            guild_id=int(doc.get("guild_id", guild_id)),
            raw=doc.get("raw"),
            title=doc.get("title"),
            description=doc.get("description"),
            created_on=doc.get("created_on") or datetime.now(timezone.utc),
        )

        summary.last_edited_at = doc.get("last_edited_at")
        summary.players = [
            self.parse_entity_id(UserID, entry)
            for entry in doc.get("players", [])
            if self.parse_entity_id(UserID, entry) is not None
        ]
        summary.characters = [
            self.parse_entity_id(CharacterID, entry)
            for entry in doc.get("characters", [])
            if self.parse_entity_id(CharacterID, entry) is not None
        ]
        summary.linked_quests = [
            self.parse_entity_id(QuestID, entry)
            for entry in doc.get("linked_quests", [])
            if self.parse_entity_id(QuestID, entry) is not None
        ]
        summary.linked_summaries = [
            self.parse_entity_id(SummaryID, entry)
            for entry in doc.get("linked_summaries", [])
            if self.parse_entity_id(SummaryID, entry) is not None
        ]

        summary.channel_id = doc.get("channel_id")
        summary.message_id = doc.get("message_id")
        summary.thread_id = doc.get("thread_id")

        status_raw = doc.get("status")
        if status_raw:
            try:
                summary.status = (
                    status_raw
                    if isinstance(status_raw, SummaryStatus)
                    else SummaryStatus(status_raw)
                )
            except ValueError:
                summary.status = SummaryStatus.POSTED
        return summary

    def parse_entity_id(self, cls, payload: object) -> Optional[object]:
        if payload is None:
            return None
        if isinstance(payload, cls):
            return payload
        if isinstance(payload, dict):
            value = payload.get("value")
            if isinstance(value, str) and value:
                return cls.parse(value)
            number = payload.get("number")
            if number is not None:
                prefix = payload.get("prefix", cls.prefix)
                return cls.parse(f"{prefix}{number}")
        if isinstance(payload, str) and payload:
            return cls.parse(payload)
        if isinstance(payload, int):
            return cls.parse(f"{cls.prefix}{payload}")
        return None

    def _guild_entry(self, guild_id: int, default: Optional[Dict] = None) -> Dict:
        guild_data = getattr(self._bot, "guild_data", None)
        if guild_data is None:
            if default is not None:
                return default
            raise RuntimeError("Bot has no guild_data attribute.")
        if guild_id not in guild_data:
            if default is not None:
                return default
            raise RuntimeError(f"No guild cache entry for guild {guild_id}.")
        return guild_data[guild_id]


__all__ = ["SummaryService"]
