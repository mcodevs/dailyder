from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dailyder_bot.db.models import User
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.services.admin import AdminService
from dailyder_bot.services.metrics import MetricsService


async def _seed_user(
    db: DatabaseSessionManager,
    *,
    user_id: str,
    telegram_user_id: int,
    username: str,
) -> User:
    user = User(
        id=user_id,
        telegram_user_id=telegram_user_id,
        username=username,
        first_name="Test",
        last_name="User",
        is_active=True,
        created_in_group_id=-100,
        joined_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    async with db.session() as session:
        async with session.begin():
            session.add(user)
    return user


def _admin_service(db: DatabaseSessionManager) -> AdminService:
    return AdminService(
        settings=SimpleNamespace(timezone_info=ZoneInfo("Asia/Tashkent"), admin_user_ids=(9001,)),
        db=db,
        access_service=SimpleNamespace(),
        metrics_service=MetricsService(db),
        reminder_service=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_issue_warning_persists_and_is_reflected_in_metrics(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'admin-warning.db'}")
    await db.create_all()
    try:
        await _seed_user(db, user_id="user-1", telegram_user_id=1001, username="devuser")
        service = _admin_service(db)
        issued_at = datetime(2026, 3, 22, 10, 0, tzinfo=ZoneInfo("Asia/Tashkent"))

        issued = await service.issue_warning(
            admin_telegram_user_id=9001,
            developer_username="@devuser",
            group_chat_id=-100123,
            reason="Digest was missing the release blocker.",
            now=issued_at,
        )

        assert issued.developer.username == "devuser"
        assert issued.warning.reason == "Digest was missing the release blocker."

        report = await service.metrics_report(date(2026, 3, 22))

        assert "@devuser" in report
        assert "Admin ogohlantirishlari (oy): 1" in report
    finally:
        await db.dispose()
