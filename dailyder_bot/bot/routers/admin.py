from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from dailyder_bot.bot import keyboards, texts
from dailyder_bot.bot.callbacks import AdminActionCallback
from dailyder_bot.bot.states import WarningFlowState
from dailyder_bot.container import AppContext
from dailyder_bot.utils.dates import local_now, today_local
from dailyder_bot.utils.telegram import telegram_user_mention_html, user_mention_html

logger = logging.getLogger(__name__)

router = Router(name="admin")

_EDIT_FALLBACK_ERRORS = (
    "message can't be edited",
    "message to edit not found",
    "message identifier is not specified",
)


@router.message(Command("bind_group"), F.chat.type.in_({"group", "supergroup"}))
async def handle_bind_group(message: Message, app_context: AppContext) -> None:
    if message.from_user is None or not app_context.access_service.is_admin(message.from_user.id):
        await message.reply(texts.admin_only_text())
        return
    await app_context.admin_service.bind_group_with_topic(
        admin_user_id=message.from_user.id,
        chat_id=message.chat.id,
        title=message.chat.title or str(message.chat.id),
        message_thread_id=message.message_thread_id,
        now=local_now(app_context.settings.timezone_info),
    )
    if message.message_thread_id is not None:
        await message.reply(f"Topic muvaffaqiyatli biriktirildi. Thread ID: {message.message_thread_id}")
    else:
        await message.reply("Guruh muvaffaqiyatli biriktirildi.")


@router.message(Command("admin"), F.chat.type == "private")
@router.message(F.chat.type == "private", F.text == keyboards.MENU_ADMIN)
async def handle_admin_menu(message: Message, app_context: AppContext) -> None:
    if not _is_admin(message, app_context):
        await message.answer(texts.admin_only_text())
        return
    await message.answer(texts.admin_menu_text(), reply_markup=keyboards.admin_menu_keyboard())


@router.message(Command("pending"), F.chat.type == "private")
@router.message(Command("pending"), F.chat.type.in_({"group", "supergroup"}))
async def handle_pending(message: Message, app_context: AppContext) -> None:
    if not _is_admin(message, app_context):
        await message.answer(texts.admin_only_text())
        return
    report = await app_context.admin_service.pending_report(today_local(app_context.settings.timezone_info))
    await message.answer(report)


@router.message(Command("warning"), F.chat.type.in_({"group", "supergroup"}))
async def handle_warning_start(
    message: Message,
    state: FSMContext,
    app_context: AppContext,
) -> None:
    if message.from_user is None or not app_context.access_service.is_admin(message.from_user.id):
        await message.answer(texts.admin_only_text())
        return

    await state.clear()
    await _delete_message_quietly(message)
    prompt = await message.answer(texts.warning_username_prompt_text())
    await state.update_data(
        chat_id=message.chat.id,
        message_thread_id=message.message_thread_id,
        prompt_message_id=prompt.message_id,
    )
    await state.set_state(WarningFlowState.waiting_for_username)


