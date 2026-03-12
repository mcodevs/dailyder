from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from dailyder_bot.db.base import Base


class DatabaseSessionManager:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
        )
        self._sessionmaker = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self):
        async with self._sessionmaker() as session:
            yield session

    async def ping(self) -> bool:
        async with self.engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def create_all(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()

