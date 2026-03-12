from datetime import UTC, date, datetime

from dailyder_bot.db.models import DailySubmission, SubmissionItem, SubmissionItemStatus, User
from dailyder_bot.services.metrics import MetricsService


def _user(user_id: str, telegram_user_id: int, joined: date) -> User:
    return User(
        id=user_id,
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        first_name="Test",
        last_name=str(telegram_user_id),
        is_active=True,
        created_in_group_id=-100,
        joined_at=datetime.combine(joined, datetime.min.time(), tzinfo=UTC),
        last_seen_at=datetime.now(UTC),
    )


def _submission(
    submission_id: str,
    user: User,
    work_date: date,
    *,
    pm_done: bool,
    status: str | None,
) -> DailySubmission:
    submission = DailySubmission(
        id=submission_id,
        user_id=user.id,
        user=user,
        work_date=work_date,
        hashtag="daily",
        am_submitted_at=datetime.now(UTC),
        pm_submitted_at=datetime.now(UTC) if pm_done else None,
    )
    item = SubmissionItem(
        id=f"item-{submission_id}",
        submission_id=submission_id,
        sort_order=1,
        project_name="Project",
        task_name="Task",
        subtask_name=None,
    )
    if status:
        item.status = SubmissionItemStatus(
            id=f"status-{submission_id}",
            submission_item_id=item.id,
            status=status,
        )
    submission.items = [item]
    return submission


def test_metrics_service_builds_expected_counts() -> None:
    service = MetricsService(db=None)  # type: ignore[arg-type]
    user = _user("u1", 1001, date(2026, 3, 10))
    submissions = [
        _submission("s1", user, date(2026, 3, 10), pm_done=True, status="completed"),
        _submission("s2", user, date(2026, 3, 11), pm_done=False, status=None),
    ]

    snapshots = service._build_snapshots(  # noqa: SLF001
        users=[user],
        submissions=submissions,
        workdays=[date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)],
    )

    snapshot = snapshots[0]
    assert snapshot.expected_workdays == 3
    assert snapshot.am_submitted == 2
    assert snapshot.pm_submitted == 1
    assert snapshot.missed_am == 1
    assert snapshot.missed_pm == 1
    assert snapshot.completed == 1

