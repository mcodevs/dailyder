from __future__ import annotations

from html import escape
from typing import Iterable

from dailyder_bot.db.models import DailySubmission, SubmissionItem
from dailyder_bot.domain.enums import ItemStatus
from dailyder_bot.utils.dates import format_uz_date
from dailyder_bot.utils.telegram import user_mention_html


def welcome_text(*, is_admin: bool) -> str:
    lines = [
        "<b>Dailyder botga xush kelibsiz.</b>",
        "Asosiy ishlar endi menyu va tugmalar orqali boshqariladi.",
        "",
        "Nimalar qila olasiz:",
        "• bugungi tasklarni kiritish va yuborish",
        "• mavjud tasklarga qo'shish, edit qilish, o'chirish",
        "• PM update yuborish va qayta tahrirlash",
        "• yordam matnini ko'rish",
    ]
    if is_admin:
        lines.extend(["", "Siz uchun admin panel ham mavjud."])
    return "\n".join(lines)


def help_text(*, is_admin: bool) -> str:
    lines = [
        "<b>Qanday ishlaydi</b>",
        "1. `Bugungi tasklar` orqali draft yig'asiz.",
        "2. Tasklarni review qilib `Yuborish` tugmasi bilan AM holatga o'tkazasiz.",
        "3. `PM update` orqali har bir taskga status berasiz va xohlasangiz yakuniy izoh qoldirasiz.",
        "4. Agar AM tasklar keyin o'zgarsa, PM update qayta yuboriladi.",
        "",
        "<b>Tez yo'l</b>",
        "Agar xohlasangiz tasklarni eski formatdagi matndan ham import qilishingiz mumkin.",
    ]
    if is_admin:
        lines.extend(["", "Admin amallari `Admin panel` ichida joylashgan."])
    return "\n".join(lines)


def group_not_bound_text() -> str:
    return "Bot hali guruhga biriktirilmagan. Admin `/bind_group` buyrug'ini supergroup ichida yuborsin."


def not_group_member_text() -> str:
    return "Siz maqsadli guruh a'zosi emassiz. Avval guruhga qo'shiling."


def start_required_text() -> str:
    return "Avval `/start` yuborib onboardingni yakunlang."


def main_menu_hint_text() -> str:
    return "Asosiy menyudan kerakli bo'limni tanlang."


def draft_summary_text(work_date, submission: DailySubmission | None) -> str:
    lines = [f"<b>Bugungi tasklar — {format_uz_date(work_date)}</b>"]
    if submission is None or not submission.items:
        lines.extend(["", "Hozircha task yo'q.", "Yangi task qo'shing yoki matndan import qiling."])
        return "\n".join(lines)

    if submission.am_submitted_at is None:
        status_line = "Holat: <b>draft</b>"
    elif submission.pm_submitted_at is None:
        status_line = "Holat: <b>AM yuborilgan</b>"
    else:
        status_line = "Holat: <b>PM update yuborilgan</b>"
    lines.extend(["", status_line, ""])
    lines.extend(_render_am_items(submission.items))
    if submission.final_note:
        lines.extend(["", f"Izoh: {escape(submission.final_note)}"])
    return "\n".join(lines)


def draft_resume_text() -> str:
    return (
        "<b>Yarim qolgan task sessiyasi bor.</b>\n"
        "Xohlasangiz davom eting yoki qaytadan boshlang."
    )


def project_picker_text() -> str:
    return "<b>Project tanlang</b>\nMavjud projectlardan birini tanlang yoki yangisini oching."


def project_prompt_text(*, current_value: str | None = None) -> str:
    if current_value:
        return (
            "<b>Project nomi</b>\n"
            f"Joriy qiymat: <b>{escape(current_value)}</b>\n"
            "Yangi project nomini yuboring."
        )
    return "<b>Project nomi</b>\nProject nomini yuboring."


def task_prompt_text(*, current_value: str | None = None) -> str:
    if current_value:
        return (
            "<b>Task nomi</b>\n"
            f"Joriy qiymat: <b>{escape(current_value)}</b>\n"
            "Yangi task nomini yuboring."
        )
    return "<b>Task nomi</b>\nTask nomini yuboring."


def subtask_builder_text(
    *,
    project_name: str,
    task_name: str,
    subtask_names: list[str],
    mode: str,
) -> str:
    title = "Taskni review qiling" if mode == "edit" else "Yangi task review"
    lines = [
        f"<b>{title}</b>",
        f"Project: <b>{escape(project_name)}</b>",
        f"Task: {escape(task_name)}",
    ]
    if subtask_names:
        lines.append("")
        lines.append("Subtasklar:")
        lines.extend(f"• {escape(subtask)}" for subtask in subtask_names)
    else:
        lines.extend(["", "Subtasklar hali yo'q."])
    lines.extend(["", "Subtask qo'shing yoki saqlang."])
    return "\n".join(lines)


