from __future__ import annotations

from app.bot.config import DiscordBotConfig
from app.bot.services.adventure_summary_ingestion import (
    AdventureSummaryIngestionService,
)
from app.bot.services.quest_ingestion import QuestIngestionService
from app.bot.settings import GuildBotSettings
from app.infra.mongo.bot_settings_repo import BotSettingsRepository


class BotSettingsService:
    """Coordinates persisted guild configuration with runtime services."""

    def __init__(
        self,
        *,
        repo: BotSettingsRepository,
        config: DiscordBotConfig,
        quest_service: QuestIngestionService,
        summary_service: AdventureSummaryIngestionService,
    ) -> None:
        self._repo = repo
        self._config = config
        self._quest_service = quest_service
        self._summary_service = summary_service

    async def ensure_settings(self, guild_id: int) -> GuildBotSettings:
        """
        Ensure settings exist for the given guild, creating defaults if needed.

        Setting:
        - guild_id: ID of the Discord guild (server).
        - quest_channel_id: ID of the channel for quest submissions.
        - summary_channel_id: ID of the channel for adventure summaries.
        - player_role_id: ID of the role assigned to players.
        - referee_role_id: ID of the role assigned to referees.

        Returns the ensured settings.
        """
        settings = await self._repo.get(guild_id)
        if settings is None:
            settings = GuildBotSettings(
                guild_id=guild_id,
                quest_channel_id=self._config.quest_channel_id,
                summary_channel_id=self._config.summary_channel_id,
                player_role_id=self._config.player_role_id,
                referee_role_id=self._config.referee_role_id,
            )
            await self._repo.upsert(settings)
        self._apply(settings)
        return settings

    async def update_all(
        self,
        guild_id: int,
        *,
        quest_channel_id: int,
        summary_channel_id: int,
        player_role_id: int,
        referee_role_id: int,
    ) -> GuildBotSettings:
        settings = await self.ensure_settings(guild_id)
        settings.quest_channel_id = quest_channel_id
        settings.summary_channel_id = summary_channel_id
        settings.player_role_id = player_role_id
        settings.referee_role_id = referee_role_id
        await self._repo.upsert(settings)
        self._apply(settings)
        return settings

    async def update_channels(
        self,
        guild_id: int,
        *,
        quest_channel_id: int | None = None,
        summary_channel_id: int | None = None,
    ) -> GuildBotSettings:
        settings = await self.ensure_settings(guild_id)
        if quest_channel_id is not None:
            settings.quest_channel_id = quest_channel_id
        if summary_channel_id is not None:
            settings.summary_channel_id = summary_channel_id
        await self._repo.upsert(settings)
        self._apply(settings)
        return settings

    async def update_roles(
        self,
        guild_id: int,
        *,
        player_role_id: int | None = None,
        referee_role_id: int | None = None,
    ) -> GuildBotSettings:
        settings = await self.ensure_settings(guild_id)
        if player_role_id is not None:
            settings.player_role_id = player_role_id
        if referee_role_id is not None:
            settings.referee_role_id = referee_role_id
        await self._repo.upsert(settings)
        self._apply(settings)
        return settings

    async def get_settings(self, guild_id: int) -> GuildBotSettings:
        return await self.ensure_settings(guild_id)

    def _apply(self, settings: GuildBotSettings) -> None:
        self._config.guild_id = settings.guild_id
        self._config.apply_channels(
            quest_channel_id=settings.quest_channel_id,
            summary_channel_id=settings.summary_channel_id,
        )
        self._config.apply_roles(
            player_role_id=settings.player_role_id,
            referee_role_id=settings.referee_role_id,
        )
        self._quest_service.update_configuration(
            quest_channel_id=settings.quest_channel_id,
            referee_role_id=settings.referee_role_id,
        )
        self._summary_service.update_configuration(
            summary_channel_id=settings.summary_channel_id,
            referee_role_id=settings.referee_role_id,
        )
