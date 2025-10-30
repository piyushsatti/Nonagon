"""Service helpers backing the character cog."""

from __future__ import annotations

from typing import Dict, List, Optional

import discord

from app.domain.models.CharacterModel import Character, CharacterRole
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.infra.mongo.guild_adapter import upsert_character_sync
from app.infra.serialization import from_bson, to_bson


class CharacterService:
    """Persistence and cache helpers for character commands.

    Instances are intended to be injected into ``CharacterCommandsCog``. They
    accept a custom ``db_client`` or ``flush_via_adapter`` flag to mirror the
    runtime settings while staying easy to stub in tests.
    """

    def __init__(
        self,
        bot: discord.Client,
        *,
        flush_via_adapter: bool = False,
        db_client=None,
    ) -> None:
        self._bot = bot
        self._flush_via_adapter = flush_via_adapter
        if db_client is None:
            from app.bot.database import db_client as default_db_client  # lazy import

            db_client = default_db_client
        self._db_client = db_client

    async def ensure_guild_cache(self, guild: discord.Guild) -> None:
        if guild.id not in getattr(self._bot, "guild_data", {}):
            load_cache = getattr(self._bot, "load_or_create_guild_cache", None)
            if load_cache is None:
                raise RuntimeError("Bot is missing load_or_create_guild_cache.")
            await load_cache(guild)

    def _guild_entry(self, guild_id: int) -> Dict:
        guild_data = getattr(self._bot, "guild_data", None)
        if guild_data is None:
            raise RuntimeError("Bot has no guild_data attribute.")
        return guild_data[guild_id]

    async def fetch_character(
        self, guild: discord.Guild, raw_character_id: str
    ) -> Optional[Character]:
        await self.ensure_guild_cache(guild)
        guild_entry = self._guild_entry(guild.id)
        db = guild_entry["db"]
        try:
            normalized = str(CharacterID.parse(raw_character_id))
        except Exception:
            normalized = raw_character_id.strip().upper()

        doc = db["characters"].find_one(
            {"guild_id": guild.id, "character_id": normalized}
        )
        if doc is None:
            doc = db["characters"].find_one(
                {"guild_id": guild.id, "character_id.value": normalized}
            )
        if doc is None:
            return None

        character = from_bson(Character, doc)
        character.guild_id = guild.id
        if isinstance(character.tags, list):
            character.tags = [str(tag) for tag in character.tags]
        else:
            character.tags = []
        if not isinstance(character.owner_id, UserID):
            try:
                character.owner_id = UserID.parse(str(character.owner_id))
            except Exception:
                pass
        if not character.status:
            character.status = CharacterRole.ACTIVE
        return character

    async def owned_character_docs(
        self, guild: discord.Guild, member: discord.Member
    ) -> List[dict]:
        await self.ensure_guild_cache(guild)
        guild_entry = self._guild_entry(guild.id)
        db = guild_entry["db"]
        owner_id = str(UserID.from_body(str(member.id)))
        cursor = db["characters"].find(
            {
                "guild_id": guild.id,
                "owner_id.value": owner_id,
            },
            {
                "_id": 0,
                "character_id": 1,
                "name": 1,
                "ddb_link": 1,
                "status": 1,
                "announcement_channel_id": 1,
                "announcement_message_id": 1,
            },
        )
        return list(cursor)

    async def next_character_id(self, guild: discord.Guild) -> CharacterID:
        await self.ensure_guild_cache(guild)
        guild_entry = self._guild_entry(guild.id)
        db = guild_entry["db"]
        coll = db["characters"]
        while True:
            candidate = CharacterID.generate()
            exists = coll.count_documents(
                {"guild_id": guild.id, "character_id": str(candidate)}, limit=1
            )
            if not exists:
                return candidate

    def persist_character(self, guild_id: int, character: Character) -> None:
        character.guild_id = guild_id
        if self._flush_via_adapter:
            upsert_character_sync(self._db_client, guild_id, character)
            return

        guild_entry = self._guild_entry(guild_id)
        db = guild_entry["db"]
        doc = to_bson(character)
        doc["guild_id"] = guild_id
        doc["character_id"] = str(character.character_id)
        db["characters"].update_one(
            {"guild_id": guild_id, "character_id": str(character.character_id)},
            {"$set": doc},
            upsert=True,
        )


__all__ = ["CharacterService"]
