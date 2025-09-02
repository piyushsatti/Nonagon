from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

from app.api.routers.users import router as users_router
from app.api.routers.characters import router as characters_router
from app.api.routers.quests import router as quests_router
from app.api.routers.summaries import router as summaries_router

app = FastAPI(title="Nonagon API", version="1.0.0")

app.add_middleware(
  CORSMiddleware, 
  allow_origins=["*"], 
  allow_credentials=True,
  allow_methods=["*"], 
  allow_headers=["*"]
)

# Routers
app.include_router(users_router)
# app.include_router(characters_router)
# app.include_router(quests_router)
# app.include_router(summaries_router)


@app.get("/healthz")
def healthz():
  return {"ok": True}

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(
    "app.api.main:app", 
    host="localhost", 
    port=8000, 
    reload=True, 
    log_level="trace"
  )