@router.message(WarningFlowState.waiting_for_username, F.chat.type.in_({"group", "supergroup"}))
async def handle_warning_username(
    message: Message,
    state: FSMContext,
    app_context: AppContext,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if not app_context.access_service.is_admin(message.from_user.id):
        return

    data = await state.get_data()
    await _delete_message_quietly(message)

    developer = await app_context.admin_service.resolve_warning_target(message.text)
    if developer is None:
        prompt_message_id = await _edit_or_send_group_prompt(
            app_context=app_context,
            chat_id=message.chat.id,
            prompt_message_id=data.get("prompt_message_id"),
            message_thread_id=data.get("message_thread_id"),
            text=texts.warning_username_not_found_text(message.text),
        )
        await state.update_data(prompt_message_id=prompt_message_id)
        return

    prompt_message_id = await _edit_or_send_group_prompt(
        app_context=app_context,
        chat_id=message.chat.id,
        prompt_message_id=data.get("prompt_message_id"),
        message_thread_id=data.get("message_thread_id"),
        text=texts.warning_reason_prompt_text(user_mention_html(developer)),
    )
    await state.update_data(
        prompt_message_id=prompt_message_id,
        developer_username=developer.username or message.text.strip().lstrip("@"),
    )
    await state.set_state(WarningFlowState.waiting_for_reason)


@router.message(WarningFlowState.waiting_for_reason, F.chat.type.in_({"group", "supergroup"}))
async def handle_warning_reason(
    message: Message,
    state: FSMContext,
    app_context: AppContext,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if not app_context.access_service.is_admin(message.from_user.id):
        return

    data = await state.get_data()
    await _delete_message_quietly(message)

    reason = message.text.strip()
    if not reason:
        prompt_message_id = await _edit_or_send_group_prompt(
            app_context=app_context,
            chat_id=message.chat.id,
            prompt_message_id=data.get("prompt_message_id"),
            message_thread_id=data.get("message_thread_id"),
            text=texts.warning_reason_empty_text(),
        )
        await state.update_data(prompt_message_id=prompt_message_id)
        return

    now = local_now(app_context.settings.timezone_info)
    try:
        issued = await app_context.admin_service.issue_warning(
            admin_telegram_user_id=message.from_user.id,
            developer_username=data["developer_username"],
            group_chat_id=message.chat.id,
            reason=reason,
            now=now,
        )
    except ValueError:
        prompt_message_id = await _edit_or_send_group_prompt(
            app_context=app_context,
            chat_id=message.chat.id,
            prompt_message_id=data.get("prompt_message_id"),
            message_thread_id=data.get("message_thread_id"),
            text=texts.warning_username_not_found_text(data.get("developer_username", "")),
        )
        await state.update_data(prompt_message_id=prompt_message_id)
        await state.set_state(WarningFlowState.waiting_for_username)
        return

    warning_text = texts.warning_message_text(
        developer_mention=user_mention_html(issued.developer),
        admin_mention=telegram_user_mention_html(message.from_user),
        reason=reason,
        issued_at=now,
    )
    await _edit_or_send_group_prompt(
        app_context=app_context,
        chat_id=message.chat.id,
        prompt_message_id=data.get("prompt_message_id"),
        message_thread_id=data.get("message_thread_id"),
        text=warning_text,
    )

    try:
        await app_context.bot.send_message(
            chat_id=issued.developer.telegram_user_id,
            text=warning_text,
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning(
            "Failed to deliver warning in private chat",
            extra={"developer_user_id": issued.developer.id, "telegram_user_id": issued.developer.telegram_user_id},
        )
        await message.answer(texts.warning_private_delivery_failed_text())

    await state.clear()


@router.message(Command("metrics"), F.chat.type == "private")
async def handle_metrics(message: Message, app_context: AppContext) -> None:
    if not _is_admin(message, app_context):
        await message.answer(texts.admin_only_text())
        return
    report = await app_context.admin_service.metrics_report(today_local(app_context.settings.timezone_info))
    await message.answer(report)


@router.message(Command("remind_missing"), F.chat.type == "private")
async def handle_remind_missing(
    message: Message,
    command: CommandObject,
    app_context: AppContext,
) -> None:
    if not _is_admin(message, app_context):
        await message.answer(texts.admin_only_text())
        return
    period = (command.args or "").strip().lower()
    if period not in {"am", "pm"}:
        await message.answer("Foydalanish: /remind_missing am yoki /remind_missing pm")
        return
    sent_count = await app_context.admin_service.resend_missing(
        period=period,
        work_date=today_local(app_context.settings.timezone_info),
        admin_user_id=message.from_user.id,
        now=local_now(app_context.settings.timezone_info),
    )
    await message.answer(f"{sent_count} ta developerga {period.upper()} eslatma yuborildi.")


@router.callback_query(AdminActionCallback.filter())
async def handle_admin_actions(
    callback: CallbackQuery,
    callback_data: AdminActionCallback,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.from_user is None or not app_context.access_service.is_admin(callback.from_user.id):
        if callback.message:
            await callback.message.answer(texts.admin_only_text())
        return
    if callback.message is None:
        return

    today = today_local(app_context.settings.timezone_info)
    admin_menu = keyboards.admin_menu_keyboard()
    if callback_data.action == "readiness":
        await _edit_or_send_private_callback(callback.message, await app_context.admin_service.readiness_report(), admin_menu)
    elif callback_data.action == "pending":
        await _edit_or_send_private_callback(callback.message, await app_context.admin_service.pending_report(today), admin_menu)
    elif callback_data.action == "metrics":
        await _edit_or_send_private_callback(callback.message, await app_context.admin_service.metrics_report(today), admin_menu)
    elif callback_data.action == "users":
        await _edit_or_send_private_callback(callback.message, await app_context.admin_service.onboarded_users_report(), admin_menu)
    elif callback_data.action == "remind_am":
        sent_count = await app_context.admin_service.resend_missing(
            period="am",
            work_date=today,
            admin_user_id=callback.from_user.id,
            now=local_now(app_context.settings.timezone_info),
        )
        await _edit_or_send_private_callback(callback.message, f"{sent_count} ta developerga AM eslatma yuborildi.", admin_menu)
    elif callback_data.action == "remind_pm":
        sent_count = await app_context.admin_service.resend_missing(
            period="pm",
            work_date=today,
            admin_user_id=callback.from_user.id,
            now=local_now(app_context.settings.timezone_info),
        )
        await _edit_or_send_private_callback(callback.message, f"{sent_count} ta developerga PM eslatma yuborildi.", admin_menu)


def _is_admin(message: Message, app_context: AppContext) -> bool:
    return bool(message.from_user) and app_context.access_service.is_admin(message.from_user.id)


async def _delete_message_quietly(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        return


async def _edit_or_send_group_prompt(
    *,
    app_context: AppContext,
    chat_id: int,
    prompt_message_id: int | None,
    message_thread_id: int | None,
    text: str,
) -> int:
    if prompt_message_id is not None:
        try:
            await app_context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=prompt_message_id,
                text=text,
            )
            return prompt_message_id
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if "message is not modified" in error_text:
                return prompt_message_id
            if not any(fragment in error_text for fragment in _EDIT_FALLBACK_ERRORS):
                raise

    sent = await app_context.bot.send_message(
        chat_id=chat_id,
        text=text,
        message_thread_id=message_thread_id,
    )
    return sent.message_id


async def _edit_or_send_private_callback(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text:
            return
        if any(fragment in error_text for fragment in _EDIT_FALLBACK_ERRORS):
            await message.answer(text, reply_markup=reply_markup)
            return
        raise
