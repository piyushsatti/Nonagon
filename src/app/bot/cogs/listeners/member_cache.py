from __future__ import annotations

from typing import Optional

from discord import Guild, Member
from discord.ext import commands

from app.bot.database import db_client
from app.bot.services.user_registry import UserRegistry
from app.domain.models.UserModel import User
from app.bot.utils.logging import get_logger


logger = get_logger(__name__)


class MemberCache:
    """Helper for keeping guild member data in sync with Mongo-backed cache."""

    def __init__(self, bot: commands.Bot, registry: Optional[UserRegistry] = None):
        self._bot = bot
        self._registry = registry or UserRegistry()

    async def ensure_cached_user(self, member: Member) -> User:
        guild_id = member.guild.id
        guild_entry = self._bot.guild_data.get(guild_id)

        if guild_entry is None:
            await self._bot.load_or_create_guild_cache(member.guild)
            guild_entry = self._bot.guild_data[guild_id]

        users = guild_entry.setdefault("users", {})
        user = users.get(member.id)

        if user is None:
            user = await self._registry.ensure_member(member, guild_id)
            user.guild_id = guild_id
            users[member.id] = user

        return user

    async def resolve_cached_user(
        self, guild: Guild, user_id: int
    ) -> Optional[User]:
        guild_entry = self._bot.guild_data.get(guild.id)

        if guild_entry is None:
            await self._bot.load_or_create_guild_cache(guild)
            guild_entry = self._bot.guild_data[guild.id]

        users = guild_entry.setdefault("users", {})
        user = users.get(user_id)

        if user is not None:
            return user

        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except Exception as exc:  # pragma: no cover - network edge
                logger.warning(
                    "Unable to resolve guild member %s in %s: %s",
                    user_id,
                    guild.id,
                    exc,
                )
                return None

        user = await self._registry.ensure_member(member, guild.id)
        user.guild_id = guild.id
        users[user_id] = user
        return user

    async def ensure_guild_entry(self, guild: Guild) -> dict:
        ensure_entry = getattr(self._bot, "_ensure_guild_entry", None)
        if callable(ensure_entry):
            guild_entry = ensure_entry(guild.id)
        else:
            guild_entry = self._bot.guild_data.setdefault(
                guild.id,
                {"db": db_client.get_database(str(guild.id)), "users": {}},
            )
        return guild_entry
