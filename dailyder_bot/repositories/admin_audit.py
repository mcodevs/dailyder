from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import AdminAuditLog
from dailyder_bot.utils.ids import new_id


class AdminAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        admin_telegram_user_id: int,
        action: str,
        payload: dict | None,
        created_at: datetime,
    ) -> None:
        record = AdminAuditLog(
            id=new_id(),
            admin_telegram_user_id=admin_telegram_user_id,
            action=action,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
            created_at=created_at,
        )
        self.session.add(record)
        await self.session.flush()

