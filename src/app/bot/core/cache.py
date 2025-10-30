from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Iterable, Tuple

import discord
from discord.ext import commands

from app.bot.config import BOT_FLUSH_VIA_ADAPTER
from app.bot.database import db_client
from app.bot.utils.logging import get_logger
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_user_sync
from app.infra.serialization import to_bson


logger = get_logger(__name__)


def ensure_guild_entry(bot: commands.Bot, guild_id: int) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "guild_id": guild_id,
        "db": db_client.get_database(str(guild_id)),
        "users": {},
        "quests": {},
        "characters": {},
        "summaries": {},
    }
    entry = bot.guild_data.setdefault(guild_id, defaults)
    for key, value in defaults.items():
        entry.setdefault(key, value)
    entry["guild_id"] = guild_id
    return entry


async def load_all_guild_caches(bot: commands.Bot) -> None:
    logger.info("Loading guild caches…")
    tasks = [load_or_create_guild_cache(bot, guild) for guild in bot.guilds]
    await asyncio.gather(*tasks)
    logger.info("All guild caches ready.")


async def auto_persist_loop(bot: commands.Bot) -> None:
    """Periodically flush *all* in-memory user caches back to MongoDB."""
    settings = getattr(bot, "settings", None)
    interval = getattr(settings, "flush_interval_seconds", 15) or 15
    flush_via_adapter = _should_flush_via_adapter(bot)
    while not bot.is_closed():
        await asyncio.sleep(interval)
        queue_size = bot.dirty_data.qsize()
        to_flush: Dict[Tuple[int, int], User] = {}
        try:
            while True:
                gid, uid = bot.dirty_data.get_nowait()
                guild_entry = bot.guild_data.get(gid)
                if guild_entry is None:
                    logger.debug(
                        "Skipping flush for gid=%s uid=%s (no guild cache)", gid, uid
                    )
                    continue
                user = guild_entry.get("users", {}).get(uid)
                if user is None:
                    logger.debug(
                        "Skipping flush for gid=%s uid=%s (user missing in cache)",
                        gid,
                        uid,
                    )
                    continue
                to_flush[(gid, uid)] = user
        except asyncio.QueueEmpty:
            pass

        if not to_flush:
            continue

        start = time.perf_counter()
        error_counter = {"count": 0}

        async def flush_user(gid: int, uid: int, user: User) -> None:
            guild_entry = bot.guild_data.get(gid)
            if guild_entry is None:
                logger.debug(
                    "Skipping flush for gid=%s uid=%s (guild missing)", gid, uid
                )
                return
            try:
                user.guild_id = gid
                if flush_via_adapter:
                    await asyncio.to_thread(upsert_user_sync, db_client, gid, user)
                else:
                    db = guild_entry["db"]
                    payload = to_bson(user)
                    payload["guild_id"] = payload.get("guild_id") or gid
                    await asyncio.to_thread(
                        db.users.update_one,
                        {
                            "guild_id": payload["guild_id"],
                            "user_id.value": str(user.user_id),
                        },
                        {"$set": payload},
                        upsert=True,
                    )
                logger.debug(
                    "Persisted gid=%s uid=%s as user_id=%s", gid, uid, user.user_id
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception(
                    "Failed to persist gid=%s uid=%s user_id=%s: %s",
                    gid,
                    uid,
                    user.user_id,
                    exc,
                )
                error_counter["count"] += 1

        # Quietly completes; detailed logging is handled by exception paths above.
        await asyncio.gather(
            *(flush_user(gid, uid, user) for (gid, uid), user in to_flush.items())
        )

        duration_ms = (time.perf_counter() - start) * 1000
        batch_size = len(to_flush)
        metrics = {
            "dirty_qsize": queue_size,
            "batch": batch_size,
            "duration_ms": round(duration_ms, 2),
        }
        logger.info("flush_metrics %s", metrics)

        flush_stats = getattr(bot, "flush_stats", None)
        if not isinstance(flush_stats, dict):
            flush_stats = bot.flush_stats = {
                "total_batches": 0,
                "total_items": 0,
                "last_duration_ms": 0.0,
                "errors": 0,
            }

        flush_stats["total_batches"] += 1
        flush_stats["total_items"] += batch_size
        flush_stats["last_duration_ms"] = metrics["duration_ms"]
        flush_stats["errors"] += error_counter["count"]


async def load_or_create_guild_cache(bot: commands.Bot, guild: discord.Guild) -> None:
    db_name = f"{guild.id}"
    entry = ensure_guild_entry(bot, guild.id)
    g_db = entry["db"]

    if db_name in db_client.list_database_names():
        logger.info("Loading cached users for %s", guild.name)
        users: Dict[int, User] = {}
        found_with_guild = False
        primary_cursor = g_db.users.find({"guild_id": guild.id}, {"_id": 0})
        for doc in primary_cursor:
            found_with_guild = True
            user = User.from_dict(doc)
            user.guild_id = guild.id
            raw_key = doc.get("discord_id") or user.discord_id
            if raw_key is None:
                logger.debug(
                    "Skipping cached user with missing discord_id (guild=%s, user_id=%s)",
                    guild.id,
                    user.user_id,
                )
                continue
            try:
                key = int(raw_key)
            except (TypeError, ValueError):
                logger.debug(
                    "Skipping cached user with non-numeric discord_id=%s (guild=%s, user_id=%s)",
                    raw_key,
                    guild.id,
                    user.user_id,
                )
                continue
            users[key] = user

        if not found_with_guild:
            legacy_cursor = g_db.users.find({}, {"_id": 0})
            for doc in legacy_cursor:
                user = User.from_dict(doc)
                user.guild_id = guild.id
                raw_key = doc.get("discord_id") or user.discord_id
                if raw_key is None:
                    logger.debug(
                        "Skipping legacy user with missing discord_id (guild=%s, user_id=%s)",
                        guild.id,
                        user.user_id,
                    )
                    continue
                try:
                    key = int(raw_key)
                except (TypeError, ValueError):
                    logger.debug(
                        "Skipping legacy user with non-numeric discord_id=%s (guild=%s, user_id=%s)",
                        raw_key,
                        guild.id,
                        user.user_id,
                    )
                    continue
                users[key] = user

        if users:
            entry["users"] = users
            bot.guild_data[guild.id] = entry
            return
        logger.info(
            "No users found in DB for %s; scraping members as fallback", guild.name
        )

    logger.info("Scraping %s (%s members)...", guild.name, guild.member_count)
    snapshot: Iterable[discord.Member] = list(guild.members)
    users = {m.id: User.from_member(m) for m in snapshot if not m.bot}
    for user in users.values():
        user.guild_id = guild.id

    entry["users"] = users
    bot.guild_data[guild.id] = entry

    docs = []
    for user in users.values():
        payload = to_bson(user)
        payload["guild_id"] = payload.get("guild_id") or guild.id
        docs.append(payload)

    if docs:
        await asyncio.to_thread(entry["db"].users.insert_many, docs)

    logger.info(
        "Initial cache and DB created for %s - %d users", guild.name, len(users)
    )


def start_auto_flush(bot: commands.Bot) -> asyncio.Task[Any]:
    """Kick off the background auto-flush loop."""
    return bot.loop.create_task(auto_persist_loop(bot))


def _should_flush_via_adapter(bot: commands.Bot) -> bool:
    settings = getattr(bot, "settings", None)
    if settings is not None:
        return bool(getattr(settings, "flush_via_adapter", BOT_FLUSH_VIA_ADAPTER))
    return BOT_FLUSH_VIA_ADAPTER


__all__ = [
    "auto_persist_loop",
    "ensure_guild_entry",
    "load_all_guild_caches",
    "load_or_create_guild_cache",
    "start_auto_flush",
]
