from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from dailyder_bot.config.settings import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def apply_migrations(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(50) PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )

            result = await connection.execute(text("SELECT version FROM schema_migrations"))
            applied = {row[0] for row in result.fetchall()}

            for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = migration_path.stem
                if version in applied:
                    continue
                sql = migration_path.read_text(encoding="utf-8")
                for statement in _split_sql(sql):
                    await connection.execute(text(statement))
                await connection.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                    {"version": version},
                )
    finally:
        await engine.dispose()


def main() -> None:
    settings = get_settings()
    asyncio.run(apply_migrations(settings.database_url))


def _split_sql(sql: str) -> list[str]:
    parts = [part.strip() for part in sql.split(";") if part.strip()]
    return parts


if __name__ == "__main__":
    main()
