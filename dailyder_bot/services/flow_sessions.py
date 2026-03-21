from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.repositories.flow_sessions import FlowSessionRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FlowSessionState:
    flow: str
    work_date: date
    step: str
    payload: dict[str, Any]
    last_message_id: int | None
    expires_at: datetime


class FlowSessionService:
    SESSION_TTL = timedelta(hours=12)

    def __init__(self, db: DatabaseSessionManager) -> None:
        self.db = db

    async def get(self, *, user_id: str, flow: str, work_date: date, now: datetime) -> FlowSessionState | None:
        async with self.db.session() as session:
            repo = FlowSessionRepository(session)
            session_state = await repo.get(user_id, flow, work_date)
            if session_state is None:
                return None
            expires_at = self._normalize_datetime(session_state.expires_at)
            if expires_at <= now:
                await repo.delete(user_id, flow, work_date)
                logger.info("Expired flow session cleared", extra={"flow": flow, "user_id": user_id})
                return None
            return FlowSessionState(
                flow=session_state.flow,
                work_date=session_state.work_date,
                step=session_state.step,
                payload=json.loads(session_state.payload_json),
                last_message_id=session_state.last_message_id,
                expires_at=expires_at,
            )

    async def set(
        self,
        *,
        user_id: str,
        flow: str,
        work_date: date,
        step: str,
        payload: dict[str, Any],
        now: datetime,
        last_message_id: int | None = None,
    ) -> FlowSessionState:
        expires_at = now + self.SESSION_TTL
        async with self.db.session() as session:
            async with session.begin():
                repo = FlowSessionRepository(session)
                await repo.upsert(
                    user_id=user_id,
                    flow=flow,
                    work_date=work_date,
                    step=step,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                    expires_at=expires_at,
                    last_message_id=last_message_id,
                )
        logger.info("Flow session saved", extra={"flow": flow, "step": step, "user_id": user_id})
        return FlowSessionState(
            flow=flow,
            work_date=work_date,
            step=step,
            payload=payload,
            last_message_id=last_message_id,
            expires_at=expires_at,
        )

    async def clear(self, *, user_id: str, flow: str, work_date: date) -> None:
        async with self.db.session() as session:
            async with session.begin():
                repo = FlowSessionRepository(session)
                await repo.delete(user_id, flow, work_date)
        logger.info("Flow session cleared", extra={"flow": flow, "user_id": user_id})

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
