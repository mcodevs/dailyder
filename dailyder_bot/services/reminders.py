from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Awaitable, Callable

from aiogram import Bot

from dailyder_bot.bot import keyboards, texts
from dailyder_bot.config.settings import Settings
from dailyder_bot.db.models import User
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.services.access import AccessService
from dailyder_bot.services.submissions import SubmissionService
from dailyder_bot.utils.telegram import user_mention_html

logger = logging.getLogger(__name__)
ReminderSendCallback = Callable[[User], Awaitable[bool]]


class ReminderService:
    MAX_CONCURRENT_REMINDERS = 4

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
        mini_app_url = getattr(self.settings, "mini_app_url", None)
        async with self.db.session() as session:
            users = await UserRepository(session).list_active()

        async def send_one(user) -> bool:
            if not await self.access_service.is_group_member(self.bot, group_chat_id, user.telegram_user_id):
                return False
            await self.bot.send_message(
                chat_id=user.telegram_user_id,
                text=texts.morning_reminder_text(work_date, self.settings.hashtag, user_mention_html(user)),
                reply_markup=keyboards.morning_shortcuts(
                    mini_app_url=mini_app_url,
                ),
            )
            return True

        return await self._send_reminders(users, only_user_ids, send_one)

    async def send_pm_reminders(self, work_date: date, only_user_ids: set[int] | None = None) -> int:
        group_chat_id = await self.access_service.require_bound_group_id()
        mini_app_url = getattr(self.settings, "mini_app_url", None)
        async with self.db.session() as session:
            users = await UserRepository(session).list_active()
        eligible_user_ids = [
            user.telegram_user_id
            for user in users
            if only_user_ids is None or user.telegram_user_id in only_user_ids
        ]
        submission_map = await self.submission_service.get_today_submission_map(
            eligible_user_ids,
            work_date,
        )

        async def send_one(user) -> bool:
            if not await self.access_service.is_group_member(self.bot, group_chat_id, user.telegram_user_id):
                return False
            await self.bot.send_message(
                chat_id=user.telegram_user_id,
                text=texts.pm_reminder_text(
                    work_date,
                    user.telegram_user_id in submission_map,
                ),
                reply_markup=keyboards.pm_shortcuts(
                    has_submission=user.telegram_user_id in submission_map,
                    mini_app_url=mini_app_url,
                ),
            )
            return True

        return await self._send_reminders(users, only_user_ids, send_one)

    async def _send_reminders(
        self,
        users: list[User],
        only_user_ids: set[int] | None,
        send_one: ReminderSendCallback,
    ) -> int:
        eligible_users = [
            user
            for user in users
            if only_user_ids is None or user.telegram_user_id in only_user_ids
        ]
        if not eligible_users:
            return 0

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REMINDERS)

        async def deliver(user: User) -> int:
            async with semaphore:
                try:
                    return 1 if await send_one(user) else 0
                except Exception:
                    logger.exception(
                        "Failed to send reminder",
                        extra={"telegram_user_id": user.telegram_user_id},
                    )
                    return 0

        results = await asyncio.gather(*(deliver(user) for user in eligible_users))
        return sum(results)
