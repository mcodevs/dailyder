from datetime import UTC, date, datetime, timedelta

import pytest

from dailyder_bot.db.models import User
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.services.flow_sessions import FlowSessionService


async def _create_user(db: DatabaseSessionManager, telegram_user_id: int = 1001) -> User:
    user = User(
        id=f"user-{telegram_user_id}",
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        first_name="Test",
        last_name=str(telegram_user_id),
        is_active=True,
        created_in_group_id=-100,
        joined_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    async with db.session() as session:
        async with session.begin():
            session.add(user)
    return user


@pytest.mark.asyncio
async def test_flow_session_round_trip(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'flow.db'}")
    await db.create_all()
    try:
        user = await _create_user(db)
        service = FlowSessionService(db)
        now = datetime(2026, 3, 18, 10, 0, tzinfo=UTC)

        await service.set(
            user_id=user.id,
            flow="morning",
            work_date=date(2026, 3, 18),
            step="awaiting_task_name",
            payload={"project_name": "TvRain"},
            now=now,
        )

        session_state = await service.get(
            user_id=user.id,
            flow="morning",
            work_date=date(2026, 3, 18),
            now=now,
        )

        assert session_state is not None
        assert session_state.step == "awaiting_task_name"
        assert session_state.payload == {"project_name": "TvRain"}

        await service.clear(
            user_id=user.id,
            flow="morning",
            work_date=date(2026, 3, 18),
        )

        assert await service.get(
            user_id=user.id,
            flow="morning",
            work_date=date(2026, 3, 18),
            now=now,
        ) is None
    finally:
        await db.dispose()


@pytest.mark.asyncio
async def test_flow_session_expires_and_is_cleared(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'flow-expire.db'}")
    await db.create_all()
    try:
        user = await _create_user(db, telegram_user_id=1002)
        service = FlowSessionService(db)
        now = datetime(2026, 3, 18, 10, 0, tzinfo=UTC)

        await service.set(
            user_id=user.id,
            flow="pm",
            work_date=date(2026, 3, 18),
            step="awaiting_note",
            payload={"final_note": None},
            now=now,
        )

        expired = await service.get(
            user_id=user.id,
            flow="pm",
            work_date=date(2026, 3, 18),
            now=now + timedelta(hours=13),
        )

        assert expired is None
    finally:
        await db.dispose()
