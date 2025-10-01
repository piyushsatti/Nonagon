from __future__ import annotations

import os
from dataclasses import dataclass

import discord
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class DiscordBotConfig:
    """Runtime configuration for the Discord quest ingestion bot."""

    token: str
    quest_channel_id: int
    summary_channel_id: int
    player_role_id: int
    referee_role_id: int


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def load_config() -> DiscordBotConfig:
    """Load configuration from environment variables."""

    token = _require("DISCORD_TOKEN")
    quest_channel = int(_require("QUEST_CHANNEL_ID"))
    summary_channel = int(_require("SUMMARY_CHANNEL_ID"))
    player_role = int(_require("PLAYER_ROLE_ID"))
    referee_role = int(_require("REFEREE_ROLE_ID"))
    return DiscordBotConfig(
        token=token,
        quest_channel_id=quest_channel,
        summary_channel_id=summary_channel,
        player_role_id=player_role,
        referee_role_id=referee_role,
    )


def build_default_intents() -> discord.Intents:
    """Return the default intents required by the ingestion bot."""

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    return intents
