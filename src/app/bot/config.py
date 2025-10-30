import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

DB_NAME = os.getenv("DB_NAME", "nonagon")

# Optional: use per-guild adapter for bot flush persistence
BOT_FLUSH_VIA_ADAPTER = os.getenv("BOT_FLUSH_VIA_ADAPTER", "false").lower() in {
    "1",
    "true",
    "yes",
}

QUEST_API_BASE_URL = os.getenv("QUEST_API_BASE_URL")

board_id_raw = os.getenv("QUEST_BOARD_CHANNEL_ID")
try:
    QUEST_BOARD_CHANNEL_ID: Optional[int] = int(board_id_raw) if board_id_raw else None
except ValueError:
    QUEST_BOARD_CHANNEL_ID = None
