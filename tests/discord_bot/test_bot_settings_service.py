from __future__ import annotations

from typing import cast

import pytest

from app.bot.config import DiscordBotConfig
from app.bot.services.adventure_summary_ingestion import (
    AdventureSummaryIngestionService,
)
from app.bot.services.bot_settings import BotSettingsService
from app.bot.services.quest_ingestion import QuestIngestionService
from app.bot.settings import GuildBotSettings
from app.infra.mongo.bot_settings_repo import BotSettingsRepository


class InMemoryBotSettingsRepo:
    def __init__(self) -> None:
        self.store: dict[int, GuildBotSettings] = {}

    async def get(self, guild_id: int) -> GuildBotSettings | None:
        return self.store.get(guild_id)

    async def upsert(self, settings: GuildBotSettings) -> GuildBotSettings:
        self.store[settings.guild_id] = settings
        return settings


class StubQuestService:
    def __init__(self) -> None:
        self.last: dict[str, int | None] | None = None

    def update_configuration(
        self,
        *,
        quest_channel_id: int | None = None,
        referee_role_id: int | None = None,
    ) -> None:
        self.last = {
            "quest_channel_id": quest_channel_id,
            "referee_role_id": referee_role_id,
        }


class StubSummaryService:
    def __init__(self) -> None:
        self.last: dict[str, int | None] | None = None

    def update_configuration(
        self,
        *,
        summary_channel_id: int | None = None,
        referee_role_id: int | None = None,
    ) -> None:
        self.last = {
            "summary_channel_id": summary_channel_id,
            "referee_role_id": referee_role_id,
        }


@pytest.mark.asyncio
async def test_ensure_settings_creates_defaults_and_applies_to_services() -> None:
    config = DiscordBotConfig(
        token="dummy",
        quest_channel_id=111,
        summary_channel_id=222,
        player_role_id=333,
        referee_role_id=444,
    )
    repo = InMemoryBotSettingsRepo()
    quest_service = StubQuestService()
    summary_service = StubSummaryService()
    service = BotSettingsService(
        repo=cast(BotSettingsRepository, repo),
        config=config,
        quest_service=cast(QuestIngestionService, quest_service),
        summary_service=cast(AdventureSummaryIngestionService, summary_service),
    )

    settings = await service.ensure_settings(guild_id=999)

    assert settings.guild_id == 999
    assert settings.quest_channel_id == 111
    assert settings.summary_channel_id == 222
    assert repo.store[999] == settings
    assert config.guild_id == 999
    assert quest_service.last == {
        "quest_channel_id": 111,
        "referee_role_id": 444,
    }
    assert summary_service.last == {
        "summary_channel_id": 222,
        "referee_role_id": 444,
    }


@pytest.mark.asyncio
async def test_update_channels_overrides_existing_settings() -> None:
    config = DiscordBotConfig(token="dummy")
    repo = InMemoryBotSettingsRepo()
    repo.store[123] = GuildBotSettings(
        guild_id=123,
        quest_channel_id=10,
        summary_channel_id=20,
        player_role_id=30,
        referee_role_id=40,
    )
    quest_service = StubQuestService()
    summary_service = StubSummaryService()
    service = BotSettingsService(
        repo=cast(BotSettingsRepository, repo),
        config=config,
        quest_service=cast(QuestIngestionService, quest_service),
        summary_service=cast(AdventureSummaryIngestionService, summary_service),
    )

    updated = await service.update_channels(123, quest_channel_id=55)

    assert updated.quest_channel_id == 55
    assert repo.store[123].quest_channel_id == 55
    assert quest_service.last == {
        "quest_channel_id": 55,
        "referee_role_id": 40,
    }
    assert summary_service.last == {
        "summary_channel_id": 20,
        "referee_role_id": 40,
    }


@pytest.mark.asyncio
async def test_update_roles_overrides_existing_settings() -> None:
    config = DiscordBotConfig(token="dummy")
    repo = InMemoryBotSettingsRepo()
    repo.store[456] = GuildBotSettings(
        guild_id=456,
        quest_channel_id=11,
        summary_channel_id=22,
        player_role_id=33,
        referee_role_id=44,
    )
    quest_service = StubQuestService()
    summary_service = StubSummaryService()
    service = BotSettingsService(
        repo=cast(BotSettingsRepository, repo),
        config=config,
        quest_service=cast(QuestIngestionService, quest_service),
        summary_service=cast(AdventureSummaryIngestionService, summary_service),
    )

    updated = await service.update_roles(456, player_role_id=99)

    assert updated.player_role_id == 99
    assert repo.store[456].player_role_id == 99
    assert config.player_role_id == 99
    assert quest_service.last == {
        "quest_channel_id": 11,
        "referee_role_id": 44,
    }
    assert summary_service.last == {
        "summary_channel_id": 22,
        "referee_role_id": 44,
    }
