import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("App package initialized")

try:
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    logger.warning("python-dotenv not installed; skipping .env loading.")
else:
    load_dotenv()
