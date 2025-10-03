"""Shared dependency providers for FastAPI routers."""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from app.bot.services.user_provisioning import UserProvisioningService
from app.infra.db import get_db
from app.infra.ids.service import MongoIdService
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quests_repo import QuestsRepoMongo
from app.infra.mongo.summaries_repo import SummariesRepoMongo
from app.infra.mongo.users_repo import UsersRepoMongo

_db = get_db()

user_repo = UsersRepoMongo()
chars_repo = CharactersRepoMongo(_db)
quests_repo = QuestsRepoMongo()
summaries_repo = SummariesRepoMongo()
id_service = MongoIdService(_db)
user_provisioning_service = UserProvisioningService(
    users_repo=user_repo,
    id_service=id_service,
)

ADMIN_TOKEN: Optional[str] = os.getenv("API_ADMIN_TOKEN")


async def require_admin(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Enforce that an admin token header is present and matches the configured secret."""
    token = ADMIN_TOKEN
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin token is not configured",
        )
    if not x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin token",
        )
    if not secrets.compare_digest(x_admin_token, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token",
        )


async def get_user_provisioning_service() -> UserProvisioningService:
    """Expose the singleton user provisioning service for dependency injection."""
    return user_provisioning_service
