# tests/infra/conftest.py
import os, asyncio
import pytest
import pytest_asyncio
from testcontainers.mongodb import MongoDbContainer

import app.infra.settings as settings
import app.infra.db as db_module  # <- do NOT reassign this name


# One loop for the whole session (prevents cross-loop Motor issues)
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def mongo_patch_db():
    """
    Start MongoDB in a container, point app.infra.db at it, and warm up the client.
    """
    with MongoDbContainer("mongo:7.0") as mongo:
        uri = mongo.get_connection_url()              # e.g. mongodb://localhost:5xxxx/test
        dbname = "nonagon_test"

        # Optional: keep settings in sync for any code that reads settings directly
        os.environ["MONGODB_URI"] = uri
        os.environ["DB_NAME"] = dbname

        # Critical: patch the *db module's* constants so get_client() uses the container
        db_module.MONGODB_URI = uri
        db_module.DB_NAME = dbname

        # Kill any cached client made with old settings
        await db_module.close_client()

        # Sanity-check: this creates a fresh client bound to THIS session loop
        ok = await db_module.ping()
        assert ok, f"Mongo ping failed; MONGODB_URI in use: {db_module.MONGODB_URI}"

        yield

        await db_module.close_client()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db():
    """
    Clear collections before each test to keep isolation.
    """
    d = db_module.get_db()
    for name in ("users", "characters", "quests", "summaries", "counters"):
        await d[name].delete_many({})
