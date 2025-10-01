from __future__ import annotations

import logging

from discord.ext import commands

from .cogs.adventure_summary_ingestion import AdventureSummaryIngestionCog
from .cogs.character_commands import CharacterCommandsCog
from .cogs.quest_ingestion import QuestIngestionCog
from .cogs.role_management import RoleManagementCog
from .cogs.user_provisioning import UserProvisioningCog
from .config import DiscordBotConfig, build_default_intents
from .services.adventure_summary_ingestion import AdventureSummaryIngestionService
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
        self._log = logging.getLogger(__name__)

    async def setup_hook(self) -> None:
        await self.add_cog(QuestIngestionCog(service=self._quest_service))
        await self.add_cog(AdventureSummaryIngestionCog(service=self._summary_service))
        await self.add_cog(UserProvisioningCog(service=self._user_service))
        await self.add_cog(
            RoleManagementCog(service=self._role_service, config=self._config)
        )
        await self.add_cog(
            CharacterCommandsCog(service=self._character_service, config=self._config)
        )

    async def on_ready(self) -> None:  # pragma: no cover - simple log
        assert self.user is not None
        self._log.info(
            "Quest ingestion bot ready",
            extra={"bot_id": self.user.id},
        )


def build_bot(
    config: DiscordBotConfig,
    quest_service: QuestIngestionService,
    summary_service: AdventureSummaryIngestionService,
    user_service: UserProvisioningService,
    role_service: RoleManagementService,
    character_service: CharacterCreationService,
) -> IngestionBot:
    return IngestionBot(
        config,
        quest_service,
        summary_service,
        user_service,
        role_service,
        character_service,
    )
