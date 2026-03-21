from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from dailyder_bot.container import AppContext
from dailyder_bot.utils.dates import local_now, today_local

UI_FLOW = "ui"

_EDIT_FALLBACK_ERRORS = (
    "message can't be edited",
    "message to edit not found",
    "message identifier is not specified",
    "there is no text in the message to edit",
)


async def render_private_screen(
    *,
    app_context: AppContext,
    user_id: str,
    chat_id: int,
    screen: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    preferred_message_id: int | None = None,
) -> int:
    now = local_now(app_context.settings.timezone_info)
    work_date = today_local(app_context.settings.timezone_info)
    session_state = await app_context.flow_session_service.get(
        user_id=user_id,
        flow=UI_FLOW,
        work_date=work_date,
        now=now,
    )

    candidate_ids: list[int] = []
    if preferred_message_id is not None:
        candidate_ids.append(preferred_message_id)
    if session_state and session_state.last_message_id is not None:
        if session_state.last_message_id not in candidate_ids:
            candidate_ids.append(session_state.last_message_id)

    rendered_message_id: int | None = None
    for message_id in candidate_ids:
        try:
            await app_context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
            rendered_message_id = message_id
            break
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if "message is not modified" in error_text:
                rendered_message_id = message_id
                break
            if any(fragment in error_text for fragment in _EDIT_FALLBACK_ERRORS):
                continue
            raise

    if rendered_message_id is None:
        sent = await app_context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )
        rendered_message_id = sent.message_id

    await app_context.flow_session_service.set(
        user_id=user_id,
        flow=UI_FLOW,
        work_date=work_date,
        step=screen,
        payload={"screen": screen},
        now=now,
        last_message_id=rendered_message_id,
    )
    return rendered_message_id
