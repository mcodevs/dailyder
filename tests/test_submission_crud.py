from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from dailyder_bot.db.models import DeveloperWarning, SubmissionItem, User
from dailyder_bot.db.session import DatabaseSessionManager
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.domain.parser import MorningSubmissionParser
from dailyder_bot.services.submissions import SubmissionService


async def _seed_user(db: DatabaseSessionManager, telegram_user_id: int = 1001) -> User:
    user = User(
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
    async with db.session() as session:
        async with session.begin():
            session.add(user)
    return user


def _service(db: DatabaseSessionManager) -> SubmissionService:
    return SubmissionService(
        settings=SimpleNamespace(hashtag="daily"),
        db=db,
        parser=MorningSubmissionParser(),
    )


@pytest.mark.asyncio
async def test_submission_service_draft_crud_resets_pm_update(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'submission.db'}")
    await db.create_all()
    try:
        await _seed_user(db)
        service = _service(db)
        work_date = date(2026, 3, 18)
        submitted_at = datetime(2026, 3, 18, 9, 0, tzinfo=UTC)
        pm_at = datetime(2026, 3, 18, 17, 0, tzinfo=UTC)

        created = await service.add_draft_item(
            telegram_user_id=1001,
            work_date=work_date,
            project_name="TvRain",
            task_name="Release",
            subtask_names=["Smoke test"],
        )
        assert created.submission.am_submitted_at is None
        assert created.pm_reset is False

        submitted = await service.submit_morning_draft(
            telegram_user_id=1001,
            work_date=work_date,
            submitted_at=submitted_at,
        )
        assert submitted.am_submitted_at == submitted_at

        await service.record_pm_statuses(
            telegram_user_id=1001,
            work_date=work_date,
            status_map={submitted.items[0].id: ItemStatus.COMPLETED},
            final_note="Done",
            submitted_at=pm_at,
        )
        await service.record_subtask_status(
            telegram_user_id=1001,
            work_date=work_date,
            item_id=submitted.items[0].id,
            subtask_id=submitted.items[0].subtasks[0].id,
            status=ItemStatus.WARNING,
        )

        updated = await service.update_draft_item(
            telegram_user_id=1001,
            work_date=work_date,
            item_id=submitted.items[0].id,
            project_name="TvRain",
            task_name="Release v2",
            subtask_names=["Smoke test", "Publish"],
        )

        assert updated.pm_reset is True
        assert updated.submission.am_submitted_at is not None
        assert updated.submission.am_submitted_at.replace(tzinfo=UTC) == submitted_at
        assert updated.submission.pm_submitted_at is None
        assert updated.submission.final_note is None
        assert updated.submission.items[0].task_name == "Release v2"
        assert updated.submission.items[0].status is None
        assert [subtask.status for subtask in updated.submission.items[0].subtasks] == [None, None]
    finally:
        await db.dispose()


@pytest.mark.asyncio
async def test_submission_service_import_replaces_existing_draft(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'submission-import.db'}")
    await db.create_all()
    try:
        await _seed_user(db, telegram_user_id=1002)
        service = _service(db)
        work_date = date(2026, 3, 18)

        await service.add_draft_item(
            telegram_user_id=1002,
            work_date=work_date,
            project_name="OldProject",
            task_name="OldTask",
            subtask_names=[],
        )

        imported = await service.import_draft_from_text(
            telegram_user_id=1002,
            work_date=work_date,
            raw_text=(
                "Project: TvRain\n"
                "Task: IOS bug fix\n"
                "Subtask: iphone bug\n"
            ),
        )

        assert imported.submission.items[0].project_name == "TvRain"
        assert imported.submission.items[0].task_name == "IOS bug fix"
        assert imported.submission.items[0].subtask_names == ["iphone bug"]
        assert len(imported.submission.items) == 1
    finally:
        await db.dispose()


@pytest.mark.asyncio
async def test_get_submitted_today_submission_hides_draft_until_submit(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'submission-visibility.db'}")
    await db.create_all()
    try:
        await _seed_user(db, telegram_user_id=1003)
        service = _service(db)
        work_date = date(2026, 3, 18)

        await service.add_draft_item(
            telegram_user_id=1003,
            work_date=work_date,
            project_name="TvRain",
            task_name="Draft task",
            subtask_names=[],
        )

        assert await service.get_submitted_today_submission(1003, work_date) is None

        await service.submit_morning_draft(
            telegram_user_id=1003,
            work_date=work_date,
            submitted_at=datetime(2026, 3, 18, 9, 0, tzinfo=UTC),
        )

        assert await service.get_submitted_today_submission(1003, work_date) is not None
    finally:
        await db.dispose()


@pytest.mark.asyncio
async def test_submission_service_persists_subtask_statuses_independently(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'submission-subtasks.db'}")
    await db.create_all()
    try:
        await _seed_user(db, telegram_user_id=1004)
        service = _service(db)
        work_date = date(2026, 3, 18)

        created = await service.add_draft_item(
            telegram_user_id=1004,
            work_date=work_date,
            project_name="TvRain",
            task_name="Release",
            subtask_names=["Draft release note", "Validate smoke test"],
        )
        item = created.submission.items[0]

        assert [subtask.subtask_name for subtask in item.subtasks] == [
            "Draft release note",
            "Validate smoke test",
        ]
        assert [subtask.status for subtask in item.subtasks] == [None, None]
        assert item.status is None

        updated = await service.record_subtask_status(
            telegram_user_id=1004,
            work_date=work_date,
            item_id=item.id,
            subtask_id=item.subtasks[1].id,
            status=ItemStatus.WARNING,
        )
        updated_item = updated.items[0]
        assert [subtask.status for subtask in updated_item.subtasks] == [None, "warning"]
        assert updated_item.status is None

        await service.submit_morning_draft(
            telegram_user_id=1004,
            work_date=work_date,
            submitted_at=datetime(2026, 3, 18, 9, 0, tzinfo=UTC),
        )

        pm_updated = await service.record_pm_statuses(
            telegram_user_id=1004,
            work_date=work_date,
            status_map={updated_item.id: ItemStatus.COMPLETED},
            final_note="Done",
            submitted_at=datetime(2026, 3, 18, 17, 0, tzinfo=UTC),
        )
        pm_item = pm_updated.items[0]
        assert pm_item.status is not None
        assert pm_item.status.status == ItemStatus.COMPLETED.value
        assert [subtask.status for subtask in pm_item.subtasks] == [None, "warning"]
    finally:
        await db.dispose()


def test_submission_item_subtask_names_falls_back_to_legacy_text() -> None:
    item = SubmissionItem(
        id="item-1",
        submission_id="submission-1",
        sort_order=1,
        project_name="TvRain",
        task_name="Release",
        subtask_name="Draft release note\nValidate smoke test",
    )

    assert item.subtask_names == ["Draft release note", "Validate smoke test"]


@pytest.mark.asyncio
async def test_developer_warning_can_be_persisted(tmp_path) -> None:
    db = DatabaseSessionManager(f"sqlite+aiosqlite:///{tmp_path / 'warnings.db'}")
    await db.create_all()
    try:
        user = await _seed_user(db, telegram_user_id=1005)
        warning = DeveloperWarning(
            id="warning-1",
            developer_user_id=user.id,
            admin_telegram_user_id=9001,
            group_chat_id=-100123,
            reason="Please include a short progress comment in the AM digest.",
        )
        async with db.session() as session:
            async with session.begin():
                session.add(warning)

        async with db.session() as session:
            stored = await session.get(DeveloperWarning, "warning-1")

        assert stored is not None
        assert stored.developer_user_id == user.id
        assert stored.admin_telegram_user_id == 9001
        assert stored.group_chat_id == -100123
        assert stored.reason.startswith("Please include")
    finally:
        await db.dispose()
