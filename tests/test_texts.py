from datetime import UTC, date, datetime

from dailyder_bot.bot import texts
from dailyder_bot.db.models import DailySubmission, SubmissionItem, SubmissionItemStatus, SubmissionSubtask, User


def test_render_am_digest_contains_mentions_and_items() -> None:
    user = User(
        id="u1",
        telegram_user_id=101,
        username="devuser",
        first_name="Dev",
        last_name="User",
        is_active=True,
        created_in_group_id=-100,
        joined_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    submission = DailySubmission(
        id="s1",
        user_id="u1",
        user=user,
        work_date=date(2026, 3, 12),
        hashtag="daily",
        am_submitted_at=datetime.now(UTC),
    )
    submission.items = [
        SubmissionItem(
            id="i1",
            submission_id="s1",
            sort_order=1,
            project_name="TvRain",
            task_name="Release",
            subtask_name=None,
        )
    ]

    rendered = texts.render_am_digest(date(2026, 3, 12), "daily", [submission])

    assert "AM digest" in rendered
    assert "@devuser" in rendered
    assert "TvRain" in rendered
    assert "Release" in rendered


def test_render_pm_digest_contains_status_emoji_and_note() -> None:
    user = User(
        id="u2",
        telegram_user_id=202,
        username=None,
        first_name="Ali",
        last_name="Valiyev",
        is_active=True,
        created_in_group_id=-100,
        joined_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    submission = DailySubmission(
        id="s2",
        user_id="u2",
        user=user,
        work_date=date(2026, 3, 12),
        hashtag="daily",
        am_submitted_at=datetime.now(UTC),
        pm_submitted_at=datetime.now(UTC),
        final_note="Release AppStore reviewda turibdi",
    )
    item = SubmissionItem(
        id="i2",
        submission_id="s2",
        sort_order=1,
        project_name="MedPay",
        task_name="Release",
        subtask_name="AppStore\nSmoke test",
    )
    item.status = SubmissionItemStatus(id="st2", submission_item_id="i2", status="completed")
    item.subtasks = [
        SubmissionSubtask(
            id="sub-1",
            submission_item_id="i2",
            sort_order=1,
            subtask_name="AppStore",
            status="warning",
        ),
        SubmissionSubtask(
            id="sub-2",
            submission_item_id="i2",
            sort_order=2,
            subtask_name="Smoke test",
            status="completed",
        ),
    ]
    submission.items = [item]

    rendered = texts.render_pm_digest(date(2026, 3, 12), "daily", [submission])

    assert "PM digest" in rendered
    assert "✅" in rendered
    assert "MedPay" in rendered
    assert "Release ✅" in rendered
    assert "Izoh" in rendered
    assert "AppStore" in rendered
    assert "Smoke test" in rendered
    assert "⚠️ AppStore" in rendered


def test_help_and_welcome_texts_do_not_expose_daily_commands() -> None:
    welcome = texts.welcome_text(is_admin=False)
    help_text = texts.help_text(is_admin=True)

    for forbidden in ("/today", "/update", "/help", "/admin"):
        assert forbidden not in welcome
        assert forbidden not in help_text
