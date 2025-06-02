# bot/database.py

from pymongo import MongoClient, ASCENDING
from .config import MONGO_URI, DB_NAME

# 1. Create the MongoClient using the local Docker URI
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)

# 2. Reference your database
db = client[DB_NAME]

# 3. Define collections for each model
users_col      = db.users             # stores UserModel, Player, DungeonMaster docs
characters_col = db.characters        # stores Character docs
quests_col     = db.quests            # stores Quest docs
summaries_col  = db.quest_summaries   # stores QuestSummary docs

# 4. Ensure indexes on primary keys for fast lookups
users_col.create_index([("user_id", ASCENDING)], unique=True)
characters_col.create_index([("character_id", ASCENDING)], unique=True)
quests_col.create_index([("quest_id", ASCENDING)], unique=True)
summaries_col.create_index([("quest_id", ASCENDING), ("posted_at", ASCENDING)])
