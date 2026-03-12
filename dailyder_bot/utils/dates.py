from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def local_now(timezone: ZoneInfo) -> datetime:
    return datetime.now(UTC).astimezone(timezone)


def today_local(timezone: ZoneInfo) -> date:
    return local_now(timezone).date()


def is_workday(target_date: date) -> bool:
    return target_date.weekday() < 5


def iter_workdays(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        return []
    days: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if is_workday(cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def format_uz_date(target_date: date) -> str:
    return target_date.strftime("%d.%m.%Y")

