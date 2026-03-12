from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from dailyder_bot.container import AppContext
from dailyder_bot.domain.enums import DigestPeriod
from dailyder_bot.services.access import GroupBindingError
from dailyder_bot.utils.dates import is_workday, local_now, today_local


class ReminderScheduler:
    def __init__(self, app_context: AppContext) -> None:
        self.app_context = app_context
        self.scheduler = AsyncIOScheduler(timezone=app_context.settings.timezone_info)

    def start(self) -> None:
        self.scheduler.add_job(
            self.run_morning_job,
            CronTrigger(
                day_of_week="mon-fri",
                hour=self.app_context.settings.am_time.hour,
                minute=self.app_context.settings.am_time.minute,
                timezone=self.app_context.settings.timezone_info,
            ),
            id="am-reminder",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_pm_job,
            CronTrigger(
                day_of_week="mon-fri",
                hour=self.app_context.settings.pm_time.hour,
                minute=self.app_context.settings.pm_time.minute,
                timezone=self.app_context.settings.timezone_info,
            ),
            id="pm-reminder",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_cleanup_job,
            CronTrigger(
                hour=0,
                minute=30,
                timezone=self.app_context.settings.timezone_info,
            ),
            id="cleanup-history",
            replace_existing=True,
        )
        self.scheduler.start()

    async def run_startup_recovery(self) -> None:
        if await self.app_context.access_service.get_bound_group_id() is None:
            return
        now = local_now(self.app_context.settings.timezone_info)
        work_date = now.date()
        if not is_workday(work_date):
            return
        if now.time() >= self.app_context.settings.am_time:
            await self.app_context.digest_service.ensure_digest(work_date, DigestPeriod.AM)
        if now.time() >= self.app_context.settings.pm_time:
            await self.app_context.digest_service.ensure_digest(work_date, DigestPeriod.PM)

    async def run_morning_job(self) -> None:
        work_date = today_local(self.app_context.settings.timezone_info)
        if not is_workday(work_date):
            return
        try:
            await self.app_context.digest_service.ensure_digest(work_date, DigestPeriod.AM)
            await self.app_context.reminder_service.send_morning_reminders(work_date)
        except GroupBindingError:
            return

    async def run_pm_job(self) -> None:
        work_date = today_local(self.app_context.settings.timezone_info)
        if not is_workday(work_date):
            return
        try:
            await self.app_context.digest_service.ensure_digest(work_date, DigestPeriod.PM)
            await self.app_context.reminder_service.send_pm_reminders(work_date)
        except GroupBindingError:
            return

    async def run_cleanup_job(self) -> None:
        await self.app_context.admin_service.cleanup_history(
            today_local(self.app_context.settings.timezone_info)
        )

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
