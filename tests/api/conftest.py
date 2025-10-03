from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.api import deps
from app.api.main import app
from app.bot.services.user_provisioning import UserProvisioningService
from app.infra import db as db_module
from app.infra.ids.service import MongoIdService
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quests_repo import QuestsRepoMongo
from app.infra.mongo.summaries_repo import SummariesRepoMongo
from app.infra.mongo.users_repo import UsersRepoMongo

# Load test-specific environment configuration if available.
load_dotenv(".env.test")

TEST_MONGODB_URI = os.getenv(
    "TEST_MONGODB_URI",
    "mongodb://root:example@localhost:27017/?authSource=admin",
)
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "nonagon_test")
TEST_ADMIN_TOKEN = os.getenv("TEST_ADMIN_TOKEN", "test-admin-token")


@pytest_asyncio.fixture(scope="session")
async def mongo_client() -> AsyncIterator[AsyncIOMotorClient[Any]]:
    client: AsyncIOMotorClient[Any] = AsyncIOMotorClient(
        TEST_MONGODB_URI,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=5000,
        socketTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    await client.admin.command("ping")
    await client.drop_database(TEST_DB_NAME)
    try:
        yield client
    finally:
        await client.drop_database(TEST_DB_NAME)
        client.close()


@pytest_asyncio.fixture(scope="session")
async def mongo_db(
    mongo_client: AsyncIOMotorClient[Any],
) -> AsyncIterator[AsyncIOMotorDatabase[Any]]:
    database: AsyncIOMotorDatabase[Any] = mongo_client[TEST_DB_NAME]
    yield database


@pytest_asyncio.fixture(scope="session", autouse=True)
async def configure_app_dependencies(
    mongo_client: AsyncIOMotorClient[Any],
    mongo_db: AsyncIOMotorDatabase[Any],
) -> AsyncIterator[None]:
    # Point the global database helpers at the dedicated test database.
    db_module._client = mongo_client  # type: ignore[attr-defined]
    db_module.DB_NAME = TEST_DB_NAME

    # Rebuild FastAPI dependency singletons against the test database.
    deps.ADMIN_TOKEN = TEST_ADMIN_TOKEN
    deps.user_repo = UsersRepoMongo()
    deps.chars_repo = CharactersRepoMongo(mongo_db)
    deps.quests_repo = QuestsRepoMongo()
    deps.summaries_repo = SummariesRepoMongo()
    deps.id_service = MongoIdService(mongo_db)
    deps.user_provisioning_service = UserProvisioningService(
        users_repo=deps.user_repo,
        id_service=deps.id_service,
    )

    # Ensure Mongo indexes exist before the tests run.
    await deps.user_repo.ensure_indexes()
    await deps.chars_repo.ensure_indexes()
    await deps.id_service.ensure_indexes()

    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_database(
    mongo_db: AsyncIOMotorDatabase[Any],
) -> AsyncIterator[None]:
    collections = await mongo_db.list_collection_names()
    for name in collections:
        await mongo_db.drop_collection(name)
    yield
    collections = await mongo_db.list_collection_names()
    for name in collections:
        await mongo_db.drop_collection(name)


@pytest_asyncio.fixture()
async def api_client() -> AsyncIterator[Any]:
    from httpx import ASGITransport, AsyncClient  # type: ignore[import]

    transport: Any = ASGITransport(app=app)  # type: ignore[import]
    async with AsyncClient(transport=transport, base_url="http://test") as client:  # type: ignore[reportUnknownVariableType]
        yield client


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": TEST_ADMIN_TOKEN}
