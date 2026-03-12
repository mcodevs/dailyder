from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class ActionCallback(CallbackData, prefix="action"):
    name: str


class ItemStatusCallback(CallbackData, prefix="item_status"):
    item_id: str
    status: str

