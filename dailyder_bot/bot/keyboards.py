from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from dailyder_bot.bot.callbacks import (
    AdminActionCallback,
    DraftActionCallback,
    DraftConfirmCallback,
    DraftItemCallback,
    MenuCallback,
    PmActionCallback,
    PmItemCallback,
    PmStatusCallback,
    PmTargetCallback,
)
from dailyder_bot.db.models import SubmissionItem
from dailyder_bot.domain.enums import ItemStatus

MENU_TODAY = "Bugungi tasklar"
MENU_PM = "PM update"
MENU_HELP = "Yordam"
MENU_ADMIN = "Admin panel"
MENU_HOME = "Bosh menyu"


def _main_menu_rows(*, is_admin: bool) -> list[list[InlineKeyboardButton]]:
    rows = [
        [
            InlineKeyboardButton(
                text=MENU_TODAY,
                callback_data=MenuCallback(action="today").pack(),
            ),
            InlineKeyboardButton(
                text=MENU_PM,
                callback_data=MenuCallback(action="pm").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=MENU_HELP,
                callback_data=MenuCallback(action="help").pack(),
            )
        ],
    ]
    if is_admin:
        rows.append(
            [
                InlineKeyboardButton(
                    text=MENU_ADMIN,
                    callback_data=MenuCallback(action="admin").pack(),
                )
            ]
        )
    return rows


def main_menu_keyboard(*, is_admin: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_main_menu_rows(is_admin=is_admin))


def with_main_menu(
    reply_markup: InlineKeyboardMarkup | None,
    *,
    is_admin: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if reply_markup is not None:
        rows.extend(reply_markup.inline_keyboard)
    rows.extend(_main_menu_rows(is_admin=is_admin))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def morning_shortcuts() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Bugungi vazifani yuborish",
                    callback_data=MenuCallback(action="today").pack(),
                )
            ]
        ]
    )


def pm_shortcuts(*, has_submission: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Statuslarni yangilash" if has_submission else "Avval vazifani yuborish",
                    callback_data=MenuCallback(action="pm" if has_submission else "today").pack(),
                )
            ]
        ]
    )


def today_summary_keyboard(*, has_items: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="Task qo'shish",
                callback_data=DraftActionCallback(action="start_add").pack(),
            ),
            InlineKeyboardButton(
                text="Matndan import",
                callback_data=DraftActionCallback(action="start_import").pack(),
            ),
        ]
    ]
    if has_items:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Taskni tahrirlash",
                    callback_data=DraftActionCallback(action="pick_edit").pack(),
                ),
                InlineKeyboardButton(
                    text="Taskni o'chirish",
                    callback_data=DraftActionCallback(action="pick_delete").pack(),
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Yuborish",
                    callback_data=DraftActionCallback(action="submit").pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def project_picker_keyboard(project_choices: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=DraftItemCallback(action="select_project", item_id=item_id).pack(),
            )
        ]
        for label, item_id in project_choices
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Yangi project",
                callback_data=DraftActionCallback(action="new_project").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subtask_builder_keyboard(*, has_subtasks: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Subtask qo'shish",
                callback_data=DraftActionCallback(action="add_subtask").pack(),
            )
        ]
    ]
    if has_subtasks:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Subtasklarni tozalash",
                    callback_data=DraftActionCallback(action="clear_subtasks").pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Saqlash",
                callback_data=DraftActionCallback(action="save_item").pack(),
            ),
            InlineKeyboardButton(
                text="Bekor qilish",
                callback_data=DraftActionCallback(action="cancel_flow").pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_picker_keyboard(items: list[SubmissionItem], *, action: str, back_action: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{index}. {item.project_name} — {item.task_name}",
                callback_data=DraftItemCallback(action=action, item_id=item.id).pack(),
            )
        ]
        for index, item in enumerate(items, start=1)
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Orqaga",
                callback_data=DraftActionCallback(action=back_action).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def draft_confirm_keyboard(*, action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Tasdiqlash",
                    callback_data=DraftConfirmCallback(action=action, decision="yes").pack(),
                ),
                InlineKeyboardButton(
                    text="Bekor qilish",
                    callback_data=DraftConfirmCallback(action=action, decision="no").pack(),
                ),
            ]
        ]
    )


def draft_resume_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Davom etish",
                    callback_data=DraftActionCallback(action="resume").pack(),
                ),
                InlineKeyboardButton(
                    text="Qaytadan boshlash",
                    callback_data=DraftActionCallback(action="restart").pack(),
                ),
            ],
        ]
    )


def pm_summary_keyboard(
    *,
    items: list[SubmissionItem],
    status_map: dict[str, str],
) -> InlineKeyboardMarkup:
    rows = []
    for index, item in enumerate(items, start=1):
        status_value = status_map.get(item.id)
        emoji = ItemStatus(status_value).emoji if status_value else "◻️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emoji} {index}. {item.task_name}",
                    callback_data=PmItemCallback(action="select_item", item_id=item.id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Yakuniy izoh",
                callback_data=PmActionCallback(action="edit_note").pack(),
            ),
            InlineKeyboardButton(
                text="Yakunlash",
                callback_data=PmActionCallback(action="submit").pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pm_item_detail_keyboard(
    *,
    item: SubmissionItem,
    current_status: str | None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{ItemStatus(current_status).emoji if current_status else '◻️'} Task status",
                callback_data=PmTargetCallback(
                    target_type="item",
                    target_id=item.id,
                ).pack(),
            )
        ]
    ]
    for subtask in item.subtasks:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{ItemStatus(subtask.status).emoji if subtask.status else '◻️'} {subtask.subtask_name}",
                    callback_data=PmTargetCallback(
                        target_type="subtask",
                        target_id=subtask.id,
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Orqaga",
                callback_data=PmActionCallback(action="back_to_summary").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pm_status_keyboard(*, target_type: str, target_id: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{status.emoji} {status.label_uz}",
                callback_data=PmStatusCallback(
                    target_type=target_type,
                    target_id=target_id,
                    status=status.value,
                ).pack(),
            )
        ]
        for status in ItemStatus
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Orqaga",
                callback_data=PmActionCallback(action="back_to_summary").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pm_note_keyboard(*, has_note: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Izohsiz qoldirish",
                callback_data=PmActionCallback(action="skip_note").pack(),
            ),
            InlineKeyboardButton(
                text="Orqaga",
                callback_data=PmActionCallback(action="back_to_summary").pack(),
            ),
        ]
    ]
    if has_note:
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    text="Izohni tozalash",
                    callback_data=PmActionCallback(action="clear_note").pack(),
                )
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pm_resume_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Davom etish",
                    callback_data=PmActionCallback(action="resume").pack(),
                ),
                InlineKeyboardButton(
                    text="Qaytadan boshlash",
                    callback_data=PmActionCallback(action="restart").pack(),
                ),
            ],
        ]
    )


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return with_main_menu(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Holat",
                        callback_data=AdminActionCallback(action="readiness").pack(),
                    ),
                    InlineKeyboardButton(
                        text="Pending",
                        callback_data=AdminActionCallback(action="pending").pack(),
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="Metrikalar",
                        callback_data=AdminActionCallback(action="metrics").pack(),
                    ),
                    InlineKeyboardButton(
                        text="Developerlar",
                        callback_data=AdminActionCallback(action="users").pack(),
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="AM eslatma",
                        callback_data=AdminActionCallback(action="remind_am").pack(),
                    ),
                    InlineKeyboardButton(
                        text="PM eslatma",
                        callback_data=AdminActionCallback(action="remind_pm").pack(),
                    ),
                ],
            ]
        ),
        is_admin=True,
    )
