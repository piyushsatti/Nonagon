import logging
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from .config import MONGO_URI


def _make_client() -> MongoClient:
	"""Create a MongoClient for the shared MongoDB deployment."""
	# Resolve URI with a clear error if missing
	uri = (MONGO_URI or os.getenv("MONGODB_URI") or "").strip()
	if not uri:
		raise RuntimeError(
			"MongoDB URI is not set. Provide ATLAS_URI in .env (mapped to MONGO_URI/MONGODB_URI)."
		)

	kwargs = {"server_api": ServerApi('1')}
	return MongoClient(uri, **kwargs)


db_client = _make_client()

try:
	db_client.admin.command('ping')
	logging.info("Pinged MongoDB. Connection OK.")
except Exception as e:
	logging.error("MongoDB ping failed: %s", e)


def create_db(db_name: str):
	return db_client.get_database(db_name)


def delete_db(db_name: str):
	return db_client.drop_database(db_name)
