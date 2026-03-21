from __future__ import annotations

import asyncio
import logging
import os

from dailyder_bot.app import DailyderApplication


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    configure_logging()
    asyncio.run(DailyderApplication().run())


if __name__ == "__main__":
    main()
