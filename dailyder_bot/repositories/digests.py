from __future__ import annotations

from datetime import date

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import DailyDigest
from dailyder_bot.domain.enums import DigestPeriod
from dailyder_bot.utils.ids import new_id


class DigestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_date_period(self, work_date: date, period: DigestPeriod) -> DailyDigest | None:
        result = await self.session.execute(
            select(DailyDigest).where(
                DailyDigest.work_date == work_date,
                DailyDigest.period == period.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        work_date: date,
        period: DigestPeriod,
        group_chat_id: int,
    ) -> DailyDigest:
        digest = await self.get_by_date_period(work_date, period)
        if digest is None:
            digest = DailyDigest(
                id=new_id(),
                work_date=work_date,
                period=period.value,
                group_chat_id=group_chat_id,
            )
            self.session.add(digest)
            await self.session.flush()
        return digest

    async def set_message_id(self, digest: DailyDigest, message_id: int) -> None:
        digest.message_id = message_id
        await self.session.flush()

    async def cleanup_older_than(self, cutoff_date: date) -> int:
        result = await self.session.execute(
            select(DailyDigest).where(DailyDigest.work_date < cutoff_date)
        )
        stale_records = list(result.scalars().all())
        if not stale_records:
            return 0
        await self.session.execute(delete(DailyDigest).where(DailyDigest.work_date < cutoff_date))
        await self.session.flush()
        return len(stale_records)
