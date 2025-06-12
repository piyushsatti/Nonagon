from pymongo import MongoClient, ASCENDING
from .config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)

db = client[DB_NAME]