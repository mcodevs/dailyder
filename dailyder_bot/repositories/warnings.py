from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dailyder_bot.db.models import DeveloperWarning
from dailyder_bot.utils.ids import new_id


class DeveloperWarningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        developer_user_id: str,
        admin_telegram_user_id: int,
        group_chat_id: int,
        reason: str,
        created_at: datetime,
    ) -> DeveloperWarning:
        warning = DeveloperWarning(
            id=new_id(),
            developer_user_id=developer_user_id,
            admin_telegram_user_id=admin_telegram_user_id,
            group_chat_id=group_chat_id,
            reason=reason.strip(),
            created_at=created_at,
            updated_at=created_at,
        )
        self.session.add(warning)
        await self.session.flush()
        result = await self.session.execute(
            select(DeveloperWarning)
            .where(DeveloperWarning.id == warning.id)
            .options(selectinload(DeveloperWarning.developer))
        )
        return result.scalar_one()

    async def list_for_window(self, start_at: datetime, end_at: datetime) -> list[DeveloperWarning]:
        result = await self.session.execute(
            select(DeveloperWarning)
            .where(
                DeveloperWarning.created_at >= start_at,
                DeveloperWarning.created_at < end_at,
            )
            .options(selectinload(DeveloperWarning.developer))
            .order_by(DeveloperWarning.created_at.asc())
        )
        return list(result.scalars().all())
