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
    subtask_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    submission: Mapped["DailySubmission"] = relationship(back_populates="items")
    status: Mapped["SubmissionItemStatus | None"] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        uselist=False,
    )


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

