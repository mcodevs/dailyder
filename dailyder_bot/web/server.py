from __future__ import annotations

from datetime import date
from html import escape

from aiohttp import web
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from dailyder_bot.bot import texts
from dailyder_bot.container import AppContext
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.repositories.users import UserRepository
from dailyder_bot.services.access import GroupBindingError, MembershipError
from dailyder_bot.utils.dates import local_now, today_local
from dailyder_bot.utils.telegram import user_mention_html
from dailyder_bot.web.auth import ApiPrincipal, ApiTokenService, TelegramMiniAppAuthenticator
from dailyder_bot.web.serializers import (
    serialize_binding_intent,
    serialize_dashboard,
    serialize_me,
    serialize_metrics_snapshot,
    serialize_pending_snapshot,
    serialize_readiness_snapshot,
    serialize_submission,
    serialize_user_summary,
    serialize_warning_result,
)


class WebServer:
    def __init__(self, app_context: AppContext, port: int) -> None:
        self.app_context = app_context
        self.port = port
        self.runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = build_application(self.app_context)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, host="0.0.0.0", port=self.port)
        await site.start()

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()


def build_application(app_context: AppContext) -> web.Application:
    app = web.Application(
        middlewares=[
            error_middleware,
            cors_middleware,
            auth_middleware,
        ]
    )
    app["app_context"] = app_context
    app["telegram_authenticator"] = TelegramMiniAppAuthenticator(app_context.settings)
    app["api_token_service"] = ApiTokenService(app_context.settings)
    app.router.add_route("OPTIONS", "/{tail:.*}", handle_options)
    app.router.add_get("/healthz", handle_health)
    app.router.add_post("/api/v1/auth/telegram", handle_telegram_auth)
    app.router.add_post("/api/v1/auth/dev-login", handle_dev_auth)
    app.router.add_get("/api/v1/me", handle_me)
    app.router.add_get("/api/v1/dashboard", handle_dashboard)
    app.router.add_get("/api/v1/submissions/today", handle_get_today_submission)
    app.router.add_post("/api/v1/submissions/today/items", handle_create_today_item)
    app.router.add_patch("/api/v1/submissions/today/items/{item_id}", handle_update_today_item)
    app.router.add_delete("/api/v1/submissions/today/items/{item_id}", handle_delete_today_item)
    app.router.add_post("/api/v1/submissions/today/import", handle_import_today_submission)
    app.router.add_post("/api/v1/submissions/today/submit-am", handle_submit_today_submission)
    app.router.add_get("/api/v1/pm", handle_get_pm_summary)
    app.router.add_put("/api/v1/pm", handle_put_pm_summary)
    app.router.add_get("/api/v1/admin/readiness", handle_admin_readiness)
    app.router.add_get("/api/v1/admin/pending", handle_admin_pending)
    app.router.add_get("/api/v1/admin/metrics", handle_admin_metrics)
    app.router.add_get("/api/v1/admin/users", handle_admin_users)
    app.router.add_post("/api/v1/admin/reminders/{period}", handle_admin_reminders)
    app.router.add_post("/api/v1/admin/warnings", handle_admin_warnings)
    app.router.add_post("/api/v1/admin/group-binding/intents", handle_admin_group_binding_intents)
    return app


