import asyncio

from app.bot.core.logging import configure_logging
from app.bot.core.runtime import start_bot
from app.bot.core.settings import load_settings


def main() -> None:
    configure_logging()
    settings = load_settings()
    asyncio.run(start_bot(settings))


if __name__ == "__main__":
    main()
