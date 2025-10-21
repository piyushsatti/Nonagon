import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.routers.demo import router as demo_router
from app.api.routers.quests import router as quests_router
from app.api.routers.users import router as users_router

log_dir = Path("/app/logs")
try:
    log_dir.mkdir(parents=True, exist_ok=True)
except Exception as exc:  # pragma: no cover - defensive logging
    logging.warning("Unable to create log directory %s: %s", log_dir, exc)
else:
    log_path = log_dir / "api.log"
    file_handler = logging.FileHandler(log_path, mode="w")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root_logger = logging.getLogger()
    if not any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == str(log_path)
        for handler in root_logger.handlers
    ):
        root_logger.addHandler(file_handler)

app = FastAPI(title="Nonagon API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(users_router)
app.include_router(quests_router)
app.include_router(demo_router, prefix="/v1")
app.include_router(demo_router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app", host="localhost", port=8000, reload=True, log_level="debug"
    )
