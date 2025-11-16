from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import guard_sender, chat_sender
from ..services.state import ensure_user, get_balance

logger = logging.getLogger("app.bot.handlers.basic")


def _message_text(notification: Notification) -> str:
    message_data = notification.event.get("messageData", {})
    text_data = message_data.get("textMessageData")
    if text_data and text_data.get("textMessage"):
        return text_data["textMessage"]
    extended = message_data.get("extendedTextMessageData")
    if extended and extended.get("text"):
        return extended["text"]
    return ""


def handle_start(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    if not guard_sender(notification, allowed):
        return
    ensure_user(chat_sender(notification), notification.event.get("senderData", {}).get("senderName"))
    notification.answer(
        "Привет! Это базовый бот на Green API. "
        "Напишите `баланс`, чтобы увидеть тестовые данные."
    )


def handle_balance(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    if not guard_sender(notification, allowed):
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    balance = get_balance(sender)
    notification.answer(f"Ваш баланс: {balance} ₽")


def handle_fallback(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    if not guard_sender(notification, allowed):
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    incoming = _message_text(notification)
    logger.info("Получено сообщение от %s: %s", sender, incoming)
    if settings.auto_reply_text and settings.auto_reply_text.strip():
        notification.answer(settings.auto_reply_text)
