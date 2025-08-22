import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("App package initialized")

from dotenv import load_dotenv
load_dotenv()