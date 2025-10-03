from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GuildBotSettings:
    guild_id: int
    quest_channel_id: int | None = None
    summary_channel_id: int | None = None
    player_role_id: int | None = None
    referee_role_id: int | None = None
    log_channel_id: int | None = None
