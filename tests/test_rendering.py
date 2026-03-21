from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText

from dailyder_bot.bot.rendering import render_private_screen


class _FakeFlowSessionService:
    def __init__(self, last_message_id: int | None = None) -> None:
        self.last_message_id = last_message_id
        self.saved: dict | None = None

    async def get(self, *, user_id: str, flow: str, work_date, now):
        if self.last_message_id is None:
            return None
        return SimpleNamespace(last_message_id=self.last_message_id)

    async def set(self, **kwargs):
        self.last_message_id = kwargs["last_message_id"]
        self.saved = kwargs
        return SimpleNamespace(last_message_id=self.last_message_id)


class _FakeBot:
    def __init__(self, *, edit_error: Exception | None = None) -> None:
        self.edit_error = edit_error
        self.edit_calls: list[dict] = []
        self.send_calls: list[dict] = []

    async def edit_message_text(self, **kwargs):
        self.edit_calls.append(kwargs)
        if self.edit_error is not None:
            raise self.edit_error
        return True

    async def send_message(self, **kwargs):
        self.send_calls.append(kwargs)
        return SimpleNamespace(message_id=901)


def _context(*, flow_session_service: _FakeFlowSessionService, bot: _FakeBot):
    return SimpleNamespace(
        bot=bot,
        flow_session_service=flow_session_service,
        settings=SimpleNamespace(timezone_info=ZoneInfo("Asia/Tashkent")),
    )


@pytest.mark.asyncio
async def test_render_private_screen_edits_existing_message() -> None:
    flow_session_service = _FakeFlowSessionService(last_message_id=55)
    bot = _FakeBot()

    message_id = await render_private_screen(
        app_context=_context(flow_session_service=flow_session_service, bot=bot),  # type: ignore[arg-type]
        user_id="user-1",
        chat_id=1001,
        screen="today_summary",
        text="Updated",
        preferred_message_id=77,
    )

    assert message_id == 77
    assert bot.edit_calls == [
        {
            "chat_id": 1001,
            "message_id": 77,
            "text": "Updated",
            "reply_markup": None,
        }
    ]
    assert bot.send_calls == []
    assert flow_session_service.saved is not None
    assert flow_session_service.saved["last_message_id"] == 77


@pytest.mark.asyncio
async def test_render_private_screen_falls_back_to_send_on_edit_error() -> None:
    flow_session_service = _FakeFlowSessionService(last_message_id=55)
    bot = _FakeBot(
        edit_error=TelegramBadRequest(
            method=EditMessageText(chat_id=1001, message_id=55, text="Updated"),
            message="message can't be edited",
        )
    )

    message_id = await render_private_screen(
        app_context=_context(flow_session_service=flow_session_service, bot=bot),  # type: ignore[arg-type]
        user_id="user-1",
        chat_id=1001,
        screen="today_summary",
        text="Updated",
    )

    assert message_id == 901
    assert bot.edit_calls[0]["message_id"] == 55
    assert bot.send_calls == [
        {
            "chat_id": 1001,
            "text": "Updated",
            "reply_markup": None,
        }
    ]
    assert flow_session_service.saved is not None
    assert flow_session_service.saved["last_message_id"] == 901
