from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from dailyder_bot.db.models import DeveloperWarning, User
from dailyder_bot.config.settings import Settings
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.repositories.admin_audit import AdminAuditRepository
from dailyder_bot.repositories.app_settings import AppSettingsRepository
from dailyder_bot.repositories.digests import DigestRepository
from dailyder_bot.repositories.submissions import SubmissionRepository
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.repositories.warnings import DeveloperWarningRepository
from dailyder_bot.services.access import AccessService
from dailyder_bot.services.metrics import MetricsService
from dailyder_bot.services.reminders import ReminderService
from dailyder_bot.utils.dates import format_uz_date
from dailyder_bot.utils.telegram import user_mention_html


@dataclass(slots=True)
class IssuedWarning:
    developer: User
    warning: DeveloperWarning


@dataclass(slots=True)
class ReadinessSnapshot:
    binding: object | None
    admin_count: int
    onboarded_user_count: int
    am_scheduler: str
    pm_scheduler: str


@dataclass(slots=True)
class PendingSnapshot:
    work_date: date
    am_pending_users: list[User]
    pm_pending_users: list[User]


class AdminService:
    def __init__(
        self,
        settings: Settings,
        db: DatabaseSessionManager,
        access_service: AccessService,
        metrics_service: MetricsService,
        reminder_service: ReminderService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.access_service = access_service
        self.metrics_service = metrics_service
        self.reminder_service = reminder_service

    async def bind_group(self, admin_user_id: int, chat_id: int, title: str, now: datetime) -> None:
        await self.bind_group_with_topic(admin_user_id, chat_id, title, None, now)

    async def bind_group_with_topic(
        self,
        admin_user_id: int,
        chat_id: int,
        title: str,
        message_thread_id: int | None,
        now: datetime,
    ) -> None:
        async with self.db.session() as session:
            async with session.begin():
                settings_repo = AppSettingsRepository(session)
                await settings_repo.set_group_binding(chat_id, title, message_thread_id)
                await AdminAuditRepository(session).log(
                    admin_telegram_user_id=admin_user_id,
                    action="bind_group",
                    payload={
                        "chat_id": chat_id,
                        "title": title,
                        "message_thread_id": message_thread_id,
                    },
                    created_at=now,
                )

    async def readiness_report(self) -> str:
        snapshot = await self.readiness_snapshot()
        binding = snapshot.binding
        lines = [
            "<b>Bot holati</b>",
            f"Group binding: {'bor' if binding else 'yoʻq'}",
            f"Guruh: {binding.title or binding.chat_id if binding else 'biriktirilmagan'}",
            (
                f"Topic: {binding.message_thread_id}"
                if binding and binding.message_thread_id is not None
                else "Topic: butun guruh"
            ),
            f"Adminlar: {snapshot.admin_count} ta",
            f"Onboarded developerlar: {snapshot.onboarded_user_count} ta",
            f"AM scheduler: {snapshot.am_scheduler}",
            f"PM scheduler: {snapshot.pm_scheduler}",
        ]
        return "\n".join(lines)

    async def readiness_snapshot(self) -> ReadinessSnapshot:
        async with self.db.session() as session:
            settings_repo = AppSettingsRepository(session)
            user_repo = UserRepository(session)
            binding = await settings_repo.get_group_binding()
            if binding is None and self.settings.group_chat_id is not None:
                from dailyder_bot.repositories.app_settings import GroupBinding

                binding = GroupBinding(chat_id=self.settings.group_chat_id, title=None, message_thread_id=None)
            user_count = await user_repo.count_active()

        return ReadinessSnapshot(
            binding=binding,
            admin_count=len(self.settings.admin_user_ids),
            onboarded_user_count=user_count,
            am_scheduler=self.settings.am_reminder_time,
            pm_scheduler=self.settings.pm_reminder_time,
        )

    async def pending_report(self, work_date: date) -> str:
        snapshot = await self.pending_snapshot(work_date)
        am_pending = [user_mention_html(user) for user in snapshot.am_pending_users]
        pm_pending = [user_mention_html(user) for user in snapshot.pm_pending_users]
        return "\n".join(
            [
                f"<b>Pending holat — {format_uz_date(snapshot.work_date)}</b>",
                "",
                "AM pending:",
                "\n".join(am_pending) if am_pending else "Yo'q",
                "",
                "PM pending:",
                "\n".join(pm_pending) if pm_pending else "Yo'q",
            ]
        )

    async def pending_snapshot(self, work_date: date) -> PendingSnapshot:
        async with self.db.session() as session:
            user_repo = UserRepository(session)
            submission_repo = SubmissionRepository(session)
            users = await user_repo.list_active()
            submissions = await submission_repo.list_for_window(work_date, work_date)

        submission_lookup = {submission.user.telegram_user_id: submission for submission in submissions}
        am_pending_users: list[User] = []
        pm_pending_users: list[User] = []

        for user in users:
            submission = submission_lookup.get(user.telegram_user_id)
            if submission is None or submission.am_submitted_at is None:
                am_pending_users.append(user)
                continue
            if submission.pm_submitted_at is None:
                pm_pending_users.append(user)

        return PendingSnapshot(
            work_date=work_date,
            am_pending_users=am_pending_users,
            pm_pending_users=pm_pending_users,
        )

    async def metrics_report(self, as_of_date: date) -> str:
        return await self.metrics_service.build_report(
            as_of_date,
            timezone_info=self.settings.timezone_info,
            days=30,
        )

    async def onboarded_users_report(self) -> str:
        users = await self.list_onboarded_users()
        lines = ["<b>Onboarded developerlar</b>"]
        if not users:
            lines.append("")
            lines.append("Hali hech kim /start qilmagan.")
            return "\n".join(lines)

        for user in users:
            lines.append("")
            lines.append(
                f"{user_mention_html(user)} | joined: {format_uz_date(user.joined_at.date())}"
            )
        return "\n".join(lines)

    async def list_onboarded_users(self) -> list[User]:
        async with self.db.session() as session:
            return await UserRepository(session).list_active()

    async def resend_missing(self, period: str, work_date: date, admin_user_id: int, now: datetime) -> int:
        async with self.db.session() as session:
            submission_repo = SubmissionRepository(session)
            user_repo = UserRepository(session)
            users = await user_repo.list_active()
            submissions = await submission_repo.list_for_window(work_date, work_date)

        submission_lookup = {submission.user.telegram_user_id: submission for submission in submissions}
        missing_user_ids: set[int] = set()
        for user in users:
            submission = submission_lookup.get(user.telegram_user_id)
            if period == "am":
                if submission is None or submission.am_submitted_at is None:
                    missing_user_ids.add(user.telegram_user_id)
            else:
                if submission is not None and submission.am_submitted_at is not None and submission.pm_submitted_at is None:
                    missing_user_ids.add(user.telegram_user_id)

        if period == "am":
            sent_count = await self.reminder_service.send_morning_reminders(work_date, missing_user_ids)
        else:
            sent_count = await self.reminder_service.send_pm_reminders(work_date, missing_user_ids)

        async with self.db.session() as session:
            async with session.begin():
                await AdminAuditRepository(session).log(
                    admin_telegram_user_id=admin_user_id,
                    action="remind_missing",
                    payload={"period": period, "work_date": work_date.isoformat(), "count": sent_count},
                    created_at=now,
                )

        return sent_count

    async def resolve_warning_target(self, username: str) -> User | None:
        async with self.db.session() as session:
            return await UserRepository(session).get_by_username(username)

    async def issue_warning(
        self,
        *,
        admin_telegram_user_id: int,
        developer_username: str,
        group_chat_id: int,
        reason: str,
        now: datetime,
    ) -> IssuedWarning:
        async with self.db.session() as session:
            async with session.begin():
                user_repo = UserRepository(session)
                developer = await user_repo.get_by_username(developer_username)
                if developer is None:
                    raise ValueError("Developer username topilmadi.")
                warning = await DeveloperWarningRepository(session).create(
                    developer_user_id=developer.id,
                    admin_telegram_user_id=admin_telegram_user_id,
                    group_chat_id=group_chat_id,
                    reason=reason,
                    created_at=now,
                )
                await AdminAuditRepository(session).log(
                    admin_telegram_user_id=admin_telegram_user_id,
                    action="issue_warning",
                    payload={
                        "developer_user_id": developer.id,
                        "developer_username": developer.username,
                        "group_chat_id": group_chat_id,
                    },
                    created_at=now,
                )
        return IssuedWarning(developer=warning.developer, warning=warning)

    async def cleanup_history(self, as_of_date: date) -> int:
        cutoff_date = as_of_date - timedelta(days=30)
        async with self.db.session() as session:
            async with session.begin():
                submission_removed = await SubmissionRepository(session).cleanup_older_than(cutoff_date)
                digest_removed = await DigestRepository(session).cleanup_older_than(cutoff_date)
        return submission_removed + digest_removed
