from dataclasses import asdict, is_dataclass
import logging
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from .config import DB_USERNAME, DB_PASSWORD

uri = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@nonagon.upiarrl.mongodb.net/?retryWrites=true&w=majority&appName=nonagon"
db_client = MongoClient(uri, server_api=ServerApi('1'))

try:
  db_client.admin.command('ping')
  logging.info("Pinged your deployment. You successfully connected to MongoDB!")

except Exception as e:
  logging.error(e)

def create_db(db_name):
  return db_client.get_database(db_name)

def delete_db(db_name):
  return db_client.drop_database(db_name)