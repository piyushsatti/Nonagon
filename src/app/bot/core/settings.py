from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

from app.bot.config import (
    BOT_FLUSH_VIA_ADAPTER,
    BOT_TOKEN,
    QUEST_API_BASE_URL,
    QUEST_BOARD_CHANNEL_ID,
)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_extensions(raw: Optional[str]) -> Optional[Tuple[str, ...]]:
    if not raw:
        return None
    parts = [segment.strip() for segment in raw.split(",")]
    filtered = tuple(part for part in parts if part)
    return filtered or None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the Nonagon bot."""

    bot_token: str
    auto_load_cogs: bool
    flush_via_adapter: bool
    flush_interval_seconds: int
    quest_api_base_url: str
    quest_board_channel_id: Optional[int]
    extensions_override: Optional[Tuple[str, ...]] = None


def load_settings() -> Settings:
    """Construct Settings from environment variables."""
    auto_load = _env_flag("AUTO_LOAD_COGS", default=False)
    override = _parse_extensions(os.getenv("BOT_EXTENSIONS"))
    flush_interval = _env_int("BOT_FLUSH_INTERVAL_SECONDS", default=15)
    return Settings(
        bot_token=BOT_TOKEN.strip(),
        auto_load_cogs=auto_load,
        flush_via_adapter=BOT_FLUSH_VIA_ADAPTER,
        flush_interval_seconds=flush_interval,
        quest_api_base_url=QUEST_API_BASE_URL.strip(),
        quest_board_channel_id=QUEST_BOARD_CHANNEL_ID,
        extensions_override=override,
    )


__all__ = ["Settings", "load_settings"]
