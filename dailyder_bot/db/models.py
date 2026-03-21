from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dailyder_bot.db.base import Base, TimestampMixin
from dailyder_bot.utils.ids import new_id


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_in_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    submissions: Mapped[list["DailySubmission"]] = relationship(back_populates="user")
    flow_sessions: Mapped[list["BotFlowSession"]] = relationship(back_populates="user")
    warnings: Mapped[list["DeveloperWarning"]] = relationship(back_populates="developer")


class DailyDigest(Base, TimestampMixin):
    __tablename__ = "daily_digests"
    __table_args__ = (UniqueConstraint("work_date", "period", name="uq_digest_date_period"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class DailySubmission(Base, TimestampMixin):
    __tablename__ = "daily_submissions"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_submission_user_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hashtag: Mapped[str] = mapped_column(String(50), nullable=False)
    am_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pm_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="submissions")
    items: Mapped[list["SubmissionItem"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionItem.sort_order",
    )


class SubmissionItem(Base, TimestampMixin):
    __tablename__ = "submission_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("daily_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_name: Mapped[str] = mapped_column(String(500), nullable=False)
    subtask_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission: Mapped["DailySubmission"] = relationship(back_populates="items")
    subtasks: Mapped[list["SubmissionSubtask"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="SubmissionSubtask.sort_order",
    )
    status: Mapped["SubmissionItemStatus | None"] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def subtask_names(self) -> list[str]:
        if self.subtasks:
            return [subtask.subtask_name for subtask in self.subtasks]
        if not self.subtask_name:
            return []
        return [item for item in self.subtask_name.split("\n") if item]

    @subtask_names.setter
    def subtask_names(self, values: list[str]) -> None:
        cleaned = [value.strip() for value in values if value and value.strip()]
        self.subtask_name = "\n".join(cleaned) if cleaned else None
        self.subtasks = [
            SubmissionSubtask(
                id=new_id(),
                sort_order=index,
                subtask_name=value,
            )
            for index, value in enumerate(cleaned, start=1)
        ]


class SubmissionSubtask(Base, TimestampMixin):
    __tablename__ = "submission_subtasks"
    __table_args__ = (
        UniqueConstraint("submission_item_id", "sort_order", name="uq_submission_subtask_order"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    submission_item_id: Mapped[str] = mapped_column(
        ForeignKey("submission_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    subtask_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    item: Mapped["SubmissionItem"] = relationship(back_populates="subtasks")


class SubmissionItemStatus(Base, TimestampMixin):
    __tablename__ = "submission_item_statuses"
    __table_args__ = (UniqueConstraint("submission_item_id", name="uq_item_status_item"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    submission_item_id: Mapped[str] = mapped_column(
        ForeignKey("submission_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    item: Mapped["SubmissionItem"] = relationship(back_populates="status")


class BotFlowSession(Base, TimestampMixin):
    __tablename__ = "bot_flow_sessions"
    __table_args__ = (UniqueConstraint("user_id", "flow", "work_date", name="uq_bot_flow_session"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    flow: Mapped[str] = mapped_column(String(50), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="flow_sessions")


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    admin_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class DeveloperWarning(Base, TimestampMixin):
    __tablename__ = "developer_warnings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    developer_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admin_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    developer: Mapped["User"] = relationship(back_populates="warnings")
