from __future__ import annotations

from datetime import date

from aiogram import Bot

from dailyder_bot.bot import keyboards, texts
from dailyder_bot.config.settings import Settings
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.services.access import AccessService
from dailyder_bot.services.submissions import SubmissionService
from dailyder_bot.utils.telegram import user_mention_html


class ReminderService:
    def __init__(
        self,
        settings: Settings,
        db: DatabaseSessionManager,
        bot: Bot,
        access_service: AccessService,
        submission_service: SubmissionService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.bot = bot
        self.access_service = access_service
        self.submission_service = submission_service

    async def send_morning_reminders(self, work_date: date, only_user_ids: set[int] | None = None) -> int:
        group_chat_id = await self.access_service.require_bound_group_id()
        async with self.db.session() as session:
            users = await UserRepository(session).list_active()

        sent_count = 0
        for user in users:
            if only_user_ids and user.telegram_user_id not in only_user_ids:
                continue
            if not await self.access_service.is_group_member(self.bot, group_chat_id, user.telegram_user_id):
                continue
            await self.bot.send_message(
                chat_id=user.telegram_user_id,
                text=texts.morning_reminder_text(work_date, self.settings.hashtag, user_mention_html(user)),
                reply_markup=keyboards.morning_shortcuts(),
            )
            sent_count += 1
        return sent_count

    async def send_pm_reminders(self, work_date: date, only_user_ids: set[int] | None = None) -> int:
        group_chat_id = await self.access_service.require_bound_group_id()
        async with self.db.session() as session:
            users = await UserRepository(session).list_active()

        sent_count = 0
        for user in users:
            if only_user_ids and user.telegram_user_id not in only_user_ids:
                continue
            if not await self.access_service.is_group_member(self.bot, group_chat_id, user.telegram_user_id):
                continue
            submission = await self.submission_service.get_today_submission(user.telegram_user_id, work_date)
            await self.bot.send_message(
                chat_id=user.telegram_user_id,
                text=texts.pm_reminder_text(work_date, submission is not None),
                reply_markup=keyboards.pm_shortcuts(has_submission=submission is not None),
            )
            sent_count += 1
        return sent_count

