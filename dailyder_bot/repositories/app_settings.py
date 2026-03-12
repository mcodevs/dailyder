from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import AppSetting


class AppSettingsRepository:
    GROUP_CHAT_ID_KEY = "group_chat_id"
    GROUP_TITLE_KEY = "group_title"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> str | None:
        setting = await self.session.get(AppSetting, key)
        return setting.value if setting else None

    async def set(self, key: str, value: str) -> AppSetting:
        setting = await self.session.get(AppSetting, key)
        if setting is None:
            setting = AppSetting(key=key, value=value)
            self.session.add(setting)
        else:
            setting.value = value
        await self.session.flush()
        return setting

    async def get_group_chat_id(self) -> int | None:
        value = await self.get(self.GROUP_CHAT_ID_KEY)
        return int(value) if value else None

    async def set_group_binding(self, chat_id: int, title: str) -> None:
        await self.set(self.GROUP_CHAT_ID_KEY, str(chat_id))
        await self.set(self.GROUP_TITLE_KEY, title)

    async def get_group_title(self) -> str | None:
        return await self.get(self.GROUP_TITLE_KEY)