def subtask_prompt_text() -> str:
    return "<b>Subtask</b>\nSubtask matnini yuboring."


def delete_confirm_text(item: SubmissionItem) -> str:
    return (
        "<b>Taskni o'chirish</b>\n"
        f"{escape(item.project_name)} — {escape(item.task_name)}\n"
        "Ushbu taskni o'chirishni tasdiqlang."
    )


def import_replace_confirm_text() -> str:
    return (
        "<b>Import replace qiladi.</b>\n"
        "Joriy draftdagi tasklar o'rniga yangi import natijasi qo'yiladi. Davom etasizmi?"
    )


def import_prompt_text() -> str:
    return (
        "<b>Matndan import</b>\n"
        "Quyidagi formatdagi matnni yuboring:\n\n"
        "Project: TvRain\n"
        "Task: IOS bug fix\n"
        "Subtask: iphone bug\n"
        "Subtask: ipad bug"
    )


def draft_change_saved_text(*, pm_reset: bool) -> str:
    if pm_reset:
        return (
            "<b>Tasklar saqlandi.</b>\n"
            "AM o'zgarishlari sabab PM update reset qilindi. PM update'ni qayta yuboring."
        )
    return "<b>Tasklar saqlandi.</b>\nDraft yangilandi."


def draft_deleted_text(*, pm_reset: bool) -> str:
    if pm_reset:
        return (
            "<b>Task o'chirildi.</b>\n"
            "PM update reset qilindi. PM update'ni qayta yuboring."
        )
    return "<b>Task o'chirildi.</b>"


def draft_submitted_text(item_count: int) -> str:
    return (
        "<b>AM tasklar yuborildi.</b>\n"
        f"{item_count} ta task saqlandi va digest yangilandi."
    )


def morning_reminder_text(work_date, hashtag: str, mention_html: str) -> str:
    return (
        f"<b>Eslatma: bugungi tasklar</b>\n"
        f"Sana: {format_uz_date(work_date)}\n"
        f"#{escape(hashtag)}\n"
        f"Developer: {mention_html}\n\n"
        "Asosiy menyudan `Bugungi tasklar` bo'limini ochib tasklaringizni yuboring."
    )


def pm_empty_text() -> str:
    return "PM update uchun avval bugungi tasklarni yuboring."


def pm_reminder_text(work_date, has_submission: bool) -> str:
    if has_submission:
        return (
            f"<b>Kechki update vaqti</b>\n"
            f"Sana: {format_uz_date(work_date)}\n"
            "Asosiy menyudan `PM update` bo'limini ochib statuslarni yuboring."
        )
    return (
        f"<b>Kechki update vaqti</b>\n"
        f"Sana: {format_uz_date(work_date)}\n"
        "Bugun ertalab tasklar yuborilmagan. Avval `Bugungi tasklar` bo'limidan task kiriting."
    )


def pm_resume_text() -> str:
    return (
        "<b>Yarim qolgan PM sessiyasi bor.</b>\n"
        "Xohlasangiz davom eting yoki qaytadan boshlang."
    )


def pm_summary_text(
    *,
    work_date,
    submission: DailySubmission,
    status_map: dict[str, str],
    final_note: str | None,
) -> str:
    lines = [f"<b>PM update — {format_uz_date(work_date)}</b>", ""]
    for index, item in enumerate(submission.items, start=1):
        status_value = status_map.get(item.id)
        emoji = ItemStatus(status_value).emoji if status_value else "◻️"
        lines.append(f"{index}. <b>{escape(item.project_name)}</b> — {escape(item.task_name)} {emoji}")
        for subtask in item.subtasks:
            subtask_emoji = ItemStatus(subtask.status).emoji if subtask.status else "◻️"
            lines.append(f"   {subtask_emoji} {escape(subtask.subtask_name)}")
        if not item.subtasks:
            for subtask_name in item.subtask_names:
                lines.append(f"   ◻️ {escape(subtask_name)}")
    lines.extend(["", f"Yakuniy izoh: {escape(final_note) if final_note else 'yoʻq'}"])
    lines.append("Kerakli taskni tanlab statusni yangilang yoki yakunlang.")
    return "\n".join(lines)


