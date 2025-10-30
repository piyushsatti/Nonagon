from __future__ import annotations

import logging
from typing import Iterable, List

import discord

logger = logging.getLogger(__name__)


async def sync_guilds(bot: discord.Client, target_ids: Iterable[int]) -> List[str]:
    """Synchronize application commands for the given guild ids.

    Returns a list of human-readable result lines per guild.
    """
    results: List[str] = []
    for guild_id in set(int(g) for g in target_ids):
        guild_obj = discord.Object(id=guild_id)
        try:
            # copy globals to the guild and sync only that guild
            bot.tree.copy_global_to(guild=guild_obj)
            commands_synced = await bot.tree.sync(guild=guild_obj)
            results.append(f"{guild_id}: {len(commands_synced)} commands")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to sync commands for guild %s", guild_id)
            results.append(f"{guild_id}: failed ({exc})")
    return results
