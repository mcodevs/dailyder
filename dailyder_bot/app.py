from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from dailyder_bot.bot.routers import register_routers
from dailyder_bot.config.settings import Settings, get_settings
from dailyder_bot.container import AppContext
from dailyder_bot.db.migrate import apply_migrations
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.domain.parser import MorningSubmissionParser
from dailyder_bot.scheduler.jobs import ReminderScheduler
from dailyder_bot.services.access import AccessService
from dailyder_bot.services.admin import AdminService
from dailyder_bot.services.digest import DigestService
from dailyder_bot.services.flow_sessions import FlowSessionService
from dailyder_bot.services.metrics import MetricsService
from dailyder_bot.services.reminders import ReminderService
from dailyder_bot.services.submissions import SubmissionService
from dailyder_bot.web.health import HealthServer


class DailyderApplication:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = DatabaseSessionManager(self.settings.database_url)
        self.bot = Bot(
            token=self.settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher(storage=MemoryStorage())

        parser = MorningSubmissionParser()
        access_service = AccessService(self.settings, self.db)
        flow_session_service = FlowSessionService(self.db)
        submission_service = SubmissionService(self.settings, self.db, parser)
        digest_service = DigestService(self.settings, self.db, self.bot, access_service)
        metrics_service = MetricsService(self.db)
        reminder_service = ReminderService(
            settings=self.settings,
            db=self.db,
            bot=self.bot,
            access_service=access_service,
            submission_service=submission_service,
        )
        admin_service = AdminService(
            settings=self.settings,
            db=self.db,
            access_service=access_service,
            metrics_service=metrics_service,
            reminder_service=reminder_service,
        )
        self.context = AppContext(
            settings=self.settings,
            db=self.db,
            bot=self.bot,
            access_service=access_service,
            flow_session_service=flow_session_service,
            submission_service=submission_service,
            digest_service=digest_service,
            reminder_service=reminder_service,
            metrics_service=metrics_service,
            admin_service=admin_service,
        )
        register_routers(self.dispatcher)
        self.scheduler = ReminderScheduler(self.context)
        self.health_server = HealthServer(self.db, self.settings.port)

    async def run(self) -> None:
        await apply_migrations(self.settings.database_url)
        await self.health_server.start()
        self.scheduler.start()
        await self.scheduler.run_startup_recovery()
        try:
            await self.dispatcher.start_polling(self.bot, app_context=self.context)
        finally:
            await self.scheduler.stop()
            await self.health_server.stop()
            await self.bot.session.close()
            await self.db.dispose()