def pm_item_prompt(item: SubmissionItem, *, current_status: str | None) -> str:
    emoji = ItemStatus(current_status).emoji if current_status else "◻️"
    lines = [
        "<b>PM status</b>",
        f"Project: <b>{escape(item.project_name)}</b>",
        f"Task: {escape(item.task_name)}",
        f"Task status: {emoji}",
    ]
    if item.subtasks:
        lines.extend(["", "Subtasklar:"])
        for subtask in item.subtasks:
            subtask_emoji = ItemStatus(subtask.status).emoji if subtask.status else "◻️"
            lines.append(f"{subtask_emoji} {escape(subtask.subtask_name)}")
    elif item.subtask_names:
        lines.extend(["", "Subtasklar:"])
        for subtask_name in item.subtask_names:
            lines.append(f"◻️ {escape(subtask_name)}")
    lines.append("")
    lines.append("Task yoki subtaskni tanlang.")
    return "\n".join(lines)


def pm_target_prompt(*, title: str, current_status: str | None) -> str:
    emoji = ItemStatus(current_status).emoji if current_status else "◻️"
    return (
        "<b>Statusni yangilash</b>\n"
        f"{escape(title)}\n"
        f"Joriy status: {emoji}\n"
        "Yangi statusni tanlang."
    )


def pm_note_prompt(*, current_note: str | None) -> str:
    if current_note:
        return (
            "<b>Yakuniy izoh</b>\n"
            f"Joriy izoh: {escape(current_note)}\n"
            "Yangi izoh yuboring yoki mavjud izohni tozalang."
        )
    return "<b>Yakuniy izoh</b>\nIzoh yuboring yoki izohsiz davom eting."


def pm_submit_error_text() -> str:
    return "Yakunlashdan oldin barcha tasklarga status tanlang."


def pm_saved_text() -> str:
    return "<b>PM update saqlandi.</b>\nPM digest yangilandi."


def pm_reset_confirmation_text() -> str:
    return (
        "<b>Bu o'zgarish PM update'ni reset qiladi.</b>\n"
        "Tasdiqlasangiz mavjud PM statuslar va yakuniy izoh tozalanadi."
    )


def admin_menu_text() -> str:
    return "<b>Admin panel</b>\nQuyidagi amallardan birini tanlang."


def admin_only_text() -> str:
    return "Bu amal faqat adminlar uchun."


def warning_username_prompt_text() -> str:
    return "<b>Warning</b>\nDeveloper username yuboring. Masalan: @devuser"


def warning_username_not_found_text(username: str) -> str:
    return (
        "<b>Developer topilmadi.</b>\n"
        f"{escape(username)} username bilan onboard qilingan foydalanuvchi yoʻq.\n"
        "Qaytadan yuboring."
    )


def warning_reason_prompt_text(developer_mention: str) -> str:
    return (
        "<b>Warning sababi</b>\n"
        f"Developer: {developer_mention}\n"
        "Izoh yoki sababni yuboring."
    )


def warning_reason_empty_text() -> str:
    return "<b>Sabab bo'sh bo'lmasin.</b>\nIltimos, warning sababini yuboring."


def warning_message_text(*, developer_mention: str, admin_mention: str, reason: str, issued_at) -> str:
    return "\n".join(
        [
            "<b>⚠️ Warning</b>",
            f"Sana: {format_uz_date(issued_at.date())} {issued_at.strftime('%H:%M')}",
            f"Developer: {developer_mention}",
            f"Admin: {admin_mention}",
            "",
            f"Sabab: {escape(reason)}",
        ]
    )


def warning_private_delivery_failed_text() -> str:
    return "Warning guruhga yuborildi, lekin developer private chatiga yetkazib bo'lmadi."


def menu_redirect_text() -> str:
    return "Asosiy menyudan davom eting."


def parse_error_text(errors: Iterable[str]) -> str:
    error_lines = "\n".join(f"• {escape(error)}" for error in errors)
    return (
        "<b>Formatda xato bor.</b>\n"
        "Quyidagi xatolarni to'g'rilang:\n"
        f"{error_lines}"
    )


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
        for subtask_name in item.subtask_names:
            lines.append(f"     - {escape(subtask_name)}")
    return lines


def _render_pm_items(items: list[SubmissionItem]) -> list[str]:
    lines: list[str] = []
    for item in items:
        emoji = ItemStatus(item.status.status).emoji if item.status else "•"
        lines.append(
            f"   <b>{escape(item.project_name)}</b> — {escape(item.task_name)} {emoji}"
        )
        for subtask in item.subtasks:
            subtask_emoji = ItemStatus(subtask.status).emoji if subtask.status else "◻️"
            lines.append(f"     {subtask_emoji} {escape(subtask.subtask_name)}")
        if not item.subtasks:
            for subtask_name in item.subtask_names:
                lines.append(f"     ◻️ {escape(subtask_name)}")
    return lines
