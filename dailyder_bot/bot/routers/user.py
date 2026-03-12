from __future__ import annotations

from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from dailyder_bot.bot.callbacks import ActionCallback, ItemStatusCallback
from dailyder_bot.bot import keyboards, texts
from dailyder_bot.bot.states import EveningUpdateState, MorningSubmissionState
from dailyder_bot.container import AppContext
from dailyder_bot.domain.enums import DigestPeriod, ItemStatus
from dailyder_bot.domain.parser import SubmissionParseError
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.services.access import GroupBindingError, MembershipError
from dailyder_bot.utils.dates import local_now, today_local
from dailyder_bot.utils.telegram import user_mention_html

router = Router(name="user")
router.message.filter(F.chat.type == "private")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
) -> None:
    if message.from_user is None:
        return

    await state.clear()
    try:
        group_chat_id = await app_context.access_service.ensure_group_member(bot, message.from_user.id)
    except GroupBindingError:
        await message.answer(texts.group_not_bound_text())
        return
    except MembershipError:
        await message.answer(texts.not_group_member_text())
        return

    now = local_now(app_context.settings.timezone_info)
    async with app_context.db.session() as session:
        async with session.begin():
            await UserRepository(session).upsert_from_telegram(
                telegram_user=message.from_user,
                joined_at=now,
                created_in_group_id=group_chat_id,
            )

    await message.answer(texts.welcome_text(), reply_markup=keyboards.morning_shortcuts())


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(texts.help_text())


@router.message(Command("today"))
async def handle_today_command(
    message: Message,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
) -> None:
    await _start_morning_flow(message, state, bot, app_context)


@router.callback_query(ActionCallback.filter(F.name == "today"))
async def handle_today_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    await _start_morning_flow(callback.message, state, bot, app_context, callback.from_user.id)


@router.message(MorningSubmissionState.waiting_for_text)
async def handle_morning_submission(
    message: Message,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
) -> None:
    if message.from_user is None or message.text is None:
        return

    try:
        await app_context.access_service.ensure_group_member(bot, message.from_user.id)
    except GroupBindingError:
        await message.answer(texts.group_not_bound_text())
        return
    except MembershipError:
        await message.answer(texts.not_group_member_text())
        return

    work_date = today_local(app_context.settings.timezone_info)
    submitted_at = local_now(app_context.settings.timezone_info)
    try:
        submission = await app_context.submission_service.submit_morning(
            telegram_user_id=message.from_user.id,
            raw_text=message.text,
            work_date=work_date,
            submitted_at=submitted_at,
        )
    except SubmissionParseError as exc:
        await message.answer(texts.parse_error_text(exc.errors))
        return
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await app_context.digest_service.refresh_digest(work_date, DigestPeriod.AM)
    await state.clear()
    await message.answer(texts.morning_submission_saved_text(len(submission.items)))


@router.message(Command("update"))
async def handle_update_command(
    message: Message,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
) -> None:
    await _start_pm_flow(message, state, bot, app_context)


