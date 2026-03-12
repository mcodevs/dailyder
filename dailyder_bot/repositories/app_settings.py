from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from dailyder_bot.db.models import AppSetting


@dataclass(slots=True)
class GroupBinding:
    chat_id: int
    title: str | None = None
    message_thread_id: int | None = None


class AppSettingsRepository:
    GROUP_CHAT_ID_KEY = "group_chat_id"
    GROUP_TITLE_KEY = "group_title"
    GROUP_MESSAGE_THREAD_ID_KEY = "group_message_thread_id"

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

    async def get_group_message_thread_id(self) -> int | None:
        value = await self.get(self.GROUP_MESSAGE_THREAD_ID_KEY)
        return int(value) if value else None

    async def get_group_binding(self) -> GroupBinding | None:
        chat_id = await self.get_group_chat_id()
        if chat_id is None:
            return None
        return GroupBinding(
            chat_id=chat_id,
            title=await self.get_group_title(),
            message_thread_id=await self.get_group_message_thread_id(),
        )

    async def set_group_binding(
        self,
        chat_id: int,
        title: str,
        message_thread_id: int | None = None,
    ) -> None:
        await self.set(self.GROUP_CHAT_ID_KEY, str(chat_id))
        await self.set(self.GROUP_TITLE_KEY, title)
        if message_thread_id is None:
            existing = await self.session.get(AppSetting, self.GROUP_MESSAGE_THREAD_ID_KEY)
            if existing is not None:
                await self.session.delete(existing)
                await self.session.flush()
        else:
            await self.set(self.GROUP_MESSAGE_THREAD_ID_KEY, str(message_thread_id))

    async def get_group_title(self) -> str | None:
        return await self.get(self.GROUP_TITLE_KEY)
