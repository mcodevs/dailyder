from __future__ import annotations

from datetime import date, datetime

from dailyder_bot.config.settings import Settings
from dailyder_bot.db.models import DailySubmission
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.domain.parser import MorningSubmissionParser
from dailyder_bot.repositories.submissions import SubmissionRepository
from dailyder_bot.repositories.users import UserRepository


class SubmissionService:
    def __init__(
        self,
        settings: Settings,
        db: DatabaseSessionManager,
        parser: MorningSubmissionParser,
    ) -> None:
        self.settings = settings
        self.db = db
        self.parser = parser

    async def get_today_submission(self, telegram_user_id: int, work_date: date) -> DailySubmission | None:
        async with self.db.session() as session:
            repo = SubmissionRepository(session)
            return await repo.get_by_telegram_user_and_date(telegram_user_id, work_date)

    async def submit_morning(
        self,
        telegram_user_id: int,
        raw_text: str,
        work_date: date,
        submitted_at: datetime,
    ) -> DailySubmission:
        parsed = self.parser.parse(raw_text)
        async with self.db.session() as session:
            async with session.begin():
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(telegram_user_id)
                if user is None:
                    raise ValueError("Avval /start buyrug'ini yuboring.")

                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.upsert_morning_submission(
                    user_id=user.id,
                    work_date=work_date,
                    hashtag=self.settings.hashtag,
                    parsed_submission=parsed,
                    submitted_at=submitted_at,
                )
            return submission

    async def record_pm_statuses(
        self,
        telegram_user_id: int,
        work_date: date,
        status_map: dict[str, ItemStatus],
        final_note: str | None,
        submitted_at: datetime,
    ) -> DailySubmission:
        async with self.db.session() as session:
            async with session.begin():
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_by_telegram_user_and_date(telegram_user_id, work_date)
                if submission is None:
                    raise ValueError("Bugun uchun ertalabgi vazifalar topilmadi.")
                submission = await submission_repo.record_pm_statuses(
                    submission_id=submission.id,
                    status_map=status_map,
                    final_note=final_note,
                    submitted_at=submitted_at,
                )
            return submission

