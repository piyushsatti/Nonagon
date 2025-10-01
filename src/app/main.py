from __future__ import annotations

import asyncio
import logging

from app.discord_bot.client import build_bot
from app.discord_bot.config import load_config
from app.discord_bot.services.adventure_summary_ingestion import (
    AdventureSummaryIngestionService,
)
from app.discord_bot.services.character_creation import CharacterCreationService
from app.discord_bot.services.quest_ingestion import QuestIngestionService
from app.discord_bot.services.role_management import RoleManagementService
from app.discord_bot.services.user_provisioning import UserProvisioningService
from app.infra.db import close_client, get_db
from app.infra.ids.service import MongoIdService
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quest_records_repo import QuestRecordsRepository
from app.infra.mongo.summary_records_repo import SummaryRecordsRepository
from app.infra.mongo.users_repo import UsersRepoMongo


async def bootstrap() -> None:
    config = load_config()

    db = get_db()
    quest_repo = QuestRecordsRepository(db)
    await quest_repo.ensure_indexes()

    summary_repo = SummaryRecordsRepository(db)
    await summary_repo.ensure_indexes()

    id_service = MongoIdService(db)
    await id_service.ensure_indexes()

    users_repo = UsersRepoMongo()
    await users_repo.ensure_indexes()

    characters_repo = CharactersRepoMongo()

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

    bot = build_bot(
        config,
        quest_service=quest_service,
        summary_service=summary_service,
        user_service=user_service,
        role_service=role_service,
        character_service=character_service,
    )
    try:
        await bot.start(config.token)
    finally:
        await close_client()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    configure_logging()
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
