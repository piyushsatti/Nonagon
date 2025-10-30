from __future__ import annotations

import asyncio
from typing import Any, Optional

import discord
from discord.ext import commands

from app.bot.cogs.manifest import DEFAULT_EXTENSIONS
from app.bot.core.cache import (
    ensure_guild_entry,
    load_all_guild_caches,
    load_or_create_guild_cache as cache_load_or_create_guild_cache,
    start_auto_flush,
)
from app.bot.core.settings import Settings
from app.bot.utils.logging import get_logger


logger = get_logger(__name__)


class Nonagon(commands.Bot):
    """Discord bot runtime with extension bootstrap helpers."""

    def __init__(self, intents: discord.Intents, settings: Settings):
        super().__init__(
            command_prefix=commands.when_mentioned_or("n.", "n!"), intents=intents
        )
        self.settings = settings
        self.guild_data: dict[int, dict[str, Any]] = {}
        self.dirty_data: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
        self.flush_stats: dict[str, Any] = {}

    async def setup_hook(self) -> None:
        loaded: list[str] = []
        failed: dict[str, str] = {}

        async def safe_load(ext: str) -> None:
            if ext in self.extensions:
                return
            try:
                await self.load_extension(ext)
                loaded.append(ext)
                logger.info("Loaded extension %s", ext)
            except Exception:
                import traceback as _tb

                failed[ext] = _tb.format_exc()
                logger.error("Error loading extension %s:\n%s", ext, failed[ext])

        extensions = self.settings.extensions_override or DEFAULT_EXTENSIONS
        core_extensions = (
            "app.bot.cogs.admin.extension_manager",
            "app.bot.cogs.admin.diagnostics",
        )
        logger.info(
            "Extension bootstrap resolved=%s (auto_load=%s)",
            ", ".join(extensions),
            self.settings.auto_load_cogs,
        )

        if self.settings.auto_load_cogs:
            ordered = dict.fromkeys((*extensions, *core_extensions))
            for ext in ordered:
                await safe_load(ext)
        else:
            for ext in core_extensions:
                await safe_load(ext)

        logger.info("Cog loader audit: %d loaded, %d failed", len(loaded), len(failed))
        if loaded:
            logger.info("Loaded cogs: %s", ", ".join(sorted(loaded)))
        if failed:
            for ext, tb in failed.items():
                logger.debug("Failed cog %s trace:\n%s", ext, tb)

        try:
            start_auto_flush(self)
        except Exception as exc:
            logger.error("Auto persist loop encountered an error: %s", exc)

        await super().setup_hook()

    async def start(self, token: Optional[str] = None, *, reconnect: bool = False):
        async def _idle_forever(reason: str) -> None:
            logger.error(
                "%s. Bot will remain idle until restarted with valid credentials.",
                reason,
            )
            while True:
                await asyncio.sleep(30)

        normalized = (token or self.settings.bot_token or "").strip()
        placeholders = {"", "replace_me"}

        if normalized.lower() in placeholders:
            await _idle_forever(
                "BOT_TOKEN is missing or still set to the placeholder value"
            )
            return

        try:
            await super().start(normalized, reconnect=reconnect)
        except discord.LoginFailure as exc:
            await _idle_forever(f"Discord login failed: {exc}")
        except discord.HTTPException as exc:
            await _idle_forever(f"Discord HTTP error during startup: {exc}")
        except Exception as exc:  # pragma: no cover - defensive fallback
            await _idle_forever(f"Unexpected error during startup: {exc}")

    async def on_ready(self) -> None:
        await self._load_cache()
        tree_commands = [cmd.qualified_name for cmd in self.tree.get_commands()]
        user_repr = str(self.user) if self.user is not None else "<no-user>"
        user_id = getattr(self.user, "id", "<no-id>")
        logger.info("Logged in as %s (ID: %s)", user_repr, user_id)
        logger.info("Loaded cogs: %s", ", ".join(sorted(self.cogs.keys())))
        logger.info("Slash commands: %s", ", ".join(sorted(tree_commands)))

    async def on_error(self, event_method, /, *args, **kwargs) -> None:
        await super().on_error(event_method, *args, **kwargs)

    def _ensure_guild_entry(self, guild_id: int) -> dict[str, Any]:
        return ensure_guild_entry(self, guild_id)

    async def _load_cache(self) -> None:
        await load_all_guild_caches(self)

    async def _sync_application_commands(self) -> None:
        await self.wait_until_ready()

        try:
            target_guild_ids = {guild.id for guild in self.guilds}
            for guild_id in target_guild_ids:
                try:
                    guild_obj = discord.Object(id=guild_id)
                    self.tree.copy_global_to(guild=guild_obj)
                    scoped_commands = await self.tree.sync(guild=guild_obj)
                    logger.info(
                        "Synced %d slash commands to guild %s",
                        len(scoped_commands),
                        guild_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to sync application commands for guild %s", guild_id
                    )
        except Exception:
            logger.exception("Failed to sync application commands")

    async def load_or_create_guild_cache(self, guild: discord.Guild) -> None:
        await cache_load_or_create_guild_cache(self, guild)


def _default_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    intents.members = True
    intents.voice_states = True
    return intents


def build_bot(settings: Settings, *, intents: Optional[discord.Intents] = None) -> Nonagon:
    intents = intents or _default_intents()
    return Nonagon(intents=intents, settings=settings)


async def start_bot(settings: Settings) -> None:
    bot = build_bot(settings)
    await bot.start(settings.bot_token)


__all__ = ["Nonagon", "build_bot", "start_bot"]
