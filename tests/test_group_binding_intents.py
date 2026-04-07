from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dailyder_bot.config.settings import Settings
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.services.group_binding import GroupBindingIntentService


def build_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123456:test-token",
        DATABASE_URL="sqlite+aiosqlite:///unused.db",
        ADMIN_USER_IDS="9001",
        BIND_INTENT_TTL_MINUTES=15,
    )


@pytest.mark.asyncio
async def test_group_binding_intent_service_creates_and_consumes_token(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'binding-intent.db'}")
    await db.create_all()
    settings = build_settings()
    service = GroupBindingIntentService(settings, db)
    now = datetime.now(UTC)

    intent = await service.create_intent(admin_telegram_user_id=9001, now=now)
    consumed = await service.consume_intent(
        token=intent.token,
        admin_telegram_user_id=9001,
        now=now + timedelta(minutes=1),
    )

    assert intent.token
    assert consumed.token == intent.token
    assert consumed.consumed_at is not None

    await db.dispose()


@pytest.mark.asyncio
async def test_group_binding_intent_service_rejects_wrong_admin(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'binding-intent-admin.db'}")
    await db.create_all()
    settings = build_settings()
    service = GroupBindingIntentService(settings, db)
    now = datetime.now(UTC)

    intent = await service.create_intent(admin_telegram_user_id=9001, now=now)

    with pytest.raises(ValueError, match="boshqa admin"):
        await service.consume_intent(
            token=intent.token,
            admin_telegram_user_id=7007,
            now=now + timedelta(minutes=1),
        )

    await db.dispose()
