# src/app/api/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, quests

app = FastAPI(title="Nonagon API", version="0.1.0")

# CORS (allow localhost by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quests.router)

@app.get("/healthz")
async def healthz():
    return {"ok": True}