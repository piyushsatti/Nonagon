import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_CLIENT_ID = os.getenv("BOT_CLIENT_ID")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

PRIMARY_GUILD_ID_RAW = os.getenv("PRIMARY_GUILD_ID")
try:
    PRIMARY_GUILD_ID = int(PRIMARY_GUILD_ID_RAW) if PRIMARY_GUILD_ID_RAW else None
except ValueError:
    PRIMARY_GUILD_ID = None

DB_NAME = os.getenv("DB_NAME", "nonagon")
DB_USERNAME = os.getenv("DB_USERNAME", "username")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

DEMO_RESET_ENABLED = os.getenv("DEMO_RESET_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
DEMO_LOG_CHANNEL_ID = os.getenv("DEMO_LOG_CHANNEL_ID")

# Optional: use per-guild adapter for bot flush persistence
BOT_FLUSH_VIA_ADAPTER = os.getenv("BOT_FLUSH_VIA_ADAPTER", "false").lower() in {
    "1",
    "true",
    "yes",
}

QUEST_API_BASE_URL = os.getenv("QUEST_API_BASE_URL")

_forge_ids_raw = os.getenv("QUEST_FORGE_CHANNEL_IDS", "")
FORGE_CHANNEL_IDS = {
    int(token)
    for part in _forge_ids_raw.split(",")
    for token in [part.strip()]
    if token
}

board_id_raw = os.getenv("QUEST_BOARD_CHANNEL_ID")
try:
    QUEST_BOARD_CHANNEL_ID: Optional[int] = int(board_id_raw) if board_id_raw else None
except ValueError:
    QUEST_BOARD_CHANNEL_ID = None
