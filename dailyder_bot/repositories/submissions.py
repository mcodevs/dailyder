from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dailyder_bot.db.models import DailySubmission, SubmissionItem, SubmissionItemStatus
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.domain.parser import ParsedMorningSubmission
from dailyder_bot.utils.ids import new_id


class SubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_and_date(self, user_id: str, work_date: date) -> DailySubmission | None:
        result = await self.session.execute(
            select(DailySubmission)
            .where(
                DailySubmission.user_id == user_id,
                DailySubmission.work_date == work_date,
            )
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.subtasks),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.status),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_user_and_date(
        self,
        telegram_user_id: int,
        work_date: date,
    ) -> DailySubmission | None:
        from dailyder_bot.db.models import User

        result = await self.session.execute(
            select(DailySubmission)
            .join(User)
            .where(
                User.telegram_user_id == telegram_user_id,
                DailySubmission.work_date == work_date,
            )
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.subtasks),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.status),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_telegram_users_and_date(
        self,
        telegram_user_ids: Sequence[int],
        work_date: date,
    ) -> list[DailySubmission]:
        if not telegram_user_ids:
            return []

        from dailyder_bot.db.models import User

        result = await self.session.execute(
            select(DailySubmission)
            .join(User)
            .where(
                User.telegram_user_id.in_(telegram_user_ids),
                DailySubmission.work_date == work_date,
            )
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.subtasks),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.status),
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, submission_id: str) -> DailySubmission | None:
        result = await self.session.execute(
            select(DailySubmission)
            .where(DailySubmission.id == submission_id)
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.subtasks),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.status),
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_draft(
        self,
        *,
        user_id: str,
        work_date: date,
        hashtag: str,
    ) -> DailySubmission:
        submission = await self.get_by_user_and_date(user_id, work_date)
        if submission is None:
            submission = DailySubmission(
                id=new_id(),
                user_id=user_id,
                work_date=work_date,
                hashtag=hashtag,
            )
            self.session.add(submission)
            await self.session.flush()
            return await self.get_by_id(submission.id)  # type: ignore[return-value]

        if not submission.hashtag:
            submission.hashtag = hashtag
            await self.session.flush()
        return submission

    async def add_item(
        self,
        *,
        submission_id: str,
        project_name: str,
        task_name: str,
        subtask_names: list[str],
    ) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        persisted_submission_id = submission.id

        submission_item = SubmissionItem(
            id=new_id(),
            submission_id=persisted_submission_id,
            sort_order=len(submission.items) + 1,
            project_name=project_name.strip(),
            task_name=task_name.strip(),
        )
        submission_item.subtask_names = subtask_names
        self.session.add(submission_item)
        await self.session.flush()
        self.session.expire_all()
        return await self.get_by_id(persisted_submission_id)  # type: ignore[return-value]

    async def update_item(
        self,
        *,
        submission_id: str,
        item_id: str,
        project_name: str,
        task_name: str,
        subtask_names: list[str],
    ) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        persisted_submission_id = submission.id

        item = next((entry for entry in submission.items if entry.id == item_id), None)
        if item is None:
            raise ValueError("Task topilmadi.")

        item.project_name = project_name.strip()
        item.task_name = task_name.strip()
        if item.subtasks:
            item.subtasks.clear()
            await self.session.flush()
        item.subtask_names = subtask_names
        await self.session.flush()
        self.session.expire_all()
        return await self.get_by_id(persisted_submission_id)  # type: ignore[return-value]

    async def delete_item(self, *, submission_id: str, item_id: str) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        persisted_submission_id = submission.id

        item = next((entry for entry in submission.items if entry.id == item_id), None)
        if item is None:
            raise ValueError("Task topilmadi.")

        await self.session.delete(item)
        await self.session.flush()

        refreshed = await self.get_by_id(persisted_submission_id)
        if refreshed is None:
            raise ValueError("Submission topilmadi.")

        for index, entry in enumerate(refreshed.items, start=1):
            entry.sort_order = index
        await self.session.flush()
        self.session.expire_all()
        return await self.get_by_id(persisted_submission_id)  # type: ignore[return-value]

    async def replace_items(
        self,
        *,
        submission_id: str,
        parsed_submission: ParsedMorningSubmission,
    ) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        persisted_submission_id = submission.id

        await self._delete_item_statuses(persisted_submission_id)
        await self._delete_items(persisted_submission_id)
        submission.final_note = None
        submission.pm_submitted_at = None

        for sort_order, item in enumerate(parsed_submission.items, start=1):
            submission_item = SubmissionItem(
                id=new_id(),
                submission_id=persisted_submission_id,
                sort_order=sort_order,
                project_name=item.project_name,
                task_name=item.task_name,
            )
            submission_item.subtask_names = item.subtask_names
            self.session.add(submission_item)

        await self.session.flush()
        self.session.expire_all()
        return await self.get_by_id(persisted_submission_id)  # type: ignore[return-value]

    async def submit_draft(self, *, submission_id: str, submitted_at: datetime) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        submission.am_submitted_at = submitted_at
        await self.session.flush()
        return submission

    async def reset_pm_update(self, *, submission_id: str) -> bool:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")

        if submission.pm_submitted_at is None and submission.final_note is None and not any(
            item.status is not None or any(subtask.status is not None for subtask in item.subtasks)
            for item in submission.items
        ):
            return False

        await self._delete_item_statuses(submission.id)
        for item in submission.items:
            for subtask in item.subtasks:
                subtask.status = None
        submission.pm_submitted_at = None
        submission.final_note = None
        await self.session.flush()
        return True

    async def upsert_morning_submission(
        self,
        user_id: str,
        work_date: date,
        hashtag: str,
        parsed_submission: ParsedMorningSubmission,
        submitted_at: datetime,
    ) -> DailySubmission:
        submission = await self.get_or_create_draft(user_id=user_id, work_date=work_date, hashtag=hashtag)
        submission = await self.replace_items(
            submission_id=submission.id,
            parsed_submission=parsed_submission,
        )
        return await self.submit_draft(submission_id=submission.id, submitted_at=submitted_at)

    async def record_pm_statuses(
        self,
        submission_id: str,
        status_map: dict[str, ItemStatus],
        final_note: str | None,
        submitted_at: datetime,
    ) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        persisted_submission_id = submission.id

        item_lookup = {item.id: item for item in submission.items}
        if set(item_lookup) != set(status_map):
            raise ValueError("Har bir vazifa uchun status yuborilishi kerak.")

        for item_id, status in status_map.items():
            item = item_lookup[item_id]
            if item.status is None:
                self.session.add(
                    SubmissionItemStatus(
                        id=new_id(),
                        submission_item_id=item.id,
                        status=status.value,
                    )
                )
            else:
                item.status.status = status.value

        submission.final_note = final_note.strip() if final_note else None
        submission.pm_submitted_at = submitted_at
        await self.session.flush()
        self.session.expire_all()
        return await self.get_by_id(persisted_submission_id)  # type: ignore[return-value]

    async def list_for_digest(self, work_date: date, only_pm_completed: bool) -> list[DailySubmission]:
        query = (
            select(DailySubmission)
            .where(DailySubmission.work_date == work_date)
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.subtasks),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.status),
            )
            .order_by(
                DailySubmission.pm_submitted_at.asc() if only_pm_completed else DailySubmission.am_submitted_at.asc()
            )
        )
        if only_pm_completed:
            query = query.where(DailySubmission.pm_submitted_at.is_not(None))
        else:
            query = query.where(DailySubmission.am_submitted_at.is_not(None))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_for_window(self, start_date: date, end_date: date) -> list[DailySubmission]:
        result = await self.session.execute(
            select(DailySubmission)
            .where(
                DailySubmission.work_date >= start_date,
                DailySubmission.work_date <= end_date,
            )
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.subtasks),
                selectinload(DailySubmission.items)
                .selectinload(SubmissionItem.status),
            )
            .order_by(DailySubmission.work_date.asc(), DailySubmission.am_submitted_at.asc())
        )
        return list(result.scalars().all())

    async def cleanup_older_than(self, cutoff_date: date) -> int:
        result = await self.session.execute(
            select(DailySubmission).where(DailySubmission.work_date < cutoff_date)
        )
        stale_records = list(result.scalars().all())
        for record in stale_records:
            await self.session.delete(record)
        await self.session.flush()
        return len(stale_records)

    async def _delete_item_statuses(self, submission_id: str) -> None:
        await self.session.execute(
            delete(SubmissionItemStatus).where(
                SubmissionItemStatus.submission_item_id.in_(
                    select(SubmissionItem.id).where(SubmissionItem.submission_id == submission_id)
                )
            )
        )

    async def _delete_items(self, submission_id: str) -> None:
        await self.session.execute(
            delete(SubmissionItem).where(SubmissionItem.submission_id == submission_id)
        )

    async def set_subtask_status(
        self,
        *,
        submission_id: str,
        item_id: str,
        subtask_id: str,
        status: ItemStatus | None,
    ) -> DailySubmission:
        submission = await self.get_by_id(submission_id)
        if submission is None:
            raise ValueError("Submission topilmadi.")
        persisted_submission_id = submission.id

        item = next((entry for entry in submission.items if entry.id == item_id), None)
        if item is None:
            raise ValueError("Task topilmadi.")

        subtask = next((entry for entry in item.subtasks if entry.id == subtask_id), None)
        if subtask is None:
            raise ValueError("Subtask topilmadi.")

        subtask.status = status.value if status is not None else None
        await self.session.flush()
        self.session.expire_all()
        return await self.get_by_id(persisted_submission_id)  # type: ignore[return-value]
