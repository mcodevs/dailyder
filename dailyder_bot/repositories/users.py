from __future__ import annotations

from datetime import datetime

from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import User
from dailyder_bot.utils.ids import new_id


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        normalized = username.strip().lstrip("@").lower()
        if not normalized:
            return None
        result = await self.session.execute(
            select(User).where(
                func.lower(User.username) == normalized,
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_telegram(
        self,
        telegram_user: TelegramUser,
        joined_at: datetime,
        created_in_group_id: int | None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_user.id)
        if user is None:
            user = User(
                id=new_id(),
                telegram_user_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                joined_at=joined_at,
                last_seen_at=joined_at,
                created_in_group_id=created_in_group_id,
                is_active=True,
            )
            self.session.add(user)
        else:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            user.last_seen_at = joined_at
            user.is_active = True
            if created_in_group_id is not None:
                user.created_in_group_id = created_in_group_id
        await self.session.flush()
        return user

    async def touch_last_seen(self, telegram_user_id: int, seen_at: datetime) -> None:
        user = await self.get_by_telegram_id(telegram_user_id)
        if user is None:
            return
        user.last_seen_at = seen_at
        await self.session.flush()

    async def list_active(self) -> list[User]:
        result = await self.session.execute(
            select(User)
            .where(User.is_active.is_(True))
            .order_by(User.joined_at.asc(), User.telegram_user_id.asc())
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
        return int(result.scalar_one())
