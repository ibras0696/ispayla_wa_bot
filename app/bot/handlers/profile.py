from __future__ import annotations

from ..services.state import get_user, get_balance


def build_profile_text(sender: str) -> str:
    """Сформировать строку профиля пользователя."""
    user = get_user(sender)
    if not user:
        return "Профиль не найден."
    username = user.username or "Не указано"
    registered = (
        user.registered_at.strftime("%Y-%m-%d %H:%M")
        if getattr(user, "registered_at", None)
        else "-"
    )
    return (
        "Профиль\n"
        f"ID: {sender}\n"
        f"Имя: {username}\n"
        f"Баланс: {get_balance(sender)} ₽\n"
        f"Регистрация: {registered}"
    )
