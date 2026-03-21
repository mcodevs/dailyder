from __future__ import annotations

import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ErrorEvent, InlineKeyboardMarkup, Message

from dailyder_bot.bot import keyboards, texts
from dailyder_bot.bot.callbacks import (
    DraftActionCallback,
    DraftConfirmCallback,
    DraftItemCallback,
    MenuCallback,
    PmActionCallback,
    PmItemCallback,
    PmStatusCallback,
    PmTargetCallback,
)
from dailyder_bot.bot.rendering import render_private_screen
from dailyder_bot.container import AppContext
from dailyder_bot.domain.enums import DigestPeriod, ItemStatus
from dailyder_bot.domain.parser import SubmissionParseError
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.services.access import GroupBindingError, MembershipError
from dailyder_bot.utils.dates import local_now, today_local

logger = logging.getLogger(__name__)

router = Router(name="user")
router.message.filter(F.chat.type == "private")

MORNING_FLOW = "morning"
PM_FLOW = "pm"


@router.message(CommandStart())
async def handle_start(
    message: Message,
    bot: Bot,
    app_context: AppContext,
) -> None:
    if message.from_user is None:
        return
    logger.info("Handling /start", extra={"telegram_user_id": message.from_user.id})

    try:
        group_chat_id = await app_context.access_service.ensure_group_member(bot, message.from_user.id)
    except GroupBindingError:
        await message.answer(texts.group_not_bound_text())
        return
    except MembershipError:
        await message.answer(texts.not_group_member_text())
        return

    now = _now(app_context)
    async with app_context.db.session() as session:
        async with session.begin():
            user = await UserRepository(session).upsert_from_telegram(
                telegram_user=message.from_user,
                joined_at=now,
                created_in_group_id=group_chat_id,
            )

    welcome_text = texts.welcome_text(is_admin=app_context.access_service.is_admin(message.from_user.id))
    await _show_today_summary(
        message,
        app_context,
        user.id,
        message.from_user.id,
        notice=welcome_text,
    )


@router.message(Command("help"))
@router.message(F.text == keyboards.MENU_HELP)
async def handle_help(
    message: Message,
    app_context: AppContext,
) -> None:
    if message.from_user is None:
        return
    logger.info(
        "Handling help entry",
        extra={"telegram_user_id": message.from_user.id, "text": getattr(message, "text", None)},
    )
    user = await _get_user_record(app_context, message.from_user.id)
    if user is None:
        await message.answer(texts.start_required_text())
        return
    await _render_screen(
        message,
        app_context,
        user.id,
        screen="help",
        text=texts.help_text(is_admin=app_context.access_service.is_admin(message.from_user.id)),
    )


@router.message(Command("today"))
@router.message(F.text == keyboards.MENU_TODAY)
async def handle_today_entry(
    message: Message,
    bot: Bot,
    app_context: AppContext,
) -> None:
    if message.from_user is None:
        return
    logger.info(
        "Handling today entry",
        extra={"telegram_user_id": message.from_user.id, "text": getattr(message, "text", None)},
    )
    user = await _ensure_ready_user(message, bot, app_context, message.from_user.id)
    if user is None:
        return
    await _show_today_summary(message, app_context, user.id, message.from_user.id)


@router.message(Command("update"))
@router.message(F.text == keyboards.MENU_PM)
async def handle_pm_entry(
    message: Message,
    bot: Bot,
    app_context: AppContext,
) -> None:
    if message.from_user is None:
        return
    logger.info(
        "Handling pm entry",
        extra={"telegram_user_id": message.from_user.id, "text": getattr(message, "text", None)},
    )
    user = await _ensure_ready_user(message, bot, app_context, message.from_user.id)
    if user is None:
        return
    await _show_pm_summary(message, app_context, user.id, message.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "home"))
