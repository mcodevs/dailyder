from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dailyder_bot.domain.enums import DigestPeriod
from dailyder_bot.scheduler.jobs import ReminderScheduler


class _FakeAccessService:
    async def get_bound_group_id(self):
        return -100123

    async def get_group_binding(self):
        return object()


class _FakeBindingAccessService:
    def __init__(self, binding_present: bool = True) -> None:
        self.binding_present = binding_present

    async def get_group_binding(self):
        return object() if self.binding_present else None


class _FakeDigestService:
    def __init__(self) -> None:
        self.calls: list[tuple[date, DigestPeriod]] = []

    async def ensure_digest(self, work_date: date, period: DigestPeriod) -> None:
        self.calls.append((work_date, period))


@pytest.mark.asyncio
async def test_startup_recovery_creates_am_and_pm_after_pm_time(monkeypatch) -> None:
    digest_service = _FakeDigestService()
    context = SimpleNamespace(
        settings=SimpleNamespace(
            timezone_info=ZoneInfo("Asia/Tashkent"),
            am_time=time(9, 0),
            pm_time=time(17, 0),
        ),
        access_service=_FakeAccessService(),
        digest_service=digest_service,
    )
    scheduler = ReminderScheduler(context)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "dailyder_bot.scheduler.jobs.local_now",
        lambda _: datetime(2026, 3, 12, 18, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    await scheduler.run_startup_recovery()

    assert digest_service.calls == [
        (date(2026, 3, 12), DigestPeriod.AM),
        (date(2026, 3, 12), DigestPeriod.PM),
    ]
