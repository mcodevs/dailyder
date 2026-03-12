from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from dailyder_bot.bot import keyboards, texts
from dailyder_bot.bot.callbacks import ActionCallback
from dailyder_bot.container import AppContext
from dailyder_bot.utils.dates import local_now, today_local

router = Router(name="admin")


@router.message(Command("bind_group"), F.chat.type.in_({"group", "supergroup"}))
async def handle_bind_group(message: Message, app_context: AppContext) -> None:
    if message.from_user is None or not app_context.access_service.is_admin(message.from_user.id):
        await message.reply(texts.admin_only_text())
        return
    await app_context.admin_service.bind_group(
        admin_user_id=message.from_user.id,
        chat_id=message.chat.id,
        title=message.chat.title or str(message.chat.id),
        now=local_now(app_context.settings.timezone_info),
    )
    await message.reply("Guruh muvaffaqiyatli biriktirildi.")


@router.message(Command("admin"), F.chat.type == "private")
async def handle_admin_menu(message: Message, app_context: AppContext) -> None:
    if not _is_admin(message, app_context):
        await message.answer(texts.admin_only_text())
        return
    await message.answer(texts.admin_menu_text(), reply_markup=keyboards.admin_menu_keyboard())


@router.message(Command("pending"), F.chat.type == "private")
async def handle_pending(message: Message, app_context: AppContext) -> None:
    if not _is_admin(message, app_context):
        await message.answer(texts.admin_only_text())
        return
    report = await app_context.admin_service.pending_report(today_local(app_context.settings.timezone_info))
    await message.answer(report)


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


@router.callback_query(ActionCallback.filter(F.name.startswith("admin_")))
async def handle_admin_callbacks(
    callback: CallbackQuery,
    callback_data: ActionCallback,
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
    if callback_data.name == "admin_readiness":
        await callback.message.answer(await app_context.admin_service.readiness_report())
    elif callback_data.name == "admin_pending":
        await callback.message.answer(await app_context.admin_service.pending_report(today))
    elif callback_data.name == "admin_metrics":
        await callback.message.answer(await app_context.admin_service.metrics_report(today))
    elif callback_data.name == "admin_users":
        await callback.message.answer(await app_context.admin_service.onboarded_users_report())
    elif callback_data.name == "admin_remind_am":
        sent_count = await app_context.admin_service.resend_missing(
            period="am",
            work_date=today,
            admin_user_id=callback.from_user.id,
            now=local_now(app_context.settings.timezone_info),
        )
        await callback.message.answer(f"{sent_count} ta developerga AM eslatma yuborildi.")
    elif callback_data.name == "admin_remind_pm":
        sent_count = await app_context.admin_service.resend_missing(
            period="pm",
            work_date=today,
            admin_user_id=callback.from_user.id,
            now=local_now(app_context.settings.timezone_info),
        )
        await callback.message.answer(f"{sent_count} ta developerga PM eslatma yuborildi.")


def _is_admin(message: Message, app_context: AppContext) -> bool:
    return bool(message.from_user) and app_context.access_service.is_admin(message.from_user.id)