@web.middleware
async def error_middleware(request: web.Request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except PermissionError as exc:
        return web.json_response({"error": str(exc)}, status=403)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    response = web.Response(status=204) if request.method == "OPTIONS" else await handler(request)
    app_context = get_app_context(request)
    allowed_origin = resolve_allowed_origin(
        configured_value=app_context.settings.web_allowed_origins,
        request_origin=request.headers.get("Origin"),
    )
    if allowed_origin is not None:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    return response


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return await handler(request)
    if request.path.startswith("/api/v1/") and request.path not in {
        "/api/v1/auth/telegram",
        "/api/v1/auth/dev-login",
    }:
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise PermissionError("Authorization header topilmadi.")
        token = authorization.removeprefix("Bearer ").strip()
        principal = get_api_token_service(request).verify_token(token, now=local_now(get_app_context(request).settings.timezone_info))
        request["api_principal"] = principal
    return await handler(request)


async def handle_options(request: web.Request) -> web.Response:
    return web.Response(status=204)


async def handle_health(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    try:
        await app_context.db.ping()
    except Exception as exc:
        return web.json_response({"status": "error", "detail": str(exc)}, status=503)
    return web.json_response({"status": "ok"})


async def handle_telegram_auth(request: web.Request) -> web.Response:
    body = await parse_json_body(request)
    init_data = str(body.get("initData", "")).strip()
    if not init_data:
        raise ValueError("initData yuborilishi shart.")
    now = local_now(get_app_context(request).settings.timezone_info)
    principal = get_telegram_authenticator(request).authenticate(init_data=init_data, now=now)
    token = get_api_token_service(request).issue_token(principal=principal, now=now)
    return web.json_response(
        {
            "accessToken": token.access_token,
            "expiresAt": token.expires_at.isoformat(),
            "authMode": principal.auth_mode,
        }
    )


async def handle_dev_auth(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    if not app_context.settings.dev_auth_enabled:
        raise PermissionError("Dev auth o'chirilgan.")
    body = await parse_json_body(request)
    telegram_user_id = body.get("telegramUserId")
    username = body.get("username")
    async with app_context.db.session() as session:
        user_repo = UserRepository(session)
        user = None
        if telegram_user_id is not None:
            user = await user_repo.get_by_telegram_id(int(telegram_user_id))
        if user is None and username:
            user = await user_repo.get_by_username(str(username))

    if user is None and telegram_user_id is None:
        raise ValueError("Dev auth uchun telegramUserId yoki username yuboring.")

    resolved_telegram_user_id = int(telegram_user_id) if telegram_user_id is not None else int(user.telegram_user_id)
    resolved_username = user.username if user is not None else (str(username).lstrip("@") if username else None)
    principal = ApiPrincipal(
        telegram_user_id=resolved_telegram_user_id,
        username=resolved_username,
        first_name=user.first_name if user is not None else (resolved_username or str(resolved_telegram_user_id)),
        last_name=user.last_name if user is not None else None,
        is_admin=app_context.access_service.is_admin(resolved_telegram_user_id),
        auth_mode="dev",
    )
    token = get_api_token_service(request).issue_token(principal=principal, now=local_now(app_context.settings.timezone_info))
    return web.json_response(
        {
            "accessToken": token.access_token,
            "expiresAt": token.expires_at.isoformat(),
            "authMode": principal.auth_mode,
        }
    )


async def handle_me(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    user = await get_current_user(app_context, principal.telegram_user_id)
    binding = await app_context.access_service.get_group_binding()
    is_group_member = await resolve_group_membership(app_context, principal.telegram_user_id, binding)
    return web.json_response(
        serialize_me(
            principal=principal,
            user=user,
            binding=binding,
            is_group_member=is_group_member,
        )
    )


async def handle_dashboard(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    user = await get_current_user(app_context, principal.telegram_user_id)
    binding = await app_context.access_service.get_group_binding()
    is_group_member = await resolve_group_membership(app_context, principal.telegram_user_id, binding)
    work_date = today_local(app_context.settings.timezone_info)
    submission = None
    if user is not None:
        submission = await app_context.submission_service.get_today_submission(principal.telegram_user_id, work_date)
    return web.json_response(
        serialize_dashboard(
            principal=principal,
            user=user,
            binding=binding,
            is_group_member=is_group_member,
            work_date=work_date,
            submission=submission,
        )
    )


async def handle_get_today_submission(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    work_date = today_local(app_context.settings.timezone_info)
    submission = await app_context.submission_service.get_today_submission(principal.telegram_user_id, work_date)
    return web.json_response(serialize_submission(submission, work_date=work_date))


async def handle_create_today_item(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    body = await parse_json_body(request)
    result = await app_context.submission_service.add_draft_item(
        telegram_user_id=principal.telegram_user_id,
        work_date=today_local(app_context.settings.timezone_info),
        project_name=str(body.get("projectName", "")).strip(),
        task_name=str(body.get("taskName", "")).strip(),
        subtask_names=parse_subtask_names(body.get("subtaskNames")),
    )
    return web.json_response(
        {
            "submission": serialize_submission(result.submission, work_date=result.submission.work_date)["submission"],
            "pmReset": result.pm_reset,
        }
    )


async def handle_update_today_item(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    body = await parse_json_body(request)
    result = await app_context.submission_service.update_draft_item(
        telegram_user_id=principal.telegram_user_id,
        work_date=today_local(app_context.settings.timezone_info),
        item_id=request.match_info["item_id"],
        project_name=str(body.get("projectName", "")).strip(),
        task_name=str(body.get("taskName", "")).strip(),
        subtask_names=parse_subtask_names(body.get("subtaskNames")),
    )
    return web.json_response(
        {
            "submission": serialize_submission(result.submission, work_date=result.submission.work_date)["submission"],
            "pmReset": result.pm_reset,
        }
    )


async def handle_delete_today_item(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    result = await app_context.submission_service.delete_draft_item(
        telegram_user_id=principal.telegram_user_id,
        work_date=today_local(app_context.settings.timezone_info),
        item_id=request.match_info["item_id"],
    )
    return web.json_response(
        {
            "submission": serialize_submission(result.submission, work_date=result.submission.work_date)["submission"],
            "pmReset": result.pm_reset,
        }
    )


async def handle_import_today_submission(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    body = await parse_json_body(request)
    result = await app_context.submission_service.import_draft_from_text(
        telegram_user_id=principal.telegram_user_id,
        raw_text=str(body.get("rawText", "")).strip(),
        work_date=today_local(app_context.settings.timezone_info),
    )
    return web.json_response(
        {
            "submission": serialize_submission(result.submission, work_date=result.submission.work_date)["submission"],
            "pmReset": result.pm_reset,
        }
    )


async def handle_submit_today_submission(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    submission = await app_context.submission_service.submit_morning_draft(
        telegram_user_id=principal.telegram_user_id,
        work_date=today_local(app_context.settings.timezone_info),
        submitted_at=local_now(app_context.settings.timezone_info),
    )
    return web.json_response(
        {
            "submission": serialize_submission(submission, work_date=submission.work_date)["submission"],
        }
    )


async def handle_get_pm_summary(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    work_date = today_local(app_context.settings.timezone_info)
    submission = await app_context.submission_service.get_submitted_today_submission(principal.telegram_user_id, work_date)
    return web.json_response(serialize_submission(submission, work_date=work_date))


async def handle_put_pm_summary(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    await ensure_ready_user(app_context, principal)
    work_date = today_local(app_context.settings.timezone_info)
    body = await parse_json_body(request)

    for subtask_status in parse_subtask_statuses(body.get("subtaskStatuses")):
        await app_context.submission_service.record_subtask_status(
            telegram_user_id=principal.telegram_user_id,
            work_date=work_date,
            item_id=subtask_status["itemId"],
            subtask_id=subtask_status["subtaskId"],
            status=subtask_status["status"],
        )

    submission = await app_context.submission_service.record_pm_statuses(
        telegram_user_id=principal.telegram_user_id,
        work_date=work_date,
        status_map=parse_item_status_map(body.get("itemStatuses")),
        final_note=parse_optional_text(body.get("finalNote")),
        submitted_at=local_now(app_context.settings.timezone_info),
    )
    return web.json_response(
        {
            "submission": serialize_submission(submission, work_date=submission.work_date)["submission"],
        }
    )


async def handle_admin_readiness(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    snapshot = await app_context.admin_service.readiness_snapshot()
    return web.json_response(serialize_readiness_snapshot(snapshot))


async def handle_admin_pending(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    work_date = resolve_query_date(request, "date") or today_local(app_context.settings.timezone_info)
    snapshot = await app_context.admin_service.pending_snapshot(work_date)
    return web.json_response(serialize_pending_snapshot(snapshot))


async def handle_admin_metrics(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    days = int(request.query.get("days", "30"))
    snapshot = await app_context.metrics_service.build_snapshot(
        today_local(app_context.settings.timezone_info),
        timezone_info=app_context.settings.timezone_info,
        days=days,
    )
    return web.json_response(serialize_metrics_snapshot(snapshot))


async def handle_admin_users(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    users = await app_context.admin_service.list_onboarded_users()
    return web.json_response({"users": [serialize_user_summary(user) for user in users]})


async def handle_admin_reminders(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    period = request.match_info["period"]
    if period not in {"am", "pm"}:
        raise ValueError("period faqat am yoki pm bo'lishi kerak.")
    sent_count = await app_context.admin_service.resend_missing(
        period=period,
        work_date=today_local(app_context.settings.timezone_info),
        admin_user_id=principal.telegram_user_id,
        now=local_now(app_context.settings.timezone_info),
    )
    return web.json_response({"period": period, "sentCount": sent_count})


async def handle_admin_warnings(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    body = await parse_json_body(request)
    developer_username = str(body.get("developerUsername", "")).strip()
    reason = str(body.get("reason", "")).strip()
    if not developer_username:
        raise ValueError("developerUsername yuborilishi shart.")
    if not reason:
        raise ValueError("reason yuborilishi shart.")

    binding = await app_context.access_service.require_group_binding()
    issued_warning = await app_context.admin_service.issue_warning(
        admin_telegram_user_id=principal.telegram_user_id,
        developer_username=developer_username,
        group_chat_id=binding.chat_id,
        reason=reason,
        now=local_now(app_context.settings.timezone_info),
    )

    admin_mention = f"@{escape(principal.username)}" if principal.username else str(principal.telegram_user_id)
    warning_text = texts.warning_message_text(
        developer_mention=user_mention_html(issued_warning.developer),
        admin_mention=admin_mention,
        reason=reason,
        issued_at=local_now(app_context.settings.timezone_info),
    )
    await app_context.bot.send_message(
        chat_id=binding.chat_id,
        text=warning_text,
        message_thread_id=binding.message_thread_id,
    )

    private_delivery_failed = False
    try:
        await app_context.bot.send_message(
            chat_id=issued_warning.developer.telegram_user_id,
            text=warning_text,
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        private_delivery_failed = True

    payload = serialize_warning_result(issued_warning)
    payload["privateDeliveryFailed"] = private_delivery_failed
    return web.json_response(payload)


async def handle_admin_group_binding_intents(request: web.Request) -> web.Response:
    app_context = get_app_context(request)
    principal = get_api_principal(request)
    ensure_admin(principal)
    intent = await app_context.group_binding_intent_service.create_intent(
        admin_telegram_user_id=principal.telegram_user_id,
        now=local_now(app_context.settings.timezone_info),
    )
    return web.json_response(serialize_binding_intent(token=intent.token, expires_at=intent.expires_at))


def get_app_context(request: web.Request) -> AppContext:
    return request.app["app_context"]


def get_telegram_authenticator(request: web.Request) -> TelegramMiniAppAuthenticator:
    return request.app["telegram_authenticator"]


def get_api_token_service(request: web.Request) -> ApiTokenService:
    return request.app["api_token_service"]


def get_api_principal(request: web.Request) -> ApiPrincipal:
    principal = request.get("api_principal")
    if principal is None:
        raise PermissionError("Auth konteksti topilmadi.")
    return principal


async def parse_json_body(request: web.Request) -> dict:
    if request.can_read_body is False:
        return {}
    if request.content_length in (None, 0):
        return {}
    body = await request.json()
    if not isinstance(body, dict):
        raise ValueError("JSON object yuborilishi kerak.")
    return body


def resolve_allowed_origin(*, configured_value: str, request_origin: str | None) -> str | None:
    if not request_origin:
        return "*"
    normalized = [item.strip() for item in configured_value.split(",") if item.strip()]
    if not normalized or configured_value.strip() == "*":
        return "*"
    if request_origin in normalized:
        return request_origin
    return None


async def get_current_user(app_context: AppContext, telegram_user_id: int):
    async with app_context.db.session() as session:
        return await UserRepository(session).get_by_telegram_id(telegram_user_id)


async def resolve_group_membership(app_context: AppContext, telegram_user_id: int, binding) -> bool:
    if binding is None:
        return False
    return await app_context.access_service.is_group_member(app_context.bot, binding.chat_id, telegram_user_id)


async def ensure_ready_user(app_context: AppContext, principal: ApiPrincipal) -> None:
    try:
        await app_context.access_service.ensure_group_member(app_context.bot, principal.telegram_user_id)
    except GroupBindingError as exc:
        raise ValueError(str(exc)) from exc
    except MembershipError as exc:
        raise PermissionError(str(exc)) from exc

    user = await get_current_user(app_context, principal.telegram_user_id)
    if user is None:
        raise PermissionError(texts.start_required_text())


def ensure_admin(principal: ApiPrincipal) -> None:
    if not principal.is_admin:
        raise PermissionError(texts.admin_only_text())


def parse_subtask_names(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("subtaskNames list bo'lishi kerak.")
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def parse_item_status_map(value) -> dict[str, ItemStatus]:
    if not isinstance(value, list):
        raise ValueError("itemStatuses list bo'lishi kerak.")
    status_map: dict[str, ItemStatus] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("itemStatuses elementlari object bo'lishi kerak.")
        item_id = str(item.get("itemId", "")).strip()
        status_value = str(item.get("status", "")).strip()
        if not item_id or not status_value:
            raise ValueError("itemStatuses ichida itemId va status yuborilishi shart.")
        status_map[item_id] = ItemStatus(status_value)
    return status_map


def parse_subtask_statuses(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("subtaskStatuses list bo'lishi kerak.")
    entries: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("subtaskStatuses elementlari object bo'lishi kerak.")
        item_id = str(item.get("itemId", "")).strip()
        subtask_id = str(item.get("subtaskId", "")).strip()
        status_value = item.get("status")
        status = ItemStatus(str(status_value)) if status_value not in (None, "") else None
        if not item_id or not subtask_id:
            raise ValueError("subtaskStatuses ichida itemId va subtaskId yuborilishi shart.")
        entries.append(
            {
                "itemId": item_id,
                "subtaskId": subtask_id,
                "status": status,
            }
        )
    return entries


def parse_optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_query_date(request: web.Request, parameter_name: str) -> date | None:
    value = request.query.get(parameter_name)
    if not value:
        return None
    return date.fromisoformat(value)
