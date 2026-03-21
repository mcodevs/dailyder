from types import SimpleNamespace

import pytest

from dailyder_bot.bot.routers import admin as admin_router


class _FakeMessage:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=9001)
        self.chat = SimpleNamespace(id=9001, type="private")
        self.answer_calls: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answer_calls.append((text, reply_markup))


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
