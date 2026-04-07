from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import GroupBindingIntent
from dailyder_bot.utils.ids import new_id


class GroupBindingIntentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        token: str,
        admin_telegram_user_id: int,
        expires_at: datetime,
    ) -> GroupBindingIntent:
        intent = GroupBindingIntent(
            id=new_id(),
            token=token,
            admin_telegram_user_id=admin_telegram_user_id,
            expires_at=expires_at,
        )
        self.session.add(intent)
        await self.session.flush()
        return intent

    async def get_by_token(self, token: str) -> GroupBindingIntent | None:
        result = await self.session.execute(
            select(GroupBindingIntent).where(GroupBindingIntent.token == token)
        )
        return result.scalar_one_or_none()

    async def consume(self, *, token: str, consumed_at: datetime) -> GroupBindingIntent | None:
        intent = await self.get_by_token(token)
        if intent is None:
            return None
        intent.consumed_at = consumed_at
        await self.session.flush()
        return intent
