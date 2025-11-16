from __future__ import annotations

from whatsapp_chatbot_python import Notification

from ...config import Settings


def handle_buy_option(notification: Notification, settings: Settings, sender: str, button_id: str) -> None:
    """Пока просто сообщаем, что функциональность в разработке."""
    notification.answer(
        "Режим покупки скоро появится. Мы работаем над возможностью подбора авто по твоим фильтрам."
    )


def handle_buy_text(notification: Notification, settings: Settings, sender: str, text: str) -> bool:
    if text.strip().lower() not in {"покупка", "buy"}:
        return False
    handle_buy_option(notification, settings, sender, "buy")
    return True
