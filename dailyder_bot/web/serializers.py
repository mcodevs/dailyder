from __future__ import annotations

from datetime import date, datetime

from dailyder_bot.db.models import DailySubmission, SubmissionItem, SubmissionSubtask, User
from dailyder_bot.repositories.app_settings import GroupBinding
from dailyder_bot.services.admin import IssuedWarning, PendingSnapshot, ReadinessSnapshot
from dailyder_bot.services.metrics import MetricsReportSnapshot, UserMetricsSnapshot
from dailyder_bot.utils.telegram import user_display_name
from dailyder_bot.web.auth import ApiPrincipal


def serialize_binding(binding: GroupBinding | None) -> dict | None:
    if binding is None:
        return None
    return {
        "chatId": binding.chat_id,
        "title": binding.title,
        "messageThreadId": binding.message_thread_id,
    }


def serialize_me(
    *,
    principal: ApiPrincipal,
    user: User | None,
    binding: GroupBinding | None,
    is_group_member: bool,
) -> dict:
    return {
        "telegramUserId": principal.telegram_user_id,
        "username": principal.username,
        "displayName": build_display_name(principal, user),
        "isAdmin": principal.is_admin,
        "isOnboarded": user is not None,
        "isGroupBound": binding is not None,
        "isGroupMember": is_group_member,
        "groupBinding": serialize_binding(binding),
        "authMode": principal.auth_mode,
    }


def serialize_dashboard(
    *,
    principal: ApiPrincipal,
    user: User | None,
    binding: GroupBinding | None,
    is_group_member: bool,
    work_date: date,
    submission: DailySubmission | None,
) -> dict:
    return {
        "workDate": work_date.isoformat(),
        "viewer": serialize_me(
            principal=principal,
            user=user,
            binding=binding,
            is_group_member=is_group_member,
        ),
        "submissionStatus": {
            "hasDraft": submission is not None and bool(submission.items),
            "amSubmitted": submission is not None and submission.am_submitted_at is not None,
            "pmSubmitted": submission is not None and submission.pm_submitted_at is not None,
            "itemCount": len(submission.items) if submission is not None else 0,
        },
    }


def serialize_submission(submission: DailySubmission | None, *, work_date: date) -> dict:
    return {
        "workDate": work_date.isoformat(),
        "submission": serialize_submission_detail(submission),
    }


def serialize_submission_detail(submission: DailySubmission | None) -> dict | None:
    if submission is None:
        return None
    return {
        "id": submission.id,
        "hashtag": submission.hashtag,
        "amSubmittedAt": serialize_datetime(submission.am_submitted_at),
        "pmSubmittedAt": serialize_datetime(submission.pm_submitted_at),
        "finalNote": submission.final_note,
        "items": [serialize_submission_item(item) for item in submission.items],
    }


def serialize_submission_item(item: SubmissionItem) -> dict:
    return {
        "id": item.id,
        "sortOrder": item.sort_order,
        "projectName": item.project_name,
        "taskName": item.task_name,
        "status": item.status.status if item.status is not None else None,
        "subtasks": [serialize_submission_subtask(subtask) for subtask in item.subtasks],
        "subtaskNames": item.subtask_names,
    }


def serialize_submission_subtask(subtask: SubmissionSubtask) -> dict:
    return {
        "id": subtask.id,
        "sortOrder": subtask.sort_order,
        "name": subtask.subtask_name,
        "status": subtask.status,
    }


def serialize_readiness_snapshot(snapshot: ReadinessSnapshot) -> dict:
    return {
        "groupBinding": serialize_binding(snapshot.binding),
        "adminCount": snapshot.admin_count,
        "onboardedUserCount": snapshot.onboarded_user_count,
        "amScheduler": snapshot.am_scheduler,
        "pmScheduler": snapshot.pm_scheduler,
    }


def serialize_pending_snapshot(snapshot: PendingSnapshot) -> dict:
    return {
        "workDate": snapshot.work_date.isoformat(),
        "amPendingUsers": [serialize_user_summary(user) for user in snapshot.am_pending_users],
        "pmPendingUsers": [serialize_user_summary(user) for user in snapshot.pm_pending_users],
    }


def serialize_metrics_snapshot(snapshot: MetricsReportSnapshot) -> dict:
    return {
        "startDate": snapshot.start_date.isoformat(),
        "endDate": snapshot.end_date.isoformat(),
        "days": snapshot.days,
        "users": [serialize_user_metrics(user_snapshot) for user_snapshot in snapshot.users],
    }


def serialize_user_metrics(snapshot: UserMetricsSnapshot) -> dict:
    return {
        "user": serialize_user_summary(snapshot.user),
        "expectedWorkdays": snapshot.expected_workdays,
        "amSubmitted": snapshot.am_submitted,
        "pmSubmitted": snapshot.pm_submitted,
        "missedAm": snapshot.missed_am,
        "missedPm": snapshot.missed_pm,
        "completed": snapshot.completed,
        "warning": snapshot.warning,
        "blocked": snapshot.blocked,
        "dropped": snapshot.dropped,
        "adminWarningsMonth": snapshot.admin_warnings_month,
    }


def serialize_user_summary(user: User) -> dict:
    return {
        "id": user.id,
        "telegramUserId": user.telegram_user_id,
        "username": user.username,
        "displayName": user_display_name(user),
        "joinedAt": serialize_datetime(user.joined_at),
    }


def serialize_warning_result(issued_warning: IssuedWarning) -> dict:
    return {
        "developer": serialize_user_summary(issued_warning.developer),
        "warningId": issued_warning.warning.id,
        "reason": issued_warning.warning.reason,
        "createdAt": serialize_datetime(issued_warning.warning.created_at),
    }


def serialize_binding_intent(*, token: str, expires_at: datetime) -> dict:
    return {
        "token": token,
        "expiresAt": serialize_datetime(expires_at),
        "bindCommand": f"/bind_group {token}",
    }


def build_display_name(principal: ApiPrincipal, user: User | None) -> str:
    if user is not None:
        return user_display_name(user)
    parts = [principal.first_name]
    if principal.last_name:
        parts.append(principal.last_name)
    return " ".join(part for part in parts if part).strip() or str(principal.telegram_user_id)


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
