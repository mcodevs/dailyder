from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    action: str


class DraftActionCallback(CallbackData, prefix="draft_action"):
    action: str


class DraftItemCallback(CallbackData, prefix="draft_item"):
    action: str
    item_id: str


class DraftConfirmCallback(CallbackData, prefix="draft_confirm"):
    action: str
    decision: str


class PmActionCallback(CallbackData, prefix="pm_action"):
    action: str


class PmItemCallback(CallbackData, prefix="pm_item"):
    action: str
    item_id: str


class PmTargetCallback(CallbackData, prefix="pm_target"):
    target_type: str
    target_id: str


class PmStatusCallback(CallbackData, prefix="pm_status"):
    target_type: str
    target_id: str
    status: str


class AdminActionCallback(CallbackData, prefix="admin_action"):
    action: str
