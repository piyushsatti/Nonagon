# src/app/api/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import quests

app = FastAPI(title="Nonagon API", version="0.1.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)

# Register routers
app.include_router(quests.router)

@app.get("/health")
async def health():
  return {"ok": True}