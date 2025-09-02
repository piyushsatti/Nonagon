from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.infra.mongo.users_repo import UsersRepoMongo
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quests_repo import QuestsRepoMongo
from app.infra.mongo.summaries_repo import SummariesRepoMongo

from app.api.routers.users import router as users_router
from app.api.routers.characters import router as characters_router
from app.api.routers.quests import router as quests_router
from app.api.routers.summaries import router as summaries_router

@asynccontextmanager
async def lifespan(app: FastAPI):
  # --- startup: instantiate once, stash on app.state ---
  app.state.users_repo = UsersRepoMongo()
  app.state.chars_repo = CharactersRepoMongo()
  app.state.quests_repo = QuestsRepoMongo()
  app.state.summaries_repo = SummariesRepoMongo()
  
  try:
    yield
  
  finally:
    pass

app = FastAPI(title="Nonagon API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
  CORSMiddleware, 
  allow_origins=["*"], 
  allow_credentials=True,
  allow_methods=["*"], 
  allow_headers=["*"]
)

# Routers
app.include_router(users_router)
app.include_router(characters_router)
app.include_router(quests_router)
app.include_router(summaries_router)

@app.get("/healthz")
def healthz():
  return {"ok": True}


if __name__ == "__main__":
  import uvicorn
  uvicorn.run("app.api.main:app", host="localhost", port=3000, reload=True, log_level="info")