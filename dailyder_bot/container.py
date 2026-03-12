from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot

from dailyder_bot.config.settings import Settings
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.services.access import AccessService
from dailyder_bot.services.admin import AdminService
from dailyder_bot.services.digest import DigestService
from dailyder_bot.services.metrics import MetricsService
from dailyder_bot.services.reminders import ReminderService
from dailyder_bot.services.submissions import SubmissionService


@dataclass(slots=True)
class AppContext:
    settings: Settings
    db: DatabaseSessionManager
    bot: Bot
    access_service: AccessService
    submission_service: SubmissionService
    digest_service: DigestService
    reminder_service: ReminderService
    metrics_service: MetricsService
    admin_service: AdminService

