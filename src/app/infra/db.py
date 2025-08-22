# src/app/infra/db.py
from __future__ import annotations
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.infra.settings import MONGODB_URI, DB_NAME

_client: Optional[AsyncIOMotorClient] = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        # single, shared async client
        _client = AsyncIOMotorClient(MONGODB_URI, appname="nonagon")
    return _client

def get_db() -> AsyncIOMotorDatabase:
    return get_client()[DB_NAME]