async def handle_menu_home(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="main_menu",
        text=texts.main_menu_hint_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(MenuCallback.filter(F.action == "today"))
async def handle_menu_today_callback(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    logger.info("Handling menu callback", extra={"telegram_user_id": callback.from_user.id, "action": "today"})
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _show_today_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(MenuCallback.filter(F.action == "help"))
async def handle_menu_help_callback(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    logger.info("Handling menu callback", extra={"telegram_user_id": callback.from_user.id, "action": "help"})
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="help",
        text=texts.help_text(is_admin=app_context.access_service.is_admin(callback.from_user.id)),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(MenuCallback.filter(F.action == "pm"))
async def handle_menu_pm_callback(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    logger.info("Handling menu callback", extra={"telegram_user_id": callback.from_user.id, "action": "pm"})
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _show_pm_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(DraftActionCallback.filter(F.action == "resume"))
async def handle_resume_morning(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _resume_morning_prompt(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(DraftActionCallback.filter(F.action == "restart"))
async def handle_restart_morning(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _clear_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    await _show_today_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(DraftActionCallback.filter(F.action == "start_add"))
async def handle_start_add(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    project_choices = _project_choices(submission) if submission else []
    if project_choices:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="morning_project_picker",
            text=texts.project_picker_text(),
            reply_markup=keyboards.project_picker_keyboard(project_choices),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_project_name",
        payload={"mode": "add", "subtask_names": []},
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_project_prompt",
        text=texts.project_prompt_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "new_project"))
async def handle_new_project(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_project_name",
        payload={"mode": "add", "subtask_names": []},
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_project_prompt",
        text=texts.project_prompt_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftItemCallback.filter(F.action == "select_project"))
async def handle_select_project(
    callback: CallbackQuery,
    callback_data: DraftItemCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    item = next((entry for entry in submission.items if entry.id == callback_data.item_id), None)
    if item is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_task_name",
        payload={
            "mode": "add",
            "project_name": item.project_name,
            "subtask_names": [],
        },
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_task_prompt",
        text=texts.task_prompt_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "pick_edit"))
async def handle_pick_edit(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is None or not submission.items:
        fallback_user = await _get_user_record(app_context, callback.from_user.id)
        if fallback_user is not None:
            await _render_screen(
                callback.message,
                app_context,
                fallback_user.id,
                screen="menu_redirect",
                text=texts.menu_redirect_text(),
                preferred_message_id=callback.message.message_id,
            )
        else:
            await callback.message.answer(texts.menu_redirect_text())
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_pick_edit",
        text="<b>Qaysi taskni tahrirlaysiz?</b>",
        reply_markup=keyboards.item_picker_keyboard(
            submission.items,
            action="edit_item",
            back_action="back_to_summary",
        ),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftItemCallback.filter(F.action == "edit_item"))
async def handle_edit_item(
    callback: CallbackQuery,
    callback_data: DraftItemCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    item = next((entry for entry in submission.items if entry.id == callback_data.item_id), None)
    if item is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_project_name",
        payload={
            "mode": "edit",
            "item_id": item.id,
            "project_name": item.project_name,
            "task_name": item.task_name,
            "subtask_names": item.subtask_names,
        },
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_project_prompt",
        text=texts.project_prompt_text(current_value=item.project_name),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "pick_delete"))
async def handle_pick_delete(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is None or not submission.items:
        user = await _get_user_record(app_context, callback.from_user.id)
        if user is not None:
            await _render_screen(
                callback.message,
                app_context,
                user.id,
                screen="menu_redirect",
                text=texts.menu_redirect_text(),
                preferred_message_id=callback.message.message_id,
            )
        else:
            await callback.message.answer(texts.menu_redirect_text())
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_pick_delete",
        text="<b>Qaysi taskni o'chirasiz?</b>",
        reply_markup=keyboards.item_picker_keyboard(
            submission.items,
            action="delete_item",
            back_action="back_to_summary",
        ),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftItemCallback.filter(F.action == "delete_item"))
async def handle_delete_item(
    callback: CallbackQuery,
    callback_data: DraftItemCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    item = next((entry for entry in submission.items if entry.id == callback_data.item_id), None)
    if item is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="confirm_delete",
        payload={"action": "delete_item", "item_id": item.id},
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_delete_confirm",
        text=texts.delete_confirm_text(item),
        reply_markup=keyboards.draft_confirm_keyboard(action="delete_item"),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "start_import"))
async def handle_start_import(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is not None and submission.items:
        await _set_flow(
            app_context,
            user_id=user.id,
            flow=MORNING_FLOW,
            work_date=_work_date(app_context),
            step="confirm_import_replace",
            payload={"action": "import_text"},
        )
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="morning_import_replace_confirm",
            text=texts.import_replace_confirm_text(),
            reply_markup=keyboards.draft_confirm_keyboard(action="replace_import"),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_import_text",
        payload={"action": "import_text"},
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_import_prompt",
        text=texts.import_prompt_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "add_subtask"))
async def handle_add_subtask(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    session_state = await _get_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    if session_state is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_subtask_name",
        payload=session_state.payload,
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_subtask_prompt",
        text=texts.subtask_prompt_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "clear_subtasks"))
async def handle_clear_subtasks(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    session_state = await _get_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    if session_state is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    payload = dict(session_state.payload)
    payload["subtask_names"] = []
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_subtask_action",
        payload=payload,
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_subtask_builder",
        text=texts.subtask_builder_text(
            project_name=payload["project_name"],
            task_name=payload["task_name"],
            subtask_names=payload.get("subtask_names", []),
            mode=payload["mode"],
        ),
        reply_markup=keyboards.subtask_builder_keyboard(
            has_subtasks=bool(payload.get("subtask_names")),
        ),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "save_item"))
