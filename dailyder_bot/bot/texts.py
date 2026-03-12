from __future__ import annotations

from html import escape
from typing import Iterable

from dailyder_bot.db.models import DailySubmission, SubmissionItem
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.utils.dates import format_uz_date
from dailyder_bot.utils.telegram import user_mention_html


def welcome_text() -> str:
    return (
        "<b>Dailyder botga xush kelibsiz.</b>\n"
        "Siz onboardingdan o'tdingiz. Endi bot ish kunlari 09:00 va 17:00 da eslatma yuboradi.\n\n"
        "Asosiy buyruqlar:\n"
        "/today - bugungi vazifalarni yuborish\n"
        "/update - kechki statuslarni yangilash\n"
        "/help - yordam"
    )


def help_text() -> str:
    return (
        "<b>Foydalanish tartibi</b>\n"
        "1. Ertalab /today orqali vazifalarni yuborasiz.\n"
        "2. Kechqurun /update orqali har bir vazifaga status tanlaysiz.\n"
        "3. Bot digest xabarlarini guruhga joylab boradi.\n\n"
        "<b>Morning format</b>\n"
        "Har blok alohida bo'lsin:\n"
        "Project: TvRain\n"
        "Task: IOS bug fix\n"
        "Subtask: iphone vs ipad\n\n"
        "Subtask ixtiyoriy."
    )


def group_not_bound_text() -> str:
    return "Bot hali guruhga biriktirilmagan. Admin `/bind_group` buyrug'ini supergroup ichida yuborsin."


def not_group_member_text() -> str:
    return "Siz maqsadli guruh a'zosi emassiz. Avval guruhga qo'shiling."


def start_required_text() -> str:
    return "Avval `/start` yuborib onboardingni yakunlang."


def morning_template_text(work_date, hashtag: str, mention_html: str) -> str:
    return (
        f"<b>Bugungi daily — {format_uz_date(work_date)}</b>\n"
        f"#{escape(hashtag)}\n"
        f"Developer: {mention_html}\n\n"
        "Quyidagi formatda yuboring:\n\n"
        "Project: TvRain\n"
        "Task: IOS bug fix\n"
        "Subtask: iphone vs ipad\n\n"
        "Project: AnorDelivery\n"
        "Task: Release\n\n"
        "Faqat `Project`, `Task`, `Subtask(optional)` satrlarini yozing."
    )


def morning_reminder_text(work_date, hashtag: str, mention_html: str) -> str:
    return (
        f"<b>Eslatma: daily yuborish vaqti</b>\n"
        f"Sana: {format_uz_date(work_date)}\n\n"
        f"{morning_template_text(work_date, hashtag, mention_html)}"
    )


def morning_submission_saved_text(item_count: int) -> str:
    return (
        "<b>Qabul qilindi.</b>\n"
        f"{item_count} ta vazifa saqlandi va AM digest yangilandi."
    )


def parse_error_text(errors: Iterable[str]) -> str:
    error_lines = "\n".join(f"• {escape(error)}" for error in errors)
    return (
        "<b>Formatda xato bor.</b>\n"
        "Iltimos, quyidagi xatolarni to'g'rilang:\n"
        f"{error_lines}"
    )


def pm_reminder_text(work_date, has_submission: bool) -> str:
    if has_submission:
        return (
            f"<b>Kechki update vaqti</b>\n"
            f"Sana: {format_uz_date(work_date)}\n"
            "Har bir ertalabgi vazifaga status tanlash uchun /update ni bosing."
        )
    return (
        f"<b>Kechki update vaqti</b>\n"
        f"Sana: {format_uz_date(work_date)}\n"
        "Bugun ertalab vazifa yuborilmagan. Zarur bo'lsa avval /today yuboring."
    )


def pm_item_prompt(item: SubmissionItem, position: int, total: int) -> str:
    return pm_item_prompt_parts(
        project_name=item.project_name,
        task_name=item.task_name,
        subtask_name=item.subtask_name,
        position=position,
        total=total,
    )


def pm_item_prompt_parts(
    *,
    project_name: str,
    task_name: str,
    subtask_name: str | None,
    position: int,
    total: int,
) -> str:
    lines = [
        f"<b>Vazifa {position}/{total}</b>",
        f"Project: <b>{escape(project_name)}</b>",
        f"Task: {escape(task_name)}",
    ]
    if subtask_name:
        lines.append(f"Subtask: {escape(subtask_name)}")
    lines.append("")
    lines.append("Statusni tanlang:")
    return "\n".join(lines)


def pm_note_prompt() -> str:
    return (
        "<b>Yakuni izoh</b>\n"
        "Xohlasangiz bugungi kun bo'yicha qisqa izoh yuboring. "
        "Izoh kerak bo'lmasa tugmani bosing."
    )


def pm_update_saved_text() -> str:
    return "<b>PM update saqlandi.</b>\nGuruhdagi PM digest yangilandi."


def admin_menu_text() -> str:
    return (
        "<b>Admin panel</b>\n"
        "Quyidagi amallardan birini tanlang."
    )


def admin_only_text() -> str:
    return "Bu buyruq faqat adminlar uchun."


def render_am_digest(work_date, hashtag: str, submissions: list[DailySubmission]) -> str:
    lines = [
        f"<b>🌅 AM digest — {format_uz_date(work_date)}</b>",
        f"#{escape(hashtag)}",
        "",
    ]
    if not submissions:
        lines.append("Hozircha hech kim vazifa yubormadi.")
        return "\n".join(lines)

    for index, submission in enumerate(submissions, start=1):
        lines.append(f"{index}. {user_mention_html(submission.user)}")
        lines.extend(_render_am_items(submission.items))
        lines.append("")
    return "\n".join(lines).strip()


def render_pm_digest(work_date, hashtag: str, submissions: list[DailySubmission]) -> str:
    lines = [
        f"<b>🌆 PM digest — {format_uz_date(work_date)}</b>",
        f"#{escape(hashtag)}",
        "",
    ]
    if not submissions:
        lines.append("Hozircha hech kim status yubormadi.")
        return "\n".join(lines)

    for index, submission in enumerate(submissions, start=1):
        lines.append(f"{index}. {user_mention_html(submission.user)}")
        lines.extend(_render_pm_items(submission.items))
        if submission.final_note:
            lines.append(f"   Izoh: {escape(submission.final_note)}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_am_items(items: list[SubmissionItem]) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(f"   • <b>{escape(item.project_name)}</b> — {escape(item.task_name)}")
        if item.subtask_name:
            lines.append(f"     - {escape(item.subtask_name)}")
    return lines


def _render_pm_items(items: list[SubmissionItem]) -> list[str]:
    lines: list[str] = []
    for item in items:
        emoji = ItemStatus(item.status.status).emoji if item.status else "•"
        lines.append(
            f"   {emoji} <b>{escape(item.project_name)}</b> — {escape(item.task_name)}"
        )
        if item.subtask_name:
            lines.append(f"     - {escape(item.subtask_name)}")
    return lines
