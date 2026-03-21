import asyncio
from collections import Counter
from datetime import UTC, date, datetime

import pytest

from dailyder_bot.db.models import User
from dailyder_bot.services.reminders import ReminderService


class _FakeSessionContext:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeDb:
    def __init__(self, session) -> None:
        self.session_obj = session

    def session(self):
        return _FakeSessionContext(self.session_obj)


class _FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = users

    async def list_active(self) -> list[User]:
        return list(self.users)


class _FakeAccessService:
    def __init__(self, member_ids: set[int]) -> None:
        self.member_ids = member_ids
        self.current_in_flight = 0
        self.max_in_flight = 0

    async def require_bound_group_id(self) -> int:
        return -100123

    async def is_group_member(self, bot, group_chat_id: int, telegram_user_id: int) -> bool:
        self.current_in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.current_in_flight)
        await asyncio.sleep(0.01)
        self.current_in_flight -= 1
        return telegram_user_id in self.member_ids


class _FakeBot:
    def __init__(self, failing_chat_ids: set[int] | None = None) -> None:
        self.failing_chat_ids = failing_chat_ids or set()
        self.attempted_chat_ids: list[int] = []
        self.sent_chat_ids: list[int] = []
        self.calls: list[dict] = []

    async def send_message(self, *, chat_id: int, text: str, reply_markup) -> None:
        self.attempted_chat_ids.append(chat_id)
        if chat_id in self.failing_chat_ids:
            raise RuntimeError(f"send failed for {chat_id}")
        self.sent_chat_ids.append(chat_id)
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )


class _FakeSubmissionService:
    def __init__(self, submitted_user_ids: set[int] | None = None) -> None:
        self.submitted_user_ids = submitted_user_ids or set()
        self.calls: list[tuple[list[int], date]] = []

    async def get_today_submission_map(self, telegram_user_ids: list[int], work_date: date):
        self.calls.append((list(telegram_user_ids), work_date))
        return {
            telegram_user_id: object()
            for telegram_user_id in telegram_user_ids
            if telegram_user_id in self.submitted_user_ids
        }


def _user(telegram_user_id: int) -> User:
    return User(
        id=f"user-{telegram_user_id}",
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        first_name="Test",
        last_name=str(telegram_user_id),
        is_active=True,
        created_in_group_id=-100,
        joined_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _build_service(
    monkeypatch,
    users: list[User],
    access_service: _FakeAccessService,
    bot: _FakeBot,
    submission_service: _FakeSubmissionService | None = None,
) -> ReminderService:
    monkeypatch.setattr(
        "dailyder_bot.services.reminders.UserRepository",
        lambda session: _FakeUserRepository(users),
    )
    return ReminderService(
        settings=type("Settings", (), {"hashtag": "daily"})(),
        db=_FakeDb(object()),  # type: ignore[arg-type]
        bot=bot,  # type: ignore[arg-type]
        access_service=access_service,  # type: ignore[arg-type]
        submission_service=submission_service or _FakeSubmissionService(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_send_morning_reminders_sends_once_per_eligible_user(monkeypatch) -> None:
    users = [_user(1001), _user(1002), _user(1003)]
    access_service = _FakeAccessService({1001, 1002, 1003})
    bot = _FakeBot()
    service = _build_service(monkeypatch, users, access_service, bot)

    sent_count = await service.send_morning_reminders(date(2026, 3, 17))

    assert sent_count == 3
    assert Counter(bot.sent_chat_ids) == Counter({1001: 1, 1002: 1, 1003: 1})


@pytest.mark.asyncio
async def test_send_morning_reminders_continues_after_send_failure(monkeypatch) -> None:
    users = [_user(1001), _user(1002), _user(1003)]
    access_service = _FakeAccessService({1001, 1002, 1003})
    bot = _FakeBot(failing_chat_ids={1002})
    service = _build_service(monkeypatch, users, access_service, bot)

    sent_count = await service.send_morning_reminders(date(2026, 3, 17))

    assert sent_count == 2
    assert Counter(bot.attempted_chat_ids) == Counter({1001: 1, 1002: 1, 1003: 1})
    assert Counter(bot.sent_chat_ids) == Counter({1001: 1, 1003: 1})


@pytest.mark.asyncio
async def test_send_morning_reminders_respects_concurrency_cap(monkeypatch) -> None:
    users = [_user(telegram_user_id) for telegram_user_id in range(1001, 1011)]
    access_service = _FakeAccessService({user.telegram_user_id for user in users})
    bot = _FakeBot()
    service = _build_service(monkeypatch, users, access_service, bot)

    sent_count = await service.send_morning_reminders(date(2026, 3, 17))

    assert sent_count == len(users)
    assert 1 < access_service.max_in_flight <= service.MAX_CONCURRENT_REMINDERS


@pytest.mark.asyncio
async def test_send_pm_reminders_batches_submission_lookup_and_respects_filter(monkeypatch) -> None:
    users = [_user(2001), _user(2002), _user(2003)]
    access_service = _FakeAccessService({2001, 2002, 2003})
    bot = _FakeBot()
    submission_service = _FakeSubmissionService({2002})
    service = _build_service(monkeypatch, users, access_service, bot, submission_service)

    sent_count = await service.send_pm_reminders(
        date(2026, 3, 17),
        only_user_ids={2002, 2003},
    )

    assert sent_count == 2
    assert submission_service.calls == [([2002, 2003], date(2026, 3, 17))]

    messages_by_chat_id = {call["chat_id"]: call for call in bot.calls}
    assert messages_by_chat_id[2002]["reply_markup"].inline_keyboard[0][0].text == "Statuslarni yangilash"
    assert messages_by_chat_id[2003]["reply_markup"].inline_keyboard[0][0].text == "Avval vazifani yuborish"
