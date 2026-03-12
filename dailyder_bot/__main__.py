from __future__ import annotations

import asyncio

from dailyder_bot.app import DailyderApplication


def main() -> None:
    asyncio.run(DailyderApplication().run())


if __name__ == "__main__":
    main()
