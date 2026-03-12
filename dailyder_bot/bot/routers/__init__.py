from aiogram import Dispatcher

from dailyder_bot.bot.routers.admin import router as admin_router
from dailyder_bot.bot.routers.user import router as user_router


def register_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)
