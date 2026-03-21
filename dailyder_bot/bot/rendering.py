from __future__ import annotations

import logging
import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from dailyder_bot.container import AppContext
from dailyder_bot.utils.dates import local_now, today_local

UI_FLOW = "ui"
logger = logging.getLogger(__name__)

_EDIT_FALLBACK_ERRORS = (
    "message can't be edited",
    "message to edit not found",
    "message identifier is not specified",
    "there is no text in the message to edit",
)
_PARSE_ERROR_FRAGMENT = "can't parse entities"
_HTML_TAG_RE = re.compile(r"<[^>]+>")


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
    logger.info(
        "Render private screen requested",
        extra={
            "chat_id": chat_id,
            "user_id": user_id,
            "screen": screen,
            "preferred_message_id": preferred_message_id,
        },
    )
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
            if _PARSE_ERROR_FRAGMENT in error_text:
                logger.warning(
                    "Retrying edit_message_text without parse mode after entity parse error",
                    extra={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "screen": screen,
                        "error": str(exc),
                    },
                )
                try:
                    await app_context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=_plain_text(text),
                        reply_markup=reply_markup,
                        parse_mode=None,
                    )
                    rendered_message_id = message_id
                    break
                except TelegramBadRequest as retry_exc:
                    logger.warning(
                        "Plain-text edit retry failed, will send a new message",
                        extra={
                            "chat_id": chat_id,
                            "message_id": message_id,
                            "screen": screen,
                            "error": str(retry_exc),
                        },
                    )
            logger.warning(
                "Falling back to send_message after edit_message_text failed",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "screen": screen,
                    "error": str(exc),
                },
            )
            continue

    if rendered_message_id is None:
        try:
            sent = await app_context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if _PARSE_ERROR_FRAGMENT not in error_text:
                raise
            logger.warning(
                "Retrying send_message without parse mode after entity parse error",
                extra={
                    "chat_id": chat_id,
                    "screen": screen,
                    "error": str(exc),
                },
            )
            sent = await app_context.bot.send_message(
                chat_id=chat_id,
                text=_plain_text(text),
                reply_markup=reply_markup,
                parse_mode=None,
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


def _plain_text(text: str) -> str:
    return _HTML_TAG_RE.sub("", text)
