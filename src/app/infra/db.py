# app/infra/db.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Type, TypeVar
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.server_api import ServerApi

from app.domain.models.EntityIDModel import EntityID
from app.infra.settings import (
    DB_NAME,
    MONGO_APPNAME,
    MONGO_OP_TIMEOUT_MS,
    MONGO_SERVER_SELECTION_TIMEOUT_MS,
    MONGODB_TLS_ALLOW_INVALID_CERTS,
    MONGODB_TLS_CA_FILE,
    MONGODB_URI,
)

MongoDocument = dict[str, Any]

_client: Optional[AsyncIOMotorClient[Any]] = None
T = TypeVar("T", bound=EntityID)
_log = logging.getLogger(__name__)

_CA_CANDIDATES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/cert.pem",
    "/etc/pki/tls/certs/ca-bundle.crt",
)


def _resolve_ca_bundle() -> str | None:
    """Return a CA bundle path if one can be found on disk."""

    if MONGODB_TLS_CA_FILE:
        candidate = Path(MONGODB_TLS_CA_FILE)
        if candidate.is_file():
            return str(candidate)
        _log.warning(
            "Configured MONGODB_TLS_CA_FILE does not exist",
            extra={"path": str(candidate)},
        )

    for path in _CA_CANDIDATES:
        candidate = Path(path)
        if candidate.is_file():
            return str(candidate)
    return None


def _is_tls_connection(uri: str) -> bool:
    parsed = urlparse(uri)
    host = parsed.hostname or ""
    return uri.startswith("mongodb+srv://") or host.endswith("mongodb.net")


def get_client() -> AsyncIOMotorClient[Any]:
    """Return a cached AsyncIOMotorClient (lazy init)."""
    global _client
    if _client is None:
        client_kwargs: dict[str, Any] = {
            "appname": MONGO_APPNAME,
            "serverSelectionTimeoutMS": MONGO_SERVER_SELECTION_TIMEOUT_MS,
            "socketTimeoutMS": MONGO_OP_TIMEOUT_MS,
            "connectTimeoutMS": MONGO_OP_TIMEOUT_MS,
            "uuidRepresentation": "standard",
        }

        if _is_tls_connection(MONGODB_URI):
            client_kwargs["tls"] = True
            client_kwargs["tlsAllowInvalidCertificates"] = (
                MONGODB_TLS_ALLOW_INVALID_CERTS
            )
            ca_bundle = _resolve_ca_bundle()
            if ca_bundle:
                client_kwargs["tlsCAFile"] = ca_bundle
            else:
                _log.warning(
                    "TLS enabled but no CA bundle discovered; relying on defaults"
                )
            client_kwargs["server_api"] = ServerApi("1")

        _client = AsyncIOMotorClient(MONGODB_URI, **client_kwargs)
    return _client


def get_db() -> AsyncIOMotorDatabase[MongoDocument]:
    return get_client()[DB_NAME]


async def ping() -> bool:
    try:
        # admin DB per official examples
        await get_client().admin.command("ping")
        return True
    except Exception as e:
        _log.error("Mongo ping failed", exc_info=e)
        return False


async def next_id(id_cls: Type[T]) -> T:
    """
    Generate the next sequential ID for a given EntityID subclass.
    Stores counters in a 'counters' collection keyed by prefix.
    """
    db = get_db()
    doc = await db["counters"].find_one_and_update(
        {"_id": id_cls.prefix},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return id_cls(number=int(doc["seq"]))


async def close_client() -> None:
    """Close the cached client (useful for app shutdown / tests)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
