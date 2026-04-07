from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from dailyder_bot.config.settings import Settings
from dailyder_bot.web.auth import ApiPrincipal, ApiTokenService, TelegramMiniAppAuthenticator


def build_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123456:test-token",
        DATABASE_URL="sqlite+aiosqlite:///unused.db",
        ADMIN_USER_IDS="9001",
        API_TOKEN_TTL_MINUTES=5,
        TELEGRAM_INIT_DATA_TTL_SECONDS=300,
    )


def build_signed_init_data(settings: Settings, *, auth_date: int) -> str:
    user_payload = {
        "id": 9001,
        "first_name": "Admin",
        "last_name": "User",
        "username": "adminuser",
    }
    values = {
        "auth_date": str(auth_date),
        "query_id": "AAEAAAE",
        "user": json.dumps(user_payload, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(
        b"WebAppData",
        settings.bot_token.get_secret_value().encode("utf-8"),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


def test_api_token_service_round_trip() -> None:
    settings = build_settings()
    service = ApiTokenService(settings)
    now = datetime.now(UTC)
    token = service.issue_token(
        principal=ApiPrincipal(
            telegram_user_id=9001,
            username="adminuser",
            first_name="Admin",
            last_name="User",
            is_admin=True,
            auth_mode="telegram",
        ),
        now=now,
    )

    principal = service.verify_token(token.access_token, now=now + timedelta(minutes=1))

    assert principal.telegram_user_id == 9001
    assert principal.username == "adminuser"
    assert principal.is_admin is True


def test_api_token_service_rejects_expired_token() -> None:
    settings = build_settings()
    service = ApiTokenService(settings)
    now = datetime.now(UTC)
    token = service.issue_token(
        principal=ApiPrincipal(
            telegram_user_id=1001,
            username="devuser",
            first_name="Dev",
            last_name=None,
            is_admin=False,
            auth_mode="dev",
        ),
        now=now,
    )

    with pytest.raises(ValueError, match="muddati tugagan"):
        service.verify_token(token.access_token, now=now + timedelta(minutes=10))


def test_telegram_authenticator_validates_signed_init_data() -> None:
    settings = build_settings()
    authenticator = TelegramMiniAppAuthenticator(settings)
    now = datetime.now(UTC)
    init_data = build_signed_init_data(settings, auth_date=int(now.timestamp()))

    principal = authenticator.authenticate(init_data=init_data, now=now)

    assert principal.telegram_user_id == 9001
    assert principal.username == "adminuser"
    assert principal.is_admin is True


def test_telegram_authenticator_rejects_invalid_hash() -> None:
    settings = build_settings()
    authenticator = TelegramMiniAppAuthenticator(settings)
    now = datetime.now(UTC)
    init_data = build_signed_init_data(settings, auth_date=int(now.timestamp()))
    tampered = init_data.replace("adminuser", "otheruser")

    with pytest.raises(ValueError, match="imzosi noto'g'ri"):
        authenticator.authenticate(init_data=tampered, now=now)
