from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from dailyder_bot.config.settings import Settings
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.repositories.app_settings import AppSettingsRepository, GroupBinding


class GroupBindingError(RuntimeError):
    pass


class MembershipError(RuntimeError):
    pass


class AccessService:
    ACTIVE_MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}

    def __init__(self, settings: Settings, db: DatabaseSessionManager) -> None:
        self.settings = settings
        self.db = db

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self.settings.admin_user_ids

    async def get_group_binding(self) -> GroupBinding | None:
        async with self.db.session() as session:
            repo = AppSettingsRepository(session)
            binding = await repo.get_group_binding()
            if binding is not None:
                return binding
        if self.settings.group_chat_id is None:
            return None
        return GroupBinding(chat_id=self.settings.group_chat_id, title=None, message_thread_id=None)

    async def get_bound_group_id(self) -> int | None:
        binding = await self.get_group_binding()
        return binding.chat_id if binding is not None else None

    async def require_group_binding(self) -> GroupBinding:
        binding = await self.get_group_binding()
        if binding is None:
            raise GroupBindingError("Guruh hali biriktirilmagan.")
        return binding

    async def require_bound_group_id(self) -> int:
        return (await self.require_group_binding()).chat_id

    async def ensure_group_member(self, bot: Bot, telegram_user_id: int) -> int:
        group_chat_id = await self.require_bound_group_id()
        if not await self.is_group_member(bot, group_chat_id, telegram_user_id):
            raise MembershipError("Siz maqsadli guruh a'zosi emassiz.")
        return group_chat_id

    async def is_group_member(self, bot: Bot, group_chat_id: int, telegram_user_id: int) -> bool:
        try:
            member = await bot.get_chat_member(chat_id=group_chat_id, user_id=telegram_user_id)
        except TelegramBadRequest:
            return False
        return member.status in self.ACTIVE_MEMBER_STATUSES
