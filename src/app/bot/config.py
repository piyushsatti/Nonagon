from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import discord
from dotenv import dotenv_values

TOKEN_KEYS = ("DISCORD_TOKEN", "BOT_TOKEN")
DEFAULT_TEST_GUILD_ID = 1372610481860120638


def _seed_token_from_env_file() -> None:
    if any(os.getenv(key) for key in TOKEN_KEYS):
        return

    env_path = Path(".env")
    if not env_path.exists():
        return

    values = dotenv_values(env_path)
    for key in TOKEN_KEYS:
        value = values.get(key)
        if value:
            os.environ.setdefault(key, value)
            break


@dataclass(slots=True)
class DiscordBotConfig:
    """Runtime configuration for the Discord quest ingestion bot."""

    token: str
    guild_id: int | None = None
    quest_channel_id: int | None = None
    summary_channel_id: int | None = None
    player_role_id: int | None = None
    referee_role_id: int | None = None
    log_channel_id: int | None = None

    def apply_channels(
        self,
        *,
        quest_channel_id: int | None = None,
        summary_channel_id: int | None = None,
    ) -> None:
        if quest_channel_id is not None:
            self.quest_channel_id = quest_channel_id
        if summary_channel_id is not None:
            self.summary_channel_id = summary_channel_id

    def apply_roles(
        self,
        *,
        player_role_id: int | None = None,
        referee_role_id: int | None = None,
    ) -> None:
        if player_role_id is not None:
            self.player_role_id = player_role_id
        if referee_role_id is not None:
            self.referee_role_id = referee_role_id

    def apply_logging(self, *, log_channel_id: int | None = None) -> None:
        if log_channel_id is not None:
            self.log_channel_id = log_channel_id


def _require_any(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    joined = ", ".join(keys)
    raise RuntimeError(f"Missing required environment variable. Tried: {joined}")


def _optional_int(key: str) -> Optional[int]:
    value = os.getenv(key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive logging
        raise RuntimeError(f"Invalid integer environment variable: {key}") from exc


def load_config() -> DiscordBotConfig:
    """Load configuration from environment variables."""

    _seed_token_from_env_file()
    token = _require_any("DISCORD_TOKEN", "BOT_TOKEN")
    config = DiscordBotConfig(
        token=token,
        guild_id=_optional_int("DISCORD_GUILD_ID") or _optional_int("GUILD_ID"),
        quest_channel_id=_optional_int("QUEST_CHANNEL_ID"),
        summary_channel_id=_optional_int("SUMMARY_CHANNEL_ID"),
        player_role_id=_optional_int("PLAYER_ROLE_ID"),
        referee_role_id=_optional_int("REFEREE_ROLE_ID"),
        log_channel_id=_optional_int("LOG_CHANNEL_ID"),
    )
    return config


def build_default_intents() -> discord.Intents:
    """Return the default intents required by the ingestion bot."""

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    return intents
