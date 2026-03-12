from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from dailyder_bot.bot import texts
from dailyder_bot.config.settings import Settings
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.domain.enums import DigestPeriod
from dailyder_bot.repositories.digests import DigestRepository
from dailyder_bot.repositories.submissions import SubmissionRepository
from dailyder_bot.services.access import AccessService


class DigestService:
    def __init__(
        self,
        settings: Settings,
        db: DatabaseSessionManager,
        bot: Bot,
        access_service: AccessService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.bot = bot
        self.access_service = access_service
        self._locks: dict[tuple[date, DigestPeriod], asyncio.Lock] = defaultdict(asyncio.Lock)

    async def ensure_digest(self, work_date: date, period: DigestPeriod) -> None:
        async with self._locks[(work_date, period)]:
            group_chat_id = await self.access_service.require_bound_group_id()
            async with self.db.session() as session:
                async with session.begin():
                    digest_repo = DigestRepository(session)
                    digest = await digest_repo.get_or_create(
                        work_date=work_date,
                        period=period,
                        group_chat_id=group_chat_id,
                    )

            text_value = await self._render_text(work_date, period)
            if digest.message_id is None:
                sent = await self.bot.send_message(chat_id=group_chat_id, text=text_value)
                async with self.db.session() as session:
                    async with session.begin():
                        digest_repo = DigestRepository(session)
                        digest = await digest_repo.get_or_create(work_date, period, group_chat_id)
                        await digest_repo.set_message_id(digest, sent.message_id)
                return

            await self._edit_message(group_chat_id, digest.message_id, text_value)

    async def refresh_digest(self, work_date: date, period: DigestPeriod) -> None:
        await self.ensure_digest(work_date, period)

    async def _render_text(self, work_date: date, period: DigestPeriod) -> str:
        async with self.db.session() as session:
            submission_repo = SubmissionRepository(session)
            submissions = await submission_repo.list_for_digest(
                work_date=work_date,
                only_pm_completed=period is DigestPeriod.PM,
            )
        if period is DigestPeriod.AM:
            return texts.render_am_digest(work_date, self.settings.hashtag, submissions)
        return texts.render_pm_digest(work_date, self.settings.hashtag, submissions)

    async def _edit_message(self, chat_id: int, message_id: int, text_value: str) -> None:
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text_value,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            raise
