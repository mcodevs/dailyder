from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dailyder_bot.bot.routers import user as user_router


class _AsyncContext:
    def __init__(self, value) -> None:
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSession:
    def begin(self):
        return _AsyncContext(None)


class _FakeDb:
    def session(self):
        return _AsyncContext(_FakeSession())


class _FakeMessage:
    def __init__(self, *, user_id: int = 9001, message_id: int = 33) -> None:
        self.from_user = SimpleNamespace(
            id=user_id,
            username="devuser",
            first_name="Dev",
            last_name="User",
        )
        self.chat = SimpleNamespace(id=user_id, type="private")
        self.message_id = message_id
        self.answer_calls: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answer_calls.append((text, reply_markup))


class _FakeCallback:
    def __init__(self, *, user_id: int = 9001, message_id: int = 55) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _FakeMessage(user_id=user_id, message_id=message_id)
        self.answer_count = 0

    async def answer(self) -> None:
        self.answer_count += 1


@pytest.mark.asyncio
async def test_handle_start_renders_today_summary_without_sending_welcome_message(monkeypatch) -> None:
    message = _FakeMessage()
    render_calls: list[dict] = []

    class _FakeUserRepository:
        def __init__(self, session) -> None:
            self.session = session

        async def upsert_from_telegram(self, *, telegram_user, joined_at, created_in_group_id):
            assert telegram_user.id == 9001
            assert created_in_group_id == -100
            return SimpleNamespace(id="user-1")

    async def _fake_ensure_group_member(bot, telegram_user_id: int):
        assert telegram_user_id == 9001
        return -100

    async def _fake_get_flow(**kwargs):
        return None

    async def _fake_get_today_submission(*args, **kwargs):
        return None

    async def _fake_render_private_screen(**kwargs):
        render_calls.append(kwargs)
        return 101

    monkeypatch.setattr(user_router, "UserRepository", _FakeUserRepository)
    monkeypatch.setattr(user_router, "render_private_screen", _fake_render_private_screen)

    app_context = SimpleNamespace(
        settings=SimpleNamespace(timezone_info=ZoneInfo("Asia/Tashkent")),
        access_service=SimpleNamespace(
            ensure_group_member=_fake_ensure_group_member,
            is_admin=lambda telegram_user_id: False,
        ),
        db=_FakeDb(),
        flow_session_service=SimpleNamespace(get=_fake_get_flow),
        submission_service=SimpleNamespace(get_today_submission=_fake_get_today_submission),
    )

    await user_router.handle_start(message, SimpleNamespace(), app_context)  # type: ignore[arg-type]

    assert message.answer_calls == []
    assert render_calls
    assert render_calls[0]["screen"] == "today_summary"
    assert "Dailyder botga xush kelibsiz." in render_calls[0]["text"]
    assert "Bugungi tasklar" in render_calls[0]["text"]
    assert render_calls[0]["reply_markup"] is not None


@pytest.mark.asyncio
async def test_menu_today_callback_shows_today_summary(monkeypatch) -> None:
    callback = _FakeCallback()
    summary_calls: list[tuple] = []

    async def _fake_get_user_record(app_context, telegram_user_id: int):
        assert telegram_user_id == 9001
        return SimpleNamespace(id="user-1")

    async def _fake_show_today_summary(message, app_context, user_id: str, telegram_user_id: int):
        summary_calls.append((message.message_id, user_id, telegram_user_id))

    monkeypatch.setattr(user_router, "_get_user_record", _fake_get_user_record)
    monkeypatch.setattr(user_router, "_show_today_summary", _fake_show_today_summary)

    await user_router.handle_menu_today_callback(callback, SimpleNamespace())  # type: ignore[arg-type]

    assert callback.answer_count == 1
    assert summary_calls == [(55, "user-1", 9001)]


@pytest.mark.asyncio
async def test_menu_pm_callback_shows_pm_summary(monkeypatch) -> None:
    callback = _FakeCallback()
    summary_calls: list[tuple] = []

    async def _fake_get_user_record(app_context, telegram_user_id: int):
        assert telegram_user_id == 9001
        return SimpleNamespace(id="user-1")

    async def _fake_show_pm_summary(message, app_context, user_id: str, telegram_user_id: int):
        summary_calls.append((message.message_id, user_id, telegram_user_id))

    monkeypatch.setattr(user_router, "_get_user_record", _fake_get_user_record)
    monkeypatch.setattr(user_router, "_show_pm_summary", _fake_show_pm_summary)

    await user_router.handle_menu_pm_callback(callback, SimpleNamespace())  # type: ignore[arg-type]

    assert callback.answer_count == 1
    assert summary_calls == [(55, "user-1", 9001)]


@pytest.mark.asyncio
async def test_menu_help_callback_renders_help_screen(monkeypatch) -> None:
    callback = _FakeCallback()
    render_calls: list[dict] = []

    async def _fake_get_user_record(app_context, telegram_user_id: int):
        assert telegram_user_id == 9001
        return SimpleNamespace(id="user-1")

    async def _fake_render_screen(message, app_context, user_id: str, **kwargs):
        render_calls.append({"message_id": message.message_id, "user_id": user_id, **kwargs})

    monkeypatch.setattr(user_router, "_get_user_record", _fake_get_user_record)
    monkeypatch.setattr(user_router, "_render_screen", _fake_render_screen)

    app_context = SimpleNamespace(
        access_service=SimpleNamespace(is_admin=lambda telegram_user_id: False),
    )

    await user_router.handle_menu_help_callback(callback, app_context)  # type: ignore[arg-type]

    assert callback.answer_count == 1
    assert render_calls
    assert render_calls[0]["message_id"] == 55
    assert render_calls[0]["user_id"] == "user-1"
    assert render_calls[0]["screen"] == "help"
    assert render_calls[0]["preferred_message_id"] == 55


@pytest.mark.asyncio
async def test_render_screen_user_message_forces_new_visible_message(monkeypatch) -> None:
    message = _FakeMessage(user_id=9001, message_id=77)
    render_calls: list[dict] = []

    async def _fake_render_private_screen(**kwargs):
        render_calls.append(kwargs)
        return 777

    monkeypatch.setattr(user_router, "render_private_screen", _fake_render_private_screen)

    app_context = SimpleNamespace(
        access_service=SimpleNamespace(is_admin=lambda telegram_user_id: False),
    )

    await user_router._render_screen(  # type: ignore[attr-defined]
        message,
        app_context,
        "user-1",
        screen="today_summary",
        text="screen body",
    )

    assert render_calls
    assert render_calls[0]["preferred_message_id"] is None
    assert render_calls[0]["include_last_message_candidate"] is False
