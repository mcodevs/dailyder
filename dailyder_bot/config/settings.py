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

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, value: Any) -> tuple[int, ...]:
        if value in (None, "", ()):
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(int(item) for item in value)
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(int(item) for item in parts)
        raise TypeError("ADMIN_USER_IDS format is invalid")

    @property
    def timezone_info(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def am_time(self):
        return time.fromisoformat(self.am_reminder_time)

    @property
    def pm_time(self):
        return time.fromisoformat(self.pm_reminder_time)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