async def handle_save_item(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    session_state = await _get_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    if session_state is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is not None and submission.pm_submitted_at is not None:
        payload = dict(session_state.payload)
        payload["action"] = "save_item"
        await _set_flow(
            app_context,
            user_id=user.id,
            flow=MORNING_FLOW,
            work_date=_work_date(app_context),
            step="confirm_pm_reset",
            payload=payload,
        )
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="pm_reset_confirm",
            text=texts.pm_reset_confirmation_text(),
            reply_markup=keyboards.draft_confirm_keyboard(action="pm_reset"),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _execute_morning_mutation(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        action="save_item",
        payload=session_state.payload,
    )


@router.callback_query(DraftActionCallback.filter(F.action == "cancel_flow"))
@router.callback_query(DraftActionCallback.filter(F.action == "back_to_summary"))
async def handle_back_to_summary(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _clear_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    await _show_today_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(DraftActionCallback.filter(F.action == "submit"))
async def handle_submit_draft(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    try:
        submission = await app_context.submission_service.submit_morning_draft(
            telegram_user_id=callback.from_user.id,
            work_date=_work_date(app_context),
            submitted_at=_now(app_context),
        )
    except ValueError as exc:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="morning_submit_error",
            text=str(exc),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _clear_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    await app_context.digest_service.refresh_digest(_work_date(app_context), DigestPeriod.AM)
    await _show_pm_summary(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        notice=texts.draft_submitted_text(len(submission.items)),
    )


@router.callback_query(DraftConfirmCallback.filter(F.action == "delete_item"))
async def handle_delete_confirmation(
    callback: CallbackQuery,
    callback_data: DraftConfirmCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    session_state = await _get_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    if session_state is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    if callback_data.decision == "no":
        await _show_today_summary(callback.message, app_context, user.id, callback.from_user.id)
        return
    submission = await app_context.submission_service.get_today_submission(callback.from_user.id, _work_date(app_context))
    if submission is not None and submission.pm_submitted_at is not None:
        payload = dict(session_state.payload)
        await _set_flow(
            app_context,
            user_id=user.id,
            flow=MORNING_FLOW,
            work_date=_work_date(app_context),
            step="confirm_pm_reset",
            payload=payload,
        )
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="pm_reset_confirm",
            text=texts.pm_reset_confirmation_text(),
            reply_markup=keyboards.draft_confirm_keyboard(action="pm_reset"),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _execute_morning_mutation(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        action="delete_item",
        payload=session_state.payload,
    )


@router.callback_query(DraftConfirmCallback.filter(F.action == "replace_import"))
async def handle_import_replace_confirmation(
    callback: CallbackQuery,
    callback_data: DraftConfirmCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    if callback_data.decision == "no":
        await _clear_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
        await _show_today_summary(callback.message, app_context, user.id, callback.from_user.id)
        return
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=MORNING_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_import_text",
        payload={"action": "import_text"},
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="morning_import_prompt",
        text=texts.import_prompt_text(),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(DraftConfirmCallback.filter(F.action == "pm_reset"))
async def handle_pm_reset_confirmation(
    callback: CallbackQuery,
    callback_data: DraftConfirmCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    session_state = await _get_flow(app_context, user.id, MORNING_FLOW, _work_date(app_context))
    if session_state is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="menu_redirect",
            text=texts.menu_redirect_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    if callback_data.decision == "no":
        await _show_today_summary(callback.message, app_context, user.id, callback.from_user.id)
        return
    action = session_state.payload.get("action", "")
    await _execute_morning_mutation(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        action=action,
        payload=session_state.payload,
    )


@router.callback_query(PmActionCallback.filter(F.action == "resume"))
async def handle_resume_pm(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _resume_pm_prompt(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(PmActionCallback.filter(F.action == "restart"))
async def handle_restart_pm(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _clear_flow(app_context, user.id, PM_FLOW, _work_date(app_context))
    await _show_pm_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(PmItemCallback.filter(F.action == "select_item"))
async def handle_select_pm_item(
    callback: CallbackQuery,
    callback_data: PmItemCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_submitted_today_submission(
        callback.from_user.id,
        _work_date(app_context),
    )
    if submission is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="pm_empty",
            text=texts.pm_empty_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    await _show_pm_item_detail(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        callback_data.item_id,
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(PmTargetCallback.filter())
async def handle_select_pm_target(
    callback: CallbackQuery,
    callback_data: PmTargetCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _show_pm_status_picker(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        target_type=callback_data.target_type,
        target_id=callback_data.target_id,
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(PmStatusCallback.filter())
async def handle_pm_status_choice(
    callback: CallbackQuery,
    callback_data: PmStatusCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_submitted_today_submission(
        callback.from_user.id,
        _work_date(app_context),
    )
    if submission is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="pm_empty",
            text=texts.pm_empty_text(),
            preferred_message_id=callback.message.message_id,
        )
        return

    item_id: str | None
    if callback_data.target_type == "item":
        item_id = callback_data.target_id if any(item.id == callback_data.target_id for item in submission.items) else None
    else:
        item_id, _ = _find_item_and_subtask_by_subtask_id(submission, callback_data.target_id)

    if item_id is None:
        await _show_pm_summary(
            callback.message,
            app_context,
            user.id,
            callback.from_user.id,
            preferred_message_id=callback.message.message_id,
        )
        return

    if callback_data.target_type == "item":
        payload = await _load_pm_payload(app_context, user.id, callback.from_user.id)
        payload["status_map"][item_id] = callback_data.status
        await _set_flow(
            app_context,
            user_id=user.id,
            flow=PM_FLOW,
            work_date=_work_date(app_context),
            step="idle",
            payload=payload,
        )
    else:
        await app_context.submission_service.record_subtask_status(
            telegram_user_id=callback.from_user.id,
            work_date=_work_date(app_context),
            item_id=item_id,
            subtask_id=callback_data.target_id,
            status=ItemStatus(callback_data.status),
        )
    await _show_pm_item_detail(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        item_id,
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(PmActionCallback.filter(F.action == "edit_note"))
async def handle_pm_note_entry(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    payload = await _load_pm_payload(app_context, user.id, callback.from_user.id)
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=PM_FLOW,
        work_date=_work_date(app_context),
        step="awaiting_note",
        payload=payload,
    )
    await _render_screen(
        callback.message,
        app_context,
        user.id,
        screen="pm_note_prompt",
        text=texts.pm_note_prompt(current_note=payload.get("final_note")),
        reply_markup=keyboards.pm_note_keyboard(has_note=bool(payload.get("final_note"))),
        preferred_message_id=callback.message.message_id,
    )


@router.callback_query(PmActionCallback.filter(F.action == "clear_note"))
@router.callback_query(PmActionCallback.filter(F.action == "skip_note"))
async def handle_pm_note_clear(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    payload = await _load_pm_payload(app_context, user.id, callback.from_user.id)
    payload["final_note"] = None
    await _set_flow(
        app_context,
        user_id=user.id,
        flow=PM_FLOW,
        work_date=_work_date(app_context),
        step="idle",
        payload=payload,
    )
    await _show_pm_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(PmActionCallback.filter(F.action == "back_to_summary"))
async def handle_pm_back_to_summary(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    await _show_pm_summary(callback.message, app_context, user.id, callback.from_user.id)


@router.callback_query(PmActionCallback.filter(F.action == "submit"))
async def handle_pm_submit(
    callback: CallbackQuery,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    user = await _get_user_record(app_context, callback.from_user.id)
    if user is None:
        await callback.message.answer(texts.start_required_text())
        return
    submission = await app_context.submission_service.get_submitted_today_submission(
        callback.from_user.id,
        _work_date(app_context),
    )
    if submission is None:
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="pm_empty",
            text=texts.pm_empty_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    payload = await _load_pm_payload(app_context, user.id, callback.from_user.id)
    expected_item_ids = {item.id for item in submission.items}
    if expected_item_ids != set(payload["status_map"]):
        await _render_screen(
            callback.message,
            app_context,
            user.id,
            screen="pm_submit_error",
            text=texts.pm_submit_error_text(),
            preferred_message_id=callback.message.message_id,
        )
        return
    await app_context.submission_service.record_pm_statuses(
        telegram_user_id=callback.from_user.id,
        work_date=_work_date(app_context),
        status_map={item_id: ItemStatus(value) for item_id, value in payload["status_map"].items()},
        final_note=payload.get("final_note"),
        submitted_at=_now(app_context),
    )
    await _clear_flow(app_context, user.id, PM_FLOW, _work_date(app_context))
    await app_context.digest_service.refresh_digest(_work_date(app_context), DigestPeriod.PM)
    await _show_pm_summary(
        callback.message,
        app_context,
        user.id,
        callback.from_user.id,
        notice=texts.pm_saved_text(),
    )


@router.message(F.text)
async def handle_flow_text_input(
    message: Message,
    app_context: AppContext,
) -> None:
    if message.from_user is None or message.text is None:
        return
    user = await _get_user_record(app_context, message.from_user.id)
    if user is None:
        await message.answer(texts.start_required_text())
        return

    work_date = _work_date(app_context)
    morning_session = await _get_flow(app_context, user.id, MORNING_FLOW, work_date)
    if morning_session is not None and morning_session.step.startswith("awaiting_"):
        await _handle_morning_text_input(message, app_context, user.id, morning_session.step, morning_session.payload)
        return

    pm_session = await _get_flow(app_context, user.id, PM_FLOW, work_date)
    if pm_session is not None and pm_session.step == "awaiting_note":
        payload = dict(pm_session.payload)
        payload["final_note"] = message.text.strip()
        await _set_flow(
            app_context,
            user_id=user.id,
            flow=PM_FLOW,
            work_date=work_date,
            step="idle",
            payload=payload,
        )
        await _show_pm_summary(message, app_context, user.id, message.from_user.id)
        return

    await _render_screen(
        message,
        app_context,
        user.id,
        screen="main_menu",
        text=texts.main_menu_hint_text(),
    )


async def _handle_morning_text_input(
    message: Message,
    app_context: AppContext,
    user_id: str,
    step: str,
    payload: dict,
) -> None:
    work_date = _work_date(app_context)
    if step == "awaiting_project_name":
        new_payload = dict(payload)
        new_payload["project_name"] = message.text.strip()
        await _set_flow(
            app_context,
            user_id=user_id,
            flow=MORNING_FLOW,
            work_date=work_date,
            step="awaiting_task_name",
            payload=new_payload,
        )
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_task_prompt",
            text=texts.task_prompt_text(current_value=payload.get("task_name")),
        )
        return

    if step == "awaiting_task_name":
        new_payload = dict(payload)
        new_payload["task_name"] = message.text.strip()
        new_payload.setdefault("subtask_names", [])
        await _set_flow(
            app_context,
            user_id=user_id,
            flow=MORNING_FLOW,
            work_date=work_date,
            step="awaiting_subtask_action",
            payload=new_payload,
        )
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_subtask_builder",
            text=texts.subtask_builder_text(
                project_name=new_payload["project_name"],
                task_name=new_payload["task_name"],
                subtask_names=new_payload.get("subtask_names", []),
                mode=new_payload["mode"],
            ),
            reply_markup=keyboards.subtask_builder_keyboard(
                has_subtasks=bool(new_payload.get("subtask_names")),
            ),
        )
        return

    if step == "awaiting_subtask_name":
        new_payload = dict(payload)
        new_payload.setdefault("subtask_names", [])
        new_payload["subtask_names"] = [*new_payload["subtask_names"], message.text.strip()]
        await _set_flow(
            app_context,
            user_id=user_id,
            flow=MORNING_FLOW,
            work_date=work_date,
            step="awaiting_subtask_action",
            payload=new_payload,
        )
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_subtask_builder",
            text=texts.subtask_builder_text(
                project_name=new_payload["project_name"],
                task_name=new_payload["task_name"],
                subtask_names=new_payload.get("subtask_names", []),
                mode=new_payload["mode"],
            ),
            reply_markup=keyboards.subtask_builder_keyboard(
                has_subtasks=bool(new_payload.get("subtask_names")),
            ),
        )
        return

    if step == "awaiting_import_text":
        submission = await app_context.submission_service.get_today_submission(message.from_user.id, work_date)
        if submission is not None and submission.pm_submitted_at is not None:
            new_payload = {"action": "import_text", "raw_text": message.text}
            await _set_flow(
                app_context,
                user_id=user_id,
                flow=MORNING_FLOW,
                work_date=work_date,
                step="confirm_pm_reset",
                payload=new_payload,
            )
            await _render_screen(
                message,
                app_context,
                user_id,
                screen="pm_reset_confirm",
                text=texts.pm_reset_confirmation_text(),
                reply_markup=keyboards.draft_confirm_keyboard(action="pm_reset"),
            )
            return
        await _execute_morning_mutation(
            message,
            app_context,
            user_id,
            message.from_user.id,
            action="import_text",
            payload={"raw_text": message.text},
        )


async def _execute_morning_mutation(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
    *,
    action: str,
    payload: dict,
) -> None:
    work_date = _work_date(app_context)
    try:
        if action == "save_item":
            if payload.get("mode") == "edit":
                result = await app_context.submission_service.update_draft_item(
                    telegram_user_id=telegram_user_id,
                    work_date=work_date,
                    item_id=payload["item_id"],
                    project_name=payload["project_name"],
                    task_name=payload["task_name"],
                    subtask_names=payload.get("subtask_names", []),
                )
            else:
                result = await app_context.submission_service.add_draft_item(
                    telegram_user_id=telegram_user_id,
                    work_date=work_date,
                    project_name=payload["project_name"],
                    task_name=payload["task_name"],
                    subtask_names=payload.get("subtask_names", []),
                )
            notice = texts.draft_change_saved_text(pm_reset=result.pm_reset)
        elif action == "delete_item":
            result = await app_context.submission_service.delete_draft_item(
                telegram_user_id=telegram_user_id,
                work_date=work_date,
                item_id=payload["item_id"],
            )
            notice = texts.draft_deleted_text(pm_reset=result.pm_reset)
        elif action == "import_text":
            result = await app_context.submission_service.import_draft_from_text(
                telegram_user_id=telegram_user_id,
                raw_text=payload["raw_text"],
                work_date=work_date,
            )
            notice = texts.draft_change_saved_text(pm_reset=result.pm_reset)
        else:
            await _render_screen(
                message,
                app_context,
                user_id,
                screen="menu_redirect",
                text=texts.menu_redirect_text(),
            )
            return
    except SubmissionParseError as exc:
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="parse_error",
            text=texts.parse_error_text(exc.errors),
        )
        return
    except ValueError as exc:
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_error",
            text=str(exc),
        )
        return

    if result.pm_reset:
        logger.info("PM update reset after AM change", extra={"telegram_user_id": telegram_user_id})
        await _clear_flow(app_context, user_id, PM_FLOW, work_date)
        await app_context.digest_service.refresh_digest(work_date, DigestPeriod.PM)

    await _clear_flow(app_context, user_id, MORNING_FLOW, work_date)
    await app_context.digest_service.refresh_digest(work_date, DigestPeriod.AM)
    await _show_today_summary(
        message,
        app_context,
        user_id,
        telegram_user_id,
        notice=notice,
    )


async def _show_today_summary(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
    preferred_message_id: int | None = None,
    notice: str | None = None,
) -> None:
    work_date = _work_date(app_context)
    session_state = await _get_flow(app_context, user_id, MORNING_FLOW, work_date)
    if session_state is not None:
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_resume",
            text=texts.draft_resume_text(),
            reply_markup=keyboards.draft_resume_keyboard(),
            preferred_message_id=preferred_message_id,
        )
        return
    submission = await app_context.submission_service.get_today_submission(telegram_user_id, work_date)
    summary_text = texts.draft_summary_text(work_date, submission)
    if notice:
        summary_text = f"{notice}\n\n{summary_text}"
    await _render_screen(
        message,
        app_context,
        user_id,
        screen="today_summary",
        text=summary_text,
        reply_markup=keyboards.today_summary_keyboard(has_items=bool(submission and submission.items)),
        preferred_message_id=preferred_message_id,
    )


async def _show_pm_summary(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
    preferred_message_id: int | None = None,
    notice: str | None = None,
) -> None:
    work_date = _work_date(app_context)
    session_state = await _get_flow(app_context, user_id, PM_FLOW, work_date)
    if session_state is not None and session_state.step == "awaiting_note":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="pm_resume",
            text=texts.pm_resume_text(),
            reply_markup=keyboards.pm_resume_keyboard(),
            preferred_message_id=preferred_message_id,
        )
        return
    submission = await app_context.submission_service.get_submitted_today_submission(telegram_user_id, work_date)
    if submission is None:
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="pm_empty",
            text=texts.pm_empty_text(),
            preferred_message_id=preferred_message_id,
        )
        return
    payload = await _load_pm_payload(app_context, user_id, telegram_user_id)
    summary_text = texts.pm_summary_text(
        work_date=work_date,
        submission=submission,
        status_map=payload["status_map"],
        final_note=payload.get("final_note"),
    )
    if notice:
        summary_text = f"{notice}\n\n{summary_text}"
    await _render_screen(
        message,
        app_context,
        user_id,
        screen="pm_summary",
        text=summary_text,
        reply_markup=keyboards.pm_summary_keyboard(
            items=submission.items,
            status_map=payload["status_map"],
        ),
        preferred_message_id=preferred_message_id,
    )


async def _show_pm_item_detail(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
    item_id: str,
    preferred_message_id: int | None = None,
) -> None:
    submission = await app_context.submission_service.get_submitted_today_submission(
        telegram_user_id,
        _work_date(app_context),
    )
    if submission is None:
        await _show_pm_summary(
            message,
            app_context,
            user_id,
            telegram_user_id,
            preferred_message_id=preferred_message_id,
        )
        return
    item = next((entry for entry in submission.items if entry.id == item_id), None)
    if item is None:
        await _show_pm_summary(
            message,
            app_context,
            user_id,
            telegram_user_id,
            preferred_message_id=preferred_message_id,
        )
        return
    payload = await _load_pm_payload(app_context, user_id, telegram_user_id)
    await _render_screen(
        message,
        app_context,
        user_id,
        screen="pm_item_detail",
        text=texts.pm_item_prompt(item, current_status=payload["status_map"].get(item.id)),
        reply_markup=keyboards.pm_item_detail_keyboard(
            item=item,
            current_status=payload["status_map"].get(item.id),
        ),
        preferred_message_id=preferred_message_id,
    )


async def _show_pm_status_picker(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
    *,
    target_type: str,
    target_id: str,
    preferred_message_id: int | None = None,
) -> None:
    submission = await app_context.submission_service.get_submitted_today_submission(
        telegram_user_id,
        _work_date(app_context),
    )
    if submission is None:
        await _show_pm_summary(
            message,
            app_context,
            user_id,
            telegram_user_id,
            preferred_message_id=preferred_message_id,
        )
        return
    item_id: str | None
    if target_type == "item":
        item_id = target_id
        item = next((entry for entry in submission.items if entry.id == item_id), None)
        if item is None:
            await _show_pm_summary(
                message,
                app_context,
                user_id,
                telegram_user_id,
                preferred_message_id=preferred_message_id,
            )
            return
        payload = await _load_pm_payload(app_context, user_id, telegram_user_id)
        title = f"Task: {item.task_name}"
        current_status = payload["status_map"].get(item.id)
    else:
        item_id, subtask = _find_item_and_subtask_by_subtask_id(submission, target_id)
        if item_id is None or subtask is None:
            await _show_pm_summary(
                message,
                app_context,
                user_id,
                telegram_user_id,
                preferred_message_id=preferred_message_id,
            )
            return
        item = next((entry for entry in submission.items if entry.id == item_id), None)
        if item is None:
            await _show_pm_summary(
                message,
                app_context,
                user_id,
                telegram_user_id,
                preferred_message_id=preferred_message_id,
            )
            return
        title = f"Subtask: {subtask.subtask_name}"
        current_status = subtask.status

    await _render_screen(
        message,
        app_context,
        user_id,
        screen="pm_status_picker",
        text=texts.pm_target_prompt(title=title, current_status=current_status),
        reply_markup=keyboards.pm_status_keyboard(
            target_type=target_type,
            target_id=target_id,
        ),
        preferred_message_id=preferred_message_id,
    )


def _find_item_and_subtask_by_subtask_id(submission: DailySubmission, subtask_id: str) -> tuple[str | None, object | None]:
    for item in submission.items:
        for subtask in item.subtasks:
            if subtask.id == subtask_id:
                return item.id, subtask
    return None, None


async def _resume_morning_prompt(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
) -> None:
    session_state = await _get_flow(app_context, user_id, MORNING_FLOW, _work_date(app_context))
    if session_state is None:
        await _show_today_summary(message, app_context, user_id, telegram_user_id)
        return
    if session_state.step == "awaiting_project_name":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_project_prompt",
            text=texts.project_prompt_text(current_value=session_state.payload.get("project_name")),
        )
    elif session_state.step == "awaiting_task_name":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_task_prompt",
            text=texts.task_prompt_text(current_value=session_state.payload.get("task_name")),
        )
    elif session_state.step == "awaiting_subtask_name":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_subtask_prompt",
            text=texts.subtask_prompt_text(),
        )
    elif session_state.step == "awaiting_subtask_action":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_subtask_builder",
            text=texts.subtask_builder_text(
                project_name=session_state.payload["project_name"],
                task_name=session_state.payload["task_name"],
                subtask_names=session_state.payload.get("subtask_names", []),
                mode=session_state.payload["mode"],
            ),
            reply_markup=keyboards.subtask_builder_keyboard(
                has_subtasks=bool(session_state.payload.get("subtask_names")),
            ),
        )
    elif session_state.step == "awaiting_import_text":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_import_prompt",
            text=texts.import_prompt_text(),
        )
    elif session_state.step == "confirm_delete":
        submission = await app_context.submission_service.get_today_submission(telegram_user_id, _work_date(app_context))
        if submission is None:
            await _show_today_summary(message, app_context, user_id, telegram_user_id)
            return
        item = next((entry for entry in submission.items if entry.id == session_state.payload["item_id"]), None)
        if item is None:
            await _show_today_summary(message, app_context, user_id, telegram_user_id)
            return
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_delete_confirm",
            text=texts.delete_confirm_text(item),
            reply_markup=keyboards.draft_confirm_keyboard(action="delete_item"),
        )
    elif session_state.step == "confirm_import_replace":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="morning_import_replace_confirm",
            text=texts.import_replace_confirm_text(),
            reply_markup=keyboards.draft_confirm_keyboard(action="replace_import"),
        )
    elif session_state.step == "confirm_pm_reset":
        await _render_screen(
            message,
            app_context,
            user_id,
            screen="pm_reset_confirm",
            text=texts.pm_reset_confirmation_text(),
            reply_markup=keyboards.draft_confirm_keyboard(action="pm_reset"),
        )
    else:
        await _show_today_summary(message, app_context, user_id, telegram_user_id)


async def _resume_pm_prompt(
    message: Message,
    app_context: AppContext,
    user_id: str,
    telegram_user_id: int,
) -> None:
    session_state = await _get_flow(app_context, user_id, PM_FLOW, _work_date(app_context))
    if session_state is None:
        await _show_pm_summary(message, app_context, user_id, telegram_user_id)
        return
    await _render_screen(
        message,
        app_context,
        user_id,
        screen="pm_note_prompt",
        text=texts.pm_note_prompt(current_note=session_state.payload.get("final_note")),
        reply_markup=keyboards.pm_note_keyboard(has_note=bool(session_state.payload.get("final_note"))),
    )


async def _load_pm_payload(app_context: AppContext, user_id: str, telegram_user_id: int) -> dict:
    work_date = _work_date(app_context)
    session_state = await _get_flow(app_context, user_id, PM_FLOW, work_date)
    if session_state is not None:
        return session_state.payload

    submission = await app_context.submission_service.get_submitted_today_submission(telegram_user_id, work_date)
    if submission is None:
        return {"status_map": {}, "final_note": None}

    payload = {
        "status_map": {
            item.id: item.status.status
            for item in submission.items
            if item.status is not None
        },
        "final_note": submission.final_note,
    }
    await _set_flow(
        app_context,
        user_id=user_id,
        flow=PM_FLOW,
        work_date=work_date,
        step="idle",
        payload=payload,
    )
    return payload


async def _ensure_ready_user(
    message: Message,
    bot: Bot,
    app_context: AppContext,
    telegram_user_id: int,
):
    try:
        await app_context.access_service.ensure_group_member(bot, telegram_user_id)
    except GroupBindingError:
        await message.answer(texts.group_not_bound_text())
        return None
    except MembershipError:
        await message.answer(texts.not_group_member_text())
        return None

    user = await _get_user_record(app_context, telegram_user_id)
    if user is None:
        await message.answer(texts.start_required_text())
        return None
    return user


async def _get_user_record(app_context: AppContext, telegram_user_id: int):
    async with app_context.db.session() as session:
        return await UserRepository(session).get_by_telegram_id(telegram_user_id)


def _work_date(app_context: AppContext) -> date:
    return today_local(app_context.settings.timezone_info)


def _now(app_context: AppContext):
    return local_now(app_context.settings.timezone_info)


async def _get_flow(app_context: AppContext, user_id: str, flow: str, work_date: date):
    return await app_context.flow_session_service.get(
        user_id=user_id,
        flow=flow,
        work_date=work_date,
        now=_now(app_context),
    )


async def _set_flow(
    app_context: AppContext,
    *,
    user_id: str,
    flow: str,
    work_date: date,
    step: str,
    payload: dict,
) -> None:
    await app_context.flow_session_service.set(
        user_id=user_id,
        flow=flow,
        work_date=work_date,
        step=step,
        payload=payload,
        now=_now(app_context),
    )


async def _clear_flow(app_context: AppContext, user_id: str, flow: str, work_date: date) -> None:
    await app_context.flow_session_service.clear(
        user_id=user_id,
        flow=flow,
        work_date=work_date,
    )


def _project_choices(submission: DailySubmission) -> list[tuple[str, str]]:
    seen: set[str] = set()
    choices: list[tuple[str, str]] = []
    for item in submission.items:
        if item.project_name in seen:
            continue
        seen.add(item.project_name)
        choices.append((item.project_name, item.id))
    return choices


async def _render_screen(
    message: Message,
    app_context: AppContext,
    user_id: str,
    *,
    screen: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    preferred_message_id: int | None = None,
) -> None:
    is_admin = message.chat.type == "private" and app_context.access_service.is_admin(message.chat.id)
    is_user_message = bool(message.from_user) and message.from_user.id == message.chat.id
    effective_preferred_message_id = preferred_message_id
    include_last_message_candidate = True
    if is_user_message and effective_preferred_message_id is None:
        # User-typed commands should always produce a fresh visible message.
        include_last_message_candidate = False
    navigation_markup = keyboards.with_main_menu(
        reply_markup,
        is_admin=is_admin,
    )
    try:
        await render_private_screen(
            app_context=app_context,
            user_id=user_id,
            chat_id=message.chat.id,
            screen=screen,
            text=text,
            reply_markup=navigation_markup,
            preferred_message_id=effective_preferred_message_id,
            include_last_message_candidate=include_last_message_candidate,
        )
    except Exception:
        logger.exception(
            "Failed to render user private screen",
            extra={
                "screen": screen,
                "chat_id": message.chat.id,
                "user_id": user_id,
                "preferred_message_id": preferred_message_id,
            },
        )
        try:
            await message.answer("Xatolik yuz berdi. /start yoki /today ni qayta yuboring.")
        except TelegramBadRequest:
            logger.exception(
                "Failed to send fallback user error message",
                extra={"chat_id": message.chat.id, "user_id": user_id},
            )


@router.error()
async def handle_user_router_error(event: ErrorEvent) -> None:
    update_id = event.update.update_id
    message = event.update.message
    callback = event.update.callback_query
    logger.error(
        "Unhandled exception in user router",
        exc_info=event.exception,
        extra={
            "update_id": update_id,
            "telegram_user_id": (
                message.from_user.id
                if message and message.from_user
                else callback.from_user.id
                if callback and callback.from_user
                else None
            ),
        },
    )
    if callback is not None and callback.message is not None:
        try:
            await callback.message.answer("Texnik xatolik bo'ldi. Iltimos, /start ni qayta yuboring.")
        except TelegramBadRequest:
            logger.exception("Failed to send callback fallback error message", extra={"update_id": update_id})
        return
    if message is not None:
        try:
            await message.answer("Texnik xatolik bo'ldi. Iltimos, /start ni qayta yuboring.")
        except TelegramBadRequest:
            logger.exception("Failed to send message fallback error text", extra={"update_id": update_id})
