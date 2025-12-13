from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

logger = logging.getLogger("app.bot.guard")


def chat_sender(notification: Notification) -> str:
    """Извлечь chatId/sender из уведомления."""
    sender_data = notification.event.get("senderData", {}) or {}
    return sender_data.get("sender") or sender_data.get("chatId") or "unknown"


def sender_name(notification: Notification) -> str | None:
    sender_data = notification.event.get("senderData", {}) or {}
    return sender_data.get("senderName")


def is_sender_allowed(sender: str, allowed: set[str] | None) -> bool:
    """
    Проверить, входит ли отправитель в белый список ALLOWED_SENDERS.

    :param sender: значение вида 79...@c.us
    :param allowed: множество разрешённых отправителей или None
    """
    if not allowed:
        return True
    if sender in allowed:
        return True
    local_part = sender.split("@", 1)[0]
    return local_part in allowed


def guard_sender(notification: Notification, allowed: set[str] | None) -> bool:
    """
    Быстро выйти из обработчика, если сообщение пришло от неразрешённого чата.
    """
    sender = chat_sender(notification)
    if sender == "unknown":
        logger.warning("Не удалось определить отправителя: %s", notification.event)
        return False
    if is_sender_allowed(sender, allowed):
        return True
    logger.info("Игнорируем сообщение от %s — вне списка ALLOWED_SENDERS=%s.", sender, allowed)
    return False
