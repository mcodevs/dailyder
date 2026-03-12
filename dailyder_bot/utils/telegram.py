from __future__ import annotations

from html import escape

from dailyder_bot.db.models import User


def user_display_name(user: User) -> str:
    parts = [user.first_name]
    if user.last_name:
        parts.append(user.last_name)
    return " ".join(part for part in parts if part).strip()


def user_mention_html(user: User) -> str:
    if user.username:
        return f"@{escape(user.username)}"
    display_name = escape(user_display_name(user) or str(user.telegram_user_id))
    return f'<a href="tg://user?id={user.telegram_user_id}">{display_name}</a>'

