import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nonagon")

MONGO_OP_TIMEOUT_MS = int(os.getenv("MONGO_OP_TIMEOUT_MS", "5000"))
MONGO_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
)
MONGO_APPNAME = os.getenv("MONGO_APPNAME", "nonagon")
