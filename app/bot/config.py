from dotenv import load_dotenv
import os
load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN")
MONGO_URI   = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME     = os.getenv("DB_NAME", "smokebomb")

LEVEL_ANNOUNCE_CHANNEL = int(os.getenv("LEVEL_ANNOUNCE_CHANNEL", 0))   # id of #guild-hall
SUMMARY_CHANNEL        = int(os.getenv("SUMMARY_CHANNEL", 0))          # id of #adventure-summaries
INACTIVITY_DAYS        = int(os.getenv("INACTIVITY_DAYS", 21))