@router.callback_query(ActionCallback.filter(F.name == "update"))
async def handle_update_callback(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    await _start_pm_flow(callback.message, state, bot, app_context, callback.from_user.id)


@router.callback_query(EveningUpdateState.choosing_status, ItemStatusCallback.filter())
async def handle_status_choice(
    callback: CallbackQuery,
    callback_data: ItemStatusCallback,
    state: FSMContext,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    items: list[dict] = data.get("items", [])
    cursor = int(data.get("cursor", 0))
    statuses: dict[str, str] = data.get("statuses", {})

    if cursor >= len(items):
        await state.clear()
        await callback.message.answer("Status sessiyasi eskirdi. /update ni qayta yuboring.")
        return

    current_item = items[cursor]
    if callback_data.item_id != current_item["id"]:
        await callback.answer("Faqat joriy vazifa uchun status tanlang.", show_alert=True)
        return

    statuses[callback_data.item_id] = callback_data.status
    cursor += 1
    await state.update_data(cursor=cursor, statuses=statuses)

    if cursor < len(items):
        next_item = items[cursor]
        await callback.message.edit_text(
            texts.pm_item_prompt_parts(
                project_name=next_item["project_name"],
                task_name=next_item["task_name"],
                subtask_name=next_item.get("subtask_name"),
                position=cursor + 1,
                total=len(items),
            ),
            reply_markup=keyboards.status_keyboard(next_item["id"]),
        )
        return

    await state.set_state(EveningUpdateState.waiting_for_note)
    await callback.message.edit_text(
        texts.pm_note_prompt(),
        reply_markup=keyboards.skip_note_keyboard(),
    )


@router.message(EveningUpdateState.waiting_for_note)
async def handle_note_input(
    message: Message,
    state: FSMContext,
    app_context: AppContext,
) -> None:
    await _finish_pm_update(
        state,
        app_context,
        message.from_user.id if message.from_user else 0,
        message.answer,
        message.text,
    )


@router.callback_query(EveningUpdateState.waiting_for_note, ActionCallback.filter(F.name == "skip_note"))
async def handle_skip_note(
    callback: CallbackQuery,
    state: FSMContext,
    app_context: AppContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    await _finish_pm_update(state, app_context, callback.from_user.id, callback.message.answer, None)


async def _start_morning_flow(
    response_message: Message,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
    telegram_user_id: int | None = None,
) -> None:
    user_id = telegram_user_id or (response_message.from_user.id if response_message.from_user else None)
    if user_id is None:
        return

    try:
        await app_context.access_service.ensure_group_member(bot, user_id)
    except GroupBindingError:
        await response_message.answer(texts.group_not_bound_text())
        return
    except MembershipError:
        await response_message.answer(texts.not_group_member_text())
        return

    async with app_context.db.session() as session:
        user = await UserRepository(session).get_by_telegram_id(user_id)
    if user is None:
        await response_message.answer(texts.start_required_text())
        return

    work_date = today_local(app_context.settings.timezone_info)
    await state.set_state(MorningSubmissionState.waiting_for_text)
    await response_message.answer(
        texts.morning_template_text(
            work_date=work_date,
            hashtag=app_context.settings.hashtag,
            mention_html=user_mention_html(user),
        )
    )


async def _start_pm_flow(
    response_message: Message,
    state: FSMContext,
    bot: Bot,
    app_context: AppContext,
    telegram_user_id: int | None = None,
) -> None:
    user_id = telegram_user_id or (response_message.from_user.id if response_message.from_user else None)
    if user_id is None:
        return

    try:
        await app_context.access_service.ensure_group_member(bot, user_id)
    except GroupBindingError:
        await response_message.answer(texts.group_not_bound_text())
        return
    except MembershipError:
        await response_message.answer(texts.not_group_member_text())
        return

    work_date = today_local(app_context.settings.timezone_info)
    submission = await app_context.submission_service.get_today_submission(user_id, work_date)
    if submission is None or not submission.items:
        await response_message.answer("Bugun uchun ertalabgi vazifalar topilmadi. Avval /today yuboring.")
        return

    items = [
        {
            "id": item.id,
            "project_name": item.project_name,
            "task_name": item.task_name,
            "subtask_name": item.subtask_name,
        }
        for item in submission.items
    ]
    await state.set_state(EveningUpdateState.choosing_status)
    await state.set_data(
        {
            "submission_id": submission.id,
            "work_date": work_date.isoformat(),
            "items": items,
            "cursor": 0,
            "statuses": {},
        }
    )
    first_item = items[0]
    await response_message.answer(
        texts.pm_item_prompt_parts(
            project_name=first_item["project_name"],
            task_name=first_item["task_name"],
            subtask_name=first_item.get("subtask_name"),
            position=1,
            total=len(items),
        ),
        reply_markup=keyboards.status_keyboard(first_item["id"]),
    )


async def _finish_pm_update(
    state: FSMContext,
    app_context: AppContext,
    telegram_user_id: int,
    responder,
    note: str | None,
) -> None:
    data = await state.get_data()
    if not data:
        await responder("Status sessiyasi topilmadi. /update ni qayta yuboring.")
        return

    work_date = date.fromisoformat(data["work_date"])
    statuses = {
        item_id: ItemStatus(status_value)
        for item_id, status_value in data.get("statuses", {}).items()
    }
    try:
        await app_context.submission_service.record_pm_statuses(
            telegram_user_id=telegram_user_id,
            work_date=work_date,
            status_map=statuses,
            final_note=note,
            submitted_at=local_now(app_context.settings.timezone_info),
        )
    except ValueError as exc:
        await responder(str(exc))
        return

    await app_context.digest_service.refresh_digest(work_date, DigestPeriod.PM)
    await state.clear()
    await responder(texts.pm_update_saved_text())
