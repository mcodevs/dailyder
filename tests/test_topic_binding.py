from datetime import date
from types import SimpleNamespace

import pytest

from dailyder_bot.domain.enums import DigestPeriod
from dailyder_bot.repositories.app_settings import GroupBinding
from dailyder_bot.services.access import AccessService
from dailyder_bot.services.digest import DigestService


class _FakeSessionContext:
    def __init__(self, session) -> None:
        self.session_obj = session

    async def __aenter__(self):
        return self.session_obj

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeTransactionContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def begin(self):
        return _FakeTransactionContext()


class _FakeDb:
    def session(self):
        return _FakeSessionContext(_FakeSession())


@pytest.mark.asyncio
async def test_access_service_falls_back_to_env_group_id(monkeypatch) -> None:
    settings = SimpleNamespace(group_chat_id=-1001, admin_user_ids=())
    service = AccessService(settings=settings, db=_FakeDb())  # type: ignore[arg-type]

    class _Repo:
        def __init__(self, session) -> None:
            self.session = session

        async def get_group_binding(self):
            return None

    monkeypatch.setattr("dailyder_bot.services.access.AppSettingsRepository", _Repo)

    binding = await service.get_group_binding()

    assert binding == GroupBinding(chat_id=-1001, title=None, message_thread_id=None)


@pytest.mark.asyncio
async def test_digest_service_sends_into_bound_topic(monkeypatch) -> None:
    calls: list[dict] = []

    class _Access:
        async def require_group_binding(self):
            return GroupBinding(chat_id=-100100, title="Dev group", message_thread_id=777)

    class _DigestRepo:
        async def get_or_create(self, work_date, period, group_chat_id):
            return SimpleNamespace(message_id=None)

        async def set_message_id(self, digest, message_id):
            digest.message_id = message_id

    class _SubmissionRepo:
        async def list_for_digest(self, work_date, only_pm_completed):
            return []

    class _Bot:
        async def send_message(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(message_id=99)

        async def edit_message_text(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr("dailyder_bot.services.digest.DigestRepository", lambda session: _DigestRepo())
    monkeypatch.setattr("dailyder_bot.services.digest.SubmissionRepository", lambda session: _SubmissionRepo())

    service = DigestService(
        settings=SimpleNamespace(hashtag="daily"),
        db=_FakeDb(),  # type: ignore[arg-type]
        bot=_Bot(),  # type: ignore[arg-type]
        access_service=_Access(),  # type: ignore[arg-type]
    )

    await service.ensure_digest(date(2026, 3, 12), DigestPeriod.AM)

    assert calls[0]["chat_id"] == -100100
    assert calls[0]["message_thread_id"] == 777
    assert "AM digest" in calls[0]["text"]


@pytest.mark.asyncio
async def test_digest_service_sends_without_thread_for_whole_group(monkeypatch) -> None:
    calls: list[dict] = []

    class _Access:
        async def require_group_binding(self):
            return GroupBinding(chat_id=-100100, title="Dev group", message_thread_id=None)

    class _DigestRepo:
        async def get_or_create(self, work_date, period, group_chat_id):
            return SimpleNamespace(message_id=None)

        async def set_message_id(self, digest, message_id):
            digest.message_id = message_id

    class _SubmissionRepo:
        async def list_for_digest(self, work_date, only_pm_completed):
            return []

    class _Bot:
        async def send_message(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(message_id=99)

    monkeypatch.setattr("dailyder_bot.services.digest.DigestRepository", lambda session: _DigestRepo())
    monkeypatch.setattr("dailyder_bot.services.digest.SubmissionRepository", lambda session: _SubmissionRepo())

    service = DigestService(
        settings=SimpleNamespace(hashtag="daily"),
        db=_FakeDb(),  # type: ignore[arg-type]
        bot=_Bot(),  # type: ignore[arg-type]
        access_service=_Access(),  # type: ignore[arg-type]
    )

    await service.ensure_digest(date(2026, 3, 12), DigestPeriod.AM)

    assert calls[0]["chat_id"] == -100100
    assert calls[0]["message_thread_id"] is None
