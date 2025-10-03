import os

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nonagon")

MONGODB_TLS_CA_FILE = os.getenv("MONGODB_TLS_CA_FILE")
MONGODB_TLS_ALLOW_INVALID_CERTS = (
    os.getenv("MONGODB_TLS_ALLOW_INVALID_CERTS", "false").lower() == "true"
)

MONGO_OP_TIMEOUT_MS = int(os.getenv("MONGO_OP_TIMEOUT_MS", "5000"))
MONGO_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
)
MONGO_APPNAME = os.getenv("MONGO_APPNAME", "nonagon")
