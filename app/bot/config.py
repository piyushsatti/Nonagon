from dotenv import load_dotenv
import os
load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN")
MONGO_URI   = os.getenv("MONGO_URI", "mongodb://localhost:27017")

DB_NAME     = os.getenv("DB_NAME", "nonagon")
DB_USERNAME = os.getenv("DB_USERNAME", "username")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
