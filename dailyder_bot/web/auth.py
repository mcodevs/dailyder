from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from dailyder_bot.config.settings import Settings


@dataclass(slots=True)
class ApiPrincipal:
    telegram_user_id: int
    username: str | None
    first_name: str
    last_name: str | None
    is_admin: bool
    auth_mode: str


@dataclass(slots=True)
class IssuedToken:
    access_token: str
    expires_at: datetime


class TelegramMiniAppAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authenticate(self, *, init_data: str, now: datetime) -> ApiPrincipal:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.get("hash")
        if not received_hash:
            raise ValueError("Telegram initData hash topilmadi.")

        auth_date_raw = params.get("auth_date")
        if not auth_date_raw:
            raise ValueError("Telegram initData auth_date topilmadi.")
        auth_date = datetime.fromtimestamp(int(auth_date_raw), tz=UTC)
        if auth_date + timedelta(seconds=self.settings.telegram_init_data_ttl_seconds) <= now.astimezone(UTC):
            raise ValueError("Telegram initData eskirib qolgan.")

        check_items = [f"{key}={value}" for key, value in sorted(params.items()) if key != "hash"]
        data_check_string = "\n".join(check_items)
        secret_key = hmac.new(
            b"WebAppData",
            self.settings.bot_token.get_secret_value().encode("utf-8"),
            hashlib.sha256,
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise ValueError("Telegram initData imzosi noto'g'ri.")

        user_raw = params.get("user")
        if not user_raw:
            raise ValueError("Telegram initData user topilmadi.")
        user_payload = json.loads(user_raw)
        telegram_user_id = int(user_payload["id"])
        return ApiPrincipal(
            telegram_user_id=telegram_user_id,
            username=user_payload.get("username"),
            first_name=user_payload.get("first_name", "") or str(telegram_user_id),
            last_name=user_payload.get("last_name"),
            is_admin=self.settings.is_admin(telegram_user_id),
            auth_mode="telegram",
        )


class ApiTokenService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def issue_token(self, *, principal: ApiPrincipal, now: datetime) -> IssuedToken:
        expires_at = now.astimezone(UTC) + timedelta(minutes=self.settings.api_token_ttl_minutes)
        payload = asdict(principal)
        payload["exp"] = int(expires_at.timestamp())
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_segment = encode_token_segment(payload_json)
        signature_segment = encode_token_segment(self.sign(payload_json))
        return IssuedToken(
            access_token=f"{payload_segment}.{signature_segment}",
            expires_at=expires_at,
        )

    def verify_token(self, token: str, *, now: datetime) -> ApiPrincipal:
        try:
            payload_segment, signature_segment = token.split(".", maxsplit=1)
        except ValueError as exc:
            raise ValueError("Access token formati noto'g'ri.") from exc

        payload_json = decode_token_segment(payload_segment)
        expected_signature = self.sign(payload_json)
        actual_signature = decode_token_segment(signature_segment)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Access token imzosi noto'g'ri.")

        payload = json.loads(payload_json.decode("utf-8"))
        if int(payload["exp"]) <= int(now.astimezone(UTC).timestamp()):
            raise ValueError("Access token muddati tugagan.")
        return ApiPrincipal(
            telegram_user_id=int(payload["telegram_user_id"]),
            username=payload.get("username"),
            first_name=payload.get("first_name", "") or str(payload["telegram_user_id"]),
            last_name=payload.get("last_name"),
            is_admin=bool(payload.get("is_admin")),
            auth_mode=str(payload.get("auth_mode", "telegram")),
        )

    def sign(self, payload_json: bytes) -> bytes:
        return hmac.new(
            self.settings.effective_api_token_secret.encode("utf-8"),
            payload_json,
            hashlib.sha256,
        ).digest()


def encode_token_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def decode_token_segment(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
