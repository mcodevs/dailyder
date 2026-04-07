from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dailyder_bot.db.models import DailySubmission, User
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.repositories.submissions import SubmissionRepository
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.repositories.warnings import DeveloperWarningRepository
from dailyder_bot.utils.dates import format_uz_date, iter_workdays
from dailyder_bot.utils.telegram import user_mention_html


@dataclass(slots=True)
class UserMetricsSnapshot:
    user: User
    expected_workdays: int = 0
    am_submitted: int = 0
    pm_submitted: int = 0
    missed_am: int = 0
    missed_pm: int = 0
    completed: int = 0
    warning: int = 0
    blocked: int = 0
    dropped: int = 0
    admin_warnings_month: int = 0


@dataclass(slots=True)
class MetricsReportSnapshot:
    start_date: date
    end_date: date
    days: int
    users: list[UserMetricsSnapshot]


class MetricsService:
    def __init__(self, db: DatabaseSessionManager) -> None:
        self.db = db

    async def build_report(self, as_of_date: date, timezone_info: ZoneInfo, days: int = 30) -> str:
        snapshot = await self.build_snapshot(as_of_date, timezone_info, days)
        lines = [
            f"<b>Oxirgi {snapshot.days} kunlik metrikalar</b>",
            f"Oraliq: {format_uz_date(snapshot.start_date)} - {format_uz_date(snapshot.end_date)}",
        ]
        if not snapshot.users:
            lines.append("")
            lines.append("Faol developerlar topilmadi.")
            return "\n".join(lines)

        for user_snapshot in snapshot.users:
            lines.extend(
                [
                    "",
                    user_mention_html(user_snapshot.user),
                    (
                        f"AM: {user_snapshot.am_submitted}/{user_snapshot.expected_workdays} | "
                        f"Missed AM: {user_snapshot.missed_am}"
                    ),
                    f"PM: {user_snapshot.pm_submitted} | Missed PM: {user_snapshot.missed_pm}",
                    (
                        "Statuslar: "
                        f"✅ {user_snapshot.completed} | ⚠️ {user_snapshot.warning} | "
                        f"🚫 {user_snapshot.blocked} | 🪓 {user_snapshot.dropped}"
                    ),
                    f"Admin ogohlantirishlari (oy): {user_snapshot.admin_warnings_month}",
                ]
            )
        return "\n".join(lines)

    async def build_snapshot(self, as_of_date: date, timezone_info: ZoneInfo, days: int = 30) -> MetricsReportSnapshot:
        start_date = as_of_date - timedelta(days=days - 1)
        month_start = as_of_date.replace(day=1)
        next_month_start = (
            as_of_date.replace(year=as_of_date.year + 1, month=1, day=1)
            if as_of_date.month == 12
            else as_of_date.replace(month=as_of_date.month + 1, day=1)
        )
        month_start_at = datetime.combine(month_start, time.min, tzinfo=timezone_info)
        month_end_at = datetime.combine(next_month_start, time.min, tzinfo=timezone_info)
        async with self.db.session() as session:
            user_repo = UserRepository(session)
            submission_repo = SubmissionRepository(session)
            warning_repo = DeveloperWarningRepository(session)
            users = await user_repo.list_active()
            submissions = await submission_repo.list_for_window(start_date, as_of_date)
            warnings = await warning_repo.list_for_window(month_start_at, month_end_at)

        workdays = iter_workdays(start_date, as_of_date)
        warning_counts = Counter(warning.developer_user_id for warning in warnings)
        snapshots = self._build_snapshots(users, submissions, workdays, warning_counts)
        return MetricsReportSnapshot(
            start_date=start_date,
            end_date=as_of_date,
            days=days,
            users=snapshots,
        )

    def _build_snapshots(
        self,
        users: list[User],
        submissions: list[DailySubmission],
        workdays: list[date],
        warning_counts: Counter[str] | None = None,
    ) -> list[UserMetricsSnapshot]:
        submission_map = {
            (submission.user.telegram_user_id, submission.work_date): submission
            for submission in submissions
        }
        warning_counts = warning_counts or Counter()
        snapshots: list[UserMetricsSnapshot] = []
        for user in users:
            snapshot = UserMetricsSnapshot(
                user=user,
                admin_warnings_month=warning_counts.get(user.id, 0),
            )
            user_start_date = user.joined_at.date()
            user_workdays = [day for day in workdays if day >= user_start_date]
            snapshot.expected_workdays = len(user_workdays)

            for workday in user_workdays:
                submission = submission_map.get((user.telegram_user_id, workday))
                if submission is None or submission.am_submitted_at is None:
                    snapshot.missed_am += 1
                    continue
                snapshot.am_submitted += 1
                if submission.pm_submitted_at is None:
                    snapshot.missed_pm += 1
                else:
                    snapshot.pm_submitted += 1

                for item in submission.items:
                    if item.status is None:
                        continue
                    status = ItemStatus(item.status.status)
                    if status is ItemStatus.COMPLETED:
                        snapshot.completed += 1
                    elif status is ItemStatus.WARNING:
                        snapshot.warning += 1
                    elif status is ItemStatus.BLOCKED:
                        snapshot.blocked += 1
                    elif status is ItemStatus.DROPPED:
                        snapshot.dropped += 1
            snapshots.append(snapshot)
        return snapshots
