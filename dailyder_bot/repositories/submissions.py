from __future__ import annotations

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
                selectinload(DailySubmission.items).selectinload(SubmissionItem.status)
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
                selectinload(DailySubmission.items).selectinload(SubmissionItem.status),
            )
        )
        return result.scalar_one_or_none()

    async def upsert_morning_submission(
        self,
        user_id: str,
        work_date: date,
        hashtag: str,
        parsed_submission: ParsedMorningSubmission,
        submitted_at: datetime,
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
        else:
            await self.session.execute(
                delete(SubmissionItemStatus).where(
                    SubmissionItemStatus.submission_item_id.in_(
                        select(SubmissionItem.id).where(SubmissionItem.submission_id == submission.id)
                    )
                )
            )
            await self.session.execute(
                delete(SubmissionItem).where(SubmissionItem.submission_id == submission.id)
            )
            submission.final_note = None
            submission.pm_submitted_at = None

        submission.hashtag = hashtag
        submission.am_submitted_at = submitted_at

        for sort_order, item in enumerate(parsed_submission.items, start=1):
            submission_item = SubmissionItem(
                id=new_id(),
                submission_id=submission.id,
                sort_order=sort_order,
                project_name=item.project_name,
                task_name=item.task_name,
            )
            submission_item.subtask_names = item.subtask_names
            self.session.add(submission_item)

        await self.session.flush()
        return await self.get_by_user_and_date(user_id, work_date)  # type: ignore[return-value]

    async def record_pm_statuses(
        self,
        submission_id: str,
        status_map: dict[str, ItemStatus],
        final_note: str | None,
        submitted_at: datetime,
    ) -> DailySubmission:
        result = await self.session.execute(
            select(DailySubmission)
            .where(DailySubmission.id == submission_id)
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items).selectinload(SubmissionItem.status),
            )
        )
        submission = result.scalar_one()

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
        return submission

    async def list_for_digest(self, work_date: date, only_pm_completed: bool) -> list[DailySubmission]:
        query = (
            select(DailySubmission)
            .where(DailySubmission.work_date == work_date)
            .options(
                selectinload(DailySubmission.user),
                selectinload(DailySubmission.items).selectinload(SubmissionItem.status),
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
                selectinload(DailySubmission.items).selectinload(SubmissionItem.status),
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
