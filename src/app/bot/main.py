from __future__ import annotations

import asyncio
import logging

from app.bot.client import build_bot
from app.bot.config import load_config
from app.bot.services.adventure_summary_ingestion import (
    AdventureSummaryIngestionService,
)
from app.bot.services.bot_settings import BotSettingsService
from app.bot.services.character_creation import CharacterCreationService
from app.bot.services.quest_ingestion import QuestIngestionService
from app.bot.services.role_management import RoleManagementService
from app.bot.services.user_provisioning import UserProvisioningService
from app.infra.db import close_client, get_db
from app.infra.ids.service import MongoIdService
from app.infra.mongo.bot_settings_repo import BotSettingsRepository
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quest_records_repo import QuestRecordsRepository
from app.infra.mongo.summary_records_repo import SummaryRecordsRepository
from app.infra.mongo.users_repo import UsersRepoMongo


async def bootstrap() -> None:
    # Load configuration
    config = load_config()
    db = get_db()

    # Load infrastructure, ensuring indexes are created
    id_service = MongoIdService(db)
    await id_service.ensure_indexes()

    users_repo = UsersRepoMongo()
    await users_repo.ensure_indexes()

    characters_repo = CharactersRepoMongo(db)
    await characters_repo.ensure_indexes()

    bot_settings_repo = BotSettingsRepository(db)
    await bot_settings_repo.ensure_indexes()

    quest_repo = QuestRecordsRepository(db)
    await quest_repo.ensure_indexes()

    summary_repo = SummaryRecordsRepository(db)
    await summary_repo.ensure_indexes()

    # Load services
    quest_service = QuestIngestionService(
        repo=quest_repo,
        id_service=id_service,
        quest_channel_id=config.quest_channel_id,
        referee_role_id=config.referee_role_id,
    )

    summary_service = AdventureSummaryIngestionService(
        repo=summary_repo,
        id_service=id_service,
        summary_channel_id=config.summary_channel_id,
        referee_role_id=config.referee_role_id,
    )

    bot_settings_service = BotSettingsService(
        repo=bot_settings_repo,
        config=config,
        quest_service=quest_service,
        summary_service=summary_service,
    )

    user_service = UserProvisioningService(
        users_repo=users_repo,
        id_service=id_service,
    )

    role_service = RoleManagementService(
        users_repo=users_repo,
        user_provisioning=user_service,
    )

    character_service = CharacterCreationService(
        characters_repo=characters_repo,
        users_repo=users_repo,
        user_provisioning=user_service,
    )

    # Build and run bot
    bot = build_bot(
        config,
        quest_service=quest_service,
        summary_service=summary_service,
        user_service=user_service,
        role_service=role_service,
        character_service=character_service,
        settings_service=bot_settings_service,
    )
    try:
        await bot.start(config.token)
    finally:
        await close_client()


def configure_logging() -> None:
    """Set up root logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    """Entrypoint for running the Discord bot."""
    configure_logging()
    asyncio.run(bootstrap())


if __name__ == "__main__":
    """
    Entrypoint for running the Discord bot.

    Prerequisites:
    - A valid configuration file at the expected path.
    - Access to a MongoDB instance as specified in the configuration.
    - Necessary Discord bot token and permissions.
    """
    main()
