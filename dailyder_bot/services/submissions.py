from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from dailyder_bot.config.settings import Settings
from dailyder_bot.db.models import DailySubmission
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.domain.parser import MorningSubmissionParser
from dailyder_bot.repositories.submissions import SubmissionRepository
from dailyder_bot.repositories.users import UserRepository


@dataclass(slots=True)
class DraftMutationResult:
    submission: DailySubmission
    pm_reset: bool


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

    async def get_submitted_today_submission(self, telegram_user_id: int, work_date: date) -> DailySubmission | None:
        submission = await self.get_today_submission(telegram_user_id, work_date)
        if submission is None or submission.am_submitted_at is None:
            return None
        return submission

    async def get_today_submission_map(
        self,
        telegram_user_ids: Sequence[int],
        work_date: date,
    ) -> dict[int, DailySubmission]:
        if not telegram_user_ids:
            return {}

        async with self.db.session() as session:
            repo = SubmissionRepository(session)
            submissions = await repo.list_by_telegram_users_and_date(telegram_user_ids, work_date)
        return {submission.user.telegram_user_id: submission for submission in submissions}

    async def get_or_create_today_draft(self, telegram_user_id: int, work_date: date) -> DailySubmission:
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_or_create_draft(
                    user_id=user.id,
                    work_date=work_date,
                    hashtag=self.settings.hashtag,
                )
            return submission

    async def add_draft_item(
        self,
        *,
        telegram_user_id: int,
        work_date: date,
        project_name: str,
        task_name: str,
        subtask_names: list[str],
    ) -> DraftMutationResult:
        self._validate_task_fields(project_name, task_name)
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_or_create_draft(
                    user_id=user.id,
                    work_date=work_date,
                    hashtag=self.settings.hashtag,
                )
                pm_reset = await submission_repo.reset_pm_update(submission_id=submission.id)
                submission = await submission_repo.add_item(
                    submission_id=submission.id,
                    project_name=project_name,
                    task_name=task_name,
                    subtask_names=subtask_names,
                )
            return DraftMutationResult(submission=submission, pm_reset=pm_reset)

    async def update_draft_item(
        self,
        *,
        telegram_user_id: int,
        work_date: date,
        item_id: str,
        project_name: str,
        task_name: str,
        subtask_names: list[str],
    ) -> DraftMutationResult:
        self._validate_task_fields(project_name, task_name)
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_by_user_and_date(user.id, work_date)
                if submission is None:
                    raise ValueError("Bugun uchun tasklar topilmadi.")
                pm_reset = await submission_repo.reset_pm_update(submission_id=submission.id)
                submission = await submission_repo.update_item(
                    submission_id=submission.id,
                    item_id=item_id,
                    project_name=project_name,
                    task_name=task_name,
                    subtask_names=subtask_names,
                )
            return DraftMutationResult(submission=submission, pm_reset=pm_reset)

    async def delete_draft_item(
        self,
        *,
        telegram_user_id: int,
        work_date: date,
        item_id: str,
    ) -> DraftMutationResult:
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_by_user_and_date(user.id, work_date)
                if submission is None:
                    raise ValueError("Bugun uchun tasklar topilmadi.")
                pm_reset = await submission_repo.reset_pm_update(submission_id=submission.id)
                submission = await submission_repo.delete_item(
                    submission_id=submission.id,
                    item_id=item_id,
                )
            return DraftMutationResult(submission=submission, pm_reset=pm_reset)

    async def import_draft_from_text(
        self,
        *,
        telegram_user_id: int,
        raw_text: str,
        work_date: date,
    ) -> DraftMutationResult:
        parsed = self.parser.parse(raw_text)
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_or_create_draft(
                    user_id=user.id,
                    work_date=work_date,
                    hashtag=self.settings.hashtag,
                )
                pm_reset = await submission_repo.reset_pm_update(submission_id=submission.id)
                submission = await submission_repo.replace_items(
                    submission_id=submission.id,
                    parsed_submission=parsed,
                )
            return DraftMutationResult(submission=submission, pm_reset=pm_reset)

    async def submit_morning(
        self,
        telegram_user_id: int,
        raw_text: str,
        work_date: date,
        submitted_at: datetime,
    ) -> DailySubmission:
        await self.import_draft_from_text(
            telegram_user_id=telegram_user_id,
            raw_text=raw_text,
            work_date=work_date,
        )
        return await self.submit_morning_draft(
            telegram_user_id=telegram_user_id,
            work_date=work_date,
            submitted_at=submitted_at,
        )

    async def submit_morning_draft(
        self,
        *,
        telegram_user_id: int,
        work_date: date,
        submitted_at: datetime,
    ) -> DailySubmission:
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_by_user_and_date(user.id, work_date)
                if submission is None or not submission.items:
                    raise ValueError("Avval kamida bitta task kiriting.")
                submission = await submission_repo.submit_draft(
                    submission_id=submission.id,
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
                if submission is None or submission.am_submitted_at is None:
                    raise ValueError("Bugun uchun ertalabgi vazifalar topilmadi.")
                submission = await submission_repo.record_pm_statuses(
                    submission_id=submission.id,
                    status_map=status_map,
                    final_note=final_note,
                    submitted_at=submitted_at,
                )
            return submission

    async def record_subtask_status(
        self,
        *,
        telegram_user_id: int,
        work_date: date,
        item_id: str,
        subtask_id: str,
        status: ItemStatus | None,
    ) -> DailySubmission:
        async with self.db.session() as session:
            async with session.begin():
                user = await self._require_user(session, telegram_user_id)
                submission_repo = SubmissionRepository(session)
                submission = await submission_repo.get_by_user_and_date(user.id, work_date)
                if submission is None:
                    raise ValueError("Bugun uchun tasklar topilmadi.")
                submission = await submission_repo.set_subtask_status(
                    submission_id=submission.id,
                    item_id=item_id,
                    subtask_id=subtask_id,
                    status=status,
                )
            return submission

    async def _require_user(self, session, telegram_user_id: int):
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_user_id)
        if user is None:
            raise ValueError("Avval /start yuborib onboardingni yakunlang.")
        return user

    @staticmethod
    def _validate_task_fields(project_name: str, task_name: str) -> None:
        if not project_name.strip():
            raise ValueError("Project nomi bo'sh bo'lmasligi kerak.")
        if not task_name.strip():
            raise ValueError("Task nomi bo'sh bo'lmasligi kerak.")
