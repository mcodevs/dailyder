from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from dailyder_bot.bot.callbacks import ActionCallback, ItemStatusCallback
from dailyder_bot.domain.enums import ItemStatus


def morning_shortcuts() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Bugungi vazifani yuborish",
                    callback_data=ActionCallback(name="today").pack(),
                )
            ]
        ]
    )


def pm_shortcuts(*, has_submission: bool) -> InlineKeyboardMarkup:
    action = "update" if has_submission else "today"
    label = "Statuslarni yangilash" if has_submission else "Avval vazifani yuborish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=ActionCallback(name=action).pack(),
                )
            ]
        ]
    )


def status_keyboard(item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{ItemStatus.COMPLETED.emoji} Bajarildi",
                    callback_data=ItemStatusCallback(item_id=item_id, status=ItemStatus.COMPLETED.value).pack(),
                ),
                InlineKeyboardButton(
                    text=f"{ItemStatus.WARNING.emoji} Xavf bor",
                    callback_data=ItemStatusCallback(item_id=item_id, status=ItemStatus.WARNING.value).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{ItemStatus.BLOCKED.emoji} To'siq bor",
                    callback_data=ItemStatusCallback(item_id=item_id, status=ItemStatus.BLOCKED.value).pack(),
                ),
                InlineKeyboardButton(
                    text=f"{ItemStatus.DROPPED.emoji} Bekor qilindi",
                    callback_data=ItemStatusCallback(item_id=item_id, status=ItemStatus.DROPPED.value).pack(),
                ),
            ],
        ]
    )


def skip_note_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Izohsiz yakunlash",
                    callback_data=ActionCallback(name="skip_note").pack(),
                )
            ]
        ]
    )


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Holat",
                    callback_data=ActionCallback(name="admin_readiness").pack(),
                ),
                InlineKeyboardButton(
                    text="Pending",
                    callback_data=ActionCallback(name="admin_pending").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Metrikalar",
                    callback_data=ActionCallback(name="admin_metrics").pack(),
                ),
                InlineKeyboardButton(
                    text="Developerlar",
                    callback_data=ActionCallback(name="admin_users").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="AM eslatma",
                    callback_data=ActionCallback(name="admin_remind_am").pack(),
                ),
                InlineKeyboardButton(
                    text="PM eslatma",
                    callback_data=ActionCallback(name="admin_remind_pm").pack(),
                ),
            ],
        ]
    )

