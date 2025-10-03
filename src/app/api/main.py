"""FastAPI application entry point and router composition for the Nonagon API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.routers.admin import router as admin_router
from app.api.routers.characters import router as characters_router
from app.api.routers.quests import router as quests_router
from app.api.routers.summaries import router as summaries_router
from app.api.routers.users import router as users_router
from app.infra.lifecycle import on_shutdown as db_on_shutdown
from app.infra.lifecycle import on_startup as db_on_startup


@asynccontextmanager
async def lifespan(_: FastAPI):
    log = logging.getLogger(__name__)
    try:
        await db_on_startup()
    except Exception:  # pragma: no cover - defensive
        log.exception("Failed MongoDB startup health check")
        raise
    else:
        log.info("MongoDB startup health check succeeded")
    try:
        yield
    finally:
        await db_on_shutdown()


app = FastAPI(title="Nonagon API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(characters_router)
app.include_router(quests_router)
app.include_router(summaries_router)


@app.get("/healthz")
def healthz():
    """Lightweight health check used by deployment probes."""
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app", host="localhost", port=8000, reload=True, log_level="debug"
    )
