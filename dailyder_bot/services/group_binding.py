from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dailyder_bot.config.settings import Settings
from dailyder_bot.db.models import GroupBindingIntent
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.repositories.group_binding_intents import GroupBindingIntentRepository


@dataclass(slots=True)
class BindingIntentResult:
    token: str
    expires_at: datetime


class GroupBindingIntentService:
    def __init__(self, settings: Settings, db: DatabaseSessionManager) -> None:
        self.settings = settings
        self.db = db

    async def create_intent(self, *, admin_telegram_user_id: int, now: datetime) -> BindingIntentResult:
        expires_at = now + timedelta(minutes=self.settings.bind_intent_ttl_minutes)
        token = secrets.token_urlsafe(24)
        async with self.db.session() as session:
            async with session.begin():
                await GroupBindingIntentRepository(session).create(
                    token=token,
                    admin_telegram_user_id=admin_telegram_user_id,
                    expires_at=expires_at,
                )
        return BindingIntentResult(token=token, expires_at=expires_at)

    async def consume_intent(
        self,
        *,
        token: str,
        admin_telegram_user_id: int,
        now: datetime,
    ) -> GroupBindingIntent:
        async with self.db.session() as session:
            async with session.begin():
                repo = GroupBindingIntentRepository(session)
                intent = await repo.get_by_token(token)
                if intent is None:
                    raise ValueError("Binding token topilmadi.")
                if intent.admin_telegram_user_id != admin_telegram_user_id:
                    raise ValueError("Binding token boshqa admin uchun yaratilgan.")
                if intent.consumed_at is not None:
                    raise ValueError("Binding token allaqachon ishlatilgan.")
                expires_at = self.normalize_datetime(intent.expires_at)
                if expires_at <= now:
                    raise ValueError("Binding token muddati tugagan.")
                consumed = await repo.consume(token=token, consumed_at=now)
                if consumed is None:
                    raise ValueError("Binding token topilmadi.")
                return consumed

    @staticmethod
    def normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
