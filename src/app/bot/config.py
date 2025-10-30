import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_int(name: str) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
MONGO_URI: str = os.getenv("MONGO_URI", "")
DB_NAME: str = os.getenv("DB_NAME", "")
BOT_FLUSH_VIA_ADAPTER: bool = _env_bool("BOT_FLUSH_VIA_ADAPTER", default=False)
QUEST_API_BASE_URL: str = os.getenv("QUEST_API_BASE_URL", "").strip()
QUEST_BOARD_CHANNEL_ID: Optional[int] = _env_optional_int("QUEST_BOARD_CHANNEL_ID")

if BOT_TOKEN == "":
    raise ValueError("BOT_TOKEN environment variable is not set.")

if MONGO_URI == "":
    raise ValueError("MONGO_URI environment variable is not set.")

if DB_NAME == "":
    raise ValueError("DB_NAME environment variable is not set.")
