from __future__ import annotations

import logging
from typing import Sequence

import discord
from discord.ext import commands

from .cogs.adventure_summary_ingestion import AdventureSummaryIngestionCog
from .cogs.bot_setup import BotSetupCog
from .cogs.character_commands import CharacterCommandsCog
from .cogs.general import GeneralCog
from .cogs.quest_ingestion import QuestIngestionCog
from .cogs.role_management import RoleManagementCog
from .cogs.user_provisioning import UserProvisioningCog
from .config import DiscordBotConfig, build_default_intents
from .services.adventure_summary_ingestion import AdventureSummaryIngestionService
from .services.bot_settings import BotSettingsService
from .services.character_creation import CharacterCreationService
from .services.quest_ingestion import QuestIngestionService
from .services.role_management import RoleManagementService
from .services.user_provisioning import UserProvisioningService


class IngestionBot(commands.Bot):
    def __init__(
        self,
        config: DiscordBotConfig,
        quest_service: QuestIngestionService,
        summary_service: AdventureSummaryIngestionService,
        user_service: UserProvisioningService,
        role_service: RoleManagementService,
        character_service: CharacterCreationService,
        settings_service: BotSettingsService,
    ) -> None:
        intents = build_default_intents()
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
        )
        self._config = config
        self._quest_service = quest_service
        self._summary_service = summary_service
        self._user_service = user_service
        self._role_service = role_service
        self._character_service = character_service
        self._settings_service = settings_service
        self._log = logging.getLogger(__name__)

    async def setup_hook(self) -> None:
        """Register cogs and sync application commands."""
        await self.add_cog(GeneralCog(self))
        await self.add_cog(
            BotSetupCog(
                self,
                config=self._config,
                settings_service=self._settings_service,
            )
        )
        await self.add_cog(UserProvisioningCog(service=self._user_service))
        await self.add_cog(
            CharacterCommandsCog(service=self._character_service, config=self._config)
        )
        await self.add_cog(QuestIngestionCog(service=self._quest_service))
        await self.add_cog(AdventureSummaryIngestionCog(service=self._summary_service))
        await self.add_cog(
            RoleManagementCog(service=self._role_service, config=self._config)
        )

        if self._config.guild_id is not None:
            await self._settings_service.ensure_settings(self._config.guild_id)
        await self._sync_app_commands()

    async def on_ready(self) -> None:  # pragma: no cover - simple log
        assert self.user is not None
        self._log.info(
            "Quest ingestion bot ready",
            extra={"bot_id": self.user.id},
        )

    async def _sync_app_commands(self) -> None:
        try:
            if self._config.guild_id is not None:
                guild_object = discord.Object(id=self._config.guild_id)
                guild_commands = await self.tree.sync(guild=guild_object)
                self._log.info(
                    "Synced guild application commands",
                    extra={
                        "scope": "guild",
                        "guild_id": self._config.guild_id,
                        "commands": self._command_names(guild_commands),
                    },
                )
            global_commands = await self.tree.sync()
            self._log.info(
                "Synced global application commands",
                extra={
                    "scope": "global",
                    "commands": self._command_names(global_commands),
                },
            )
        except Exception as exc:  # pragma: no cover - defensive log
            self._log.warning("Failed to sync application commands", exc_info=exc)

    def _command_names(self, commands: Sequence[object]) -> list[str]:
        names: list[str] = []
        for command in commands:
            qualified = getattr(command, "qualified_name", None)
            if isinstance(qualified, str):
                names.append(qualified)
                continue
            name = getattr(command, "name", None)
            if isinstance(name, str):
                names.append(name)
            else:  # pragma: no cover - defensive
                names.append("<unknown>")
        return sorted(names)


def build_bot(
    config: DiscordBotConfig,
    quest_service: QuestIngestionService,
    summary_service: AdventureSummaryIngestionService,
    user_service: UserProvisioningService,
    role_service: RoleManagementService,
    character_service: CharacterCreationService,
    settings_service: BotSettingsService,
) -> IngestionBot:
    return IngestionBot(
        config,
        quest_service,
        summary_service,
        user_service,
        role_service,
        character_service,
        settings_service,
    )
