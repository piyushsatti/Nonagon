from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.bot.database import db_client

_COLLECTION_NAME = "guild_settings"
_DOCUMENT_ID = "config"


def _collection(guild_id: int):
	return db_client.get_database(str(guild_id))[_COLLECTION_NAME]


def fetch_settings(guild_id: int) -> Optional[Dict[str, Any]]:
	"""Return the stored guild settings for the guild, if any."""
	doc = _collection(guild_id).find_one({"_id": _DOCUMENT_ID})
	if not doc:
		return None
	doc.pop("_id", None)
	return doc


def save_settings(guild_id: int, data: Dict[str, Any]) -> None:
	"""Persist the guild settings document."""
	payload = dict(data)
	payload["_id"] = _DOCUMENT_ID
	payload["updated_at"] = datetime.now(timezone.utc)
	_collection(guild_id).replace_one({"_id": _DOCUMENT_ID}, payload, upsert=True)


def delete_settings(guild_id: int) -> bool:
	"""Delete the guild settings document. Returns True if one existed."""
	result = _collection(guild_id).delete_one({"_id": _DOCUMENT_ID})
	return result.deleted_count == 1
