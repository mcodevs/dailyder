from __future__ import annotations

from datetime import time
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    bot_token: SecretStr = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    timezone: str = Field(default="Asia/Tashkent", alias="TIMEZONE")
    group_chat_id: int | None = Field(default=None, alias="GROUP_CHAT_ID")
    admin_user_ids: tuple[int, ...] = Field(default_factory=tuple, alias="ADMIN_USER_IDS")
    am_reminder_time: str = Field(default="09:00", alias="AM_REMINDER_TIME")
    pm_reminder_time: str = Field(default="17:00", alias="PM_REMINDER_TIME")
    hashtag: str = Field(default="daily", alias="HASHTAG")
    port: int = Field(default=8080, alias="PORT")
    mini_app_url: str | None = Field(default=None, alias="MINI_APP_URL")
    web_allowed_origins: str = Field(default="*", alias="WEB_ALLOWED_ORIGINS")
    dev_auth_enabled: bool = Field(default=False, alias="DEV_AUTH_ENABLED")
    api_token_secret: SecretStr | None = Field(default=None, alias="API_TOKEN_SECRET")
    api_token_ttl_minutes: int = Field(default=120, alias="API_TOKEN_TTL_MINUTES")
    telegram_init_data_ttl_seconds: int = Field(default=300, alias="TELEGRAM_INIT_DATA_TTL_SECONDS")
    bind_intent_ttl_minutes: int = Field(default=15, alias="BIND_INTENT_TTL_MINUTES")

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, value: Any) -> tuple[int, ...]:
        if value in (None, "", ()):
            return ()
        if isinstance(value, int):
            return (value,)
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(int(item) for item in value)
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(int(item) for item in parts)
        raise TypeError("ADMIN_USER_IDS format is invalid")

    @field_validator("group_chat_id", mode="before")
    @classmethod
    def parse_group_chat_id(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    @property
    def timezone_info(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def am_time(self):
        return time.fromisoformat(self.am_reminder_time)

    @property
    def pm_time(self):
        return time.fromisoformat(self.pm_reminder_time)

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self.admin_user_ids

    @property
    def effective_api_token_secret(self) -> str:
        if self.api_token_secret is not None:
            return self.api_token_secret.get_secret_value()
        return self.bot_token.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
