from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dailyder_bot.bot import texts
from dailyder_bot.bot.routers import admin as admin_router


class _FakeMessage:
    def __init__(
        self,
        *,
        from_user_id: int = 9001,
        message_id: int = 44,
        message_author_id: int | None = None,
    ) -> None:
        self.from_user = SimpleNamespace(id=from_user_id if message_author_id is None else message_author_id)
        self.chat = SimpleNamespace(id=9001, type="private")
        self.message_id = message_id
        self.answer_calls: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answer_calls.append((text, reply_markup))


class _FakeCallback:
    def __init__(self, *, user_id: int = 9001, message_author_id: int = 777, message_id: int = 55) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _FakeMessage(
            from_user_id=user_id,
            message_id=message_id,
            message_author_id=message_author_id,
        )
        self.answer_count = 0

    async def answer(self) -> None:
        self.answer_count += 1


@pytest.mark.asyncio
async def test_handle_admin_menu_registers_current_private_screen(monkeypatch) -> None:
    message = _FakeMessage()
    render_calls: list[dict] = []

    async def _fake_render_private_screen(**kwargs):
        render_calls.append(kwargs)
        return 101

    async def _fake_get_private_user_id(app_context, message):
        return "user-1"

    monkeypatch.setattr(admin_router, "render_private_screen", _fake_render_private_screen)
    monkeypatch.setattr(admin_router, "_get_private_user_id", _fake_get_private_user_id)

    app_context = SimpleNamespace(
        access_service=SimpleNamespace(is_admin=lambda user_id: True),
    )

    await admin_router.handle_admin_menu(message, app_context)  # type: ignore[arg-type]

    assert message.answer_calls == []
    assert render_calls
    assert render_calls[0]["user_id"] == "user-1"
    assert render_calls[0]["chat_id"] == 9001
    assert render_calls[0]["screen"] == "admin_menu"


@pytest.mark.asyncio
async def test_menu_admin_callback_requires_admin(monkeypatch) -> None:
    callback = _FakeCallback()
    render_calls: list[dict] = []

    async def _fake_render_private_screen(**kwargs):
        render_calls.append(kwargs)
        return 101

    monkeypatch.setattr(admin_router, "render_private_screen", _fake_render_private_screen)

    app_context = SimpleNamespace(
        access_service=SimpleNamespace(is_admin=lambda user_id: False),
    )

    await admin_router.handle_menu_admin_callback(callback, app_context)  # type: ignore[arg-type]

    assert callback.answer_count == 1
    assert callback.message.answer_calls == [(texts.admin_only_text(), None)]
    assert render_calls == []


@pytest.mark.asyncio
async def test_menu_admin_callback_renders_current_private_screen(monkeypatch) -> None:
    callback = _FakeCallback()
    render_calls: list[dict] = []

    async def _fake_render_private_screen(**kwargs):
        render_calls.append(kwargs)
        return 101

    async def _fake_get_private_user_id(app_context, telegram_user_id: int):
        assert telegram_user_id == 9001
        return "user-1"

    monkeypatch.setattr(admin_router, "render_private_screen", _fake_render_private_screen)
    monkeypatch.setattr(admin_router, "_get_private_user_id_by_telegram_id", _fake_get_private_user_id)

    app_context = SimpleNamespace(
        access_service=SimpleNamespace(is_admin=lambda user_id: True),
    )

    await admin_router.handle_menu_admin_callback(callback, app_context)  # type: ignore[arg-type]

    assert callback.answer_count == 1
    assert callback.message.answer_calls == []
    assert render_calls == [
        {
            "app_context": app_context,
            "user_id": "user-1",
            "chat_id": 9001,
            "screen": "admin_menu",
            "text": texts.admin_menu_text(),
            "reply_markup": render_calls[0]["reply_markup"],
            "preferred_message_id": 55,
        }
    ]


@pytest.mark.asyncio
async def test_handle_admin_actions_uses_callback_user_id_for_private_render(monkeypatch) -> None:
    callback = _FakeCallback(user_id=9001, message_author_id=123456)
    render_calls: list[dict] = []

    async def _fake_render_private_screen(**kwargs):
        render_calls.append(kwargs)
        return 101

    async def _fake_get_private_user_id(app_context, telegram_user_id: int):
        assert telegram_user_id == 9001
        return "user-1"

    async def _fake_readiness_report():
        return "All green"

    monkeypatch.setattr(admin_router, "render_private_screen", _fake_render_private_screen)
    monkeypatch.setattr(admin_router, "_get_private_user_id_by_telegram_id", _fake_get_private_user_id)

    app_context = SimpleNamespace(
        access_service=SimpleNamespace(is_admin=lambda user_id: True),
        admin_service=SimpleNamespace(readiness_report=_fake_readiness_report),
        settings=SimpleNamespace(timezone_info=ZoneInfo("Asia/Tashkent")),
    )

    await admin_router.handle_admin_actions(
        callback,
        SimpleNamespace(action="readiness"),
        app_context,
    )  # type: ignore[arg-type]

    assert callback.answer_count == 1
    assert callback.message.answer_calls == []
    assert render_calls
    assert render_calls[0]["user_id"] == "user-1"
    assert render_calls[0]["preferred_message_id"] == 55
    assert render_calls[0]["text"] == "All green"
