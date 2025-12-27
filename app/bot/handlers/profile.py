from __future__ import annotations

from ..services.state import get_user, get_balance, get_favorites


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
    lines = [
        "Профиль",
        f"ID: {sender}",
        f"Имя: {username}",
        f"Баланс: {get_balance(sender)} ₽",
        f"Регистрация: {registered}",
    ]
    favorites = get_favorites(sender)
    if favorites:
        lines.append("")
        lines.append(f"Избранное: {len(favorites)} объявлений.")
        for ad in favorites[:3]:
            lines.append(f"• ID {ad.id}: {ad.title} — {ad.price} ₽")
        lines.append("Напиши `ID 123`, чтобы открыть карточку, или открой `Покупка → Избранное`.")
    else:
        lines.append("")
        lines.append("Избранное: пока пусто. Открой объявление и нажми кнопку «Добавить в избранное».")
    return "\n".join(lines)
