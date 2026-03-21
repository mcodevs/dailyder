from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import BotFlowSession
from dailyder_bot.utils.ids import new_id


class FlowSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: str, flow: str, work_date: date) -> BotFlowSession | None:
        result = await self.session.execute(
            select(BotFlowSession).where(
                BotFlowSession.user_id == user_id,
                BotFlowSession.flow == flow,
                BotFlowSession.work_date == work_date,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: str,
        flow: str,
        work_date: date,
        step: str,
        payload_json: str,
        expires_at: datetime,
        last_message_id: int | None = None,
    ) -> None:
        values = {
            "id": new_id(),
            "user_id": user_id,
            "flow": flow,
            "work_date": work_date,
            "step": step,
            "payload_json": payload_json,
            "last_message_id": last_message_id,
            "expires_at": expires_at,
        }
        update_values = {
            "step": step,
            "payload_json": payload_json,
            "last_message_id": last_message_id,
            "expires_at": expires_at,
            "updated_at": func.now(),
        }

        dialect_name = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect_name == "postgresql":
            stmt = pg_insert(BotFlowSession).values(**values).on_conflict_do_update(
                index_elements=[BotFlowSession.user_id, BotFlowSession.flow, BotFlowSession.work_date],
                set_=update_values,
            )
            await self.session.execute(stmt)
        elif dialect_name == "sqlite":
            stmt = sqlite_insert(BotFlowSession).values(**values).on_conflict_do_update(
                index_elements=[BotFlowSession.user_id, BotFlowSession.flow, BotFlowSession.work_date],
                set_=update_values,
            )
            await self.session.execute(stmt)
        else:
            session_state = await self.get(user_id, flow, work_date)
            if session_state is None:
                session_state = BotFlowSession(
                    **values,
                )
                self.session.add(session_state)
            else:
                session_state.step = step
                session_state.payload_json = payload_json
                session_state.expires_at = expires_at
                session_state.last_message_id = last_message_id
            await self.session.flush()

    async def delete(self, user_id: str, flow: str, work_date: date) -> None:
        session_state = await self.get(user_id, flow, work_date)
        if session_state is None:
            return
        await self.session.delete(session_state)
        await self.session.flush()
