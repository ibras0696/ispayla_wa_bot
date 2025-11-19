from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import guard_sender, chat_sender
from ..services.state import ensure_user, get_balance
from ..services.forms import sell_form_manager
from ..ui.texts import START_TEXT
from .sell import handle_sell_text
from .buy import handle_buy_text

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
    """Ответить на /start и зарегистрировать пользователя."""
    if not guard_sender(notification, allowed):
        return
    ensure_user(chat_sender(notification), notification.event.get("senderData", {}).get("senderName"))
    notification.answer(START_TEXT)


def handle_balance(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Вывести баланс пользователя."""
    if not guard_sender(notification, allowed):
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    balance = get_balance(sender)
    notification.answer(f"Ваш баланс: {balance} ₽")


def handle_fallback(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Ловит все остальные сообщения и проксирует в мастер продажи."""
    if not guard_sender(notification, allowed):
        return
    if notification.event.get("typeWebhook") not in {"incomingMessageReceived", "outgoingMessageReceived"}:
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    message_data = notification.event.get("messageData", {})
    if sell_form_manager.has_state(sender):
        # Сначала проверяем, не прислал ли пользователь медиа
        media_response = sell_form_manager.handle_media(sender, message_data)
        if media_response:
            notification.answer(media_response)
            return
    incoming = _message_text(notification)
    if sell_form_manager.has_state(sender):
        reply = sell_form_manager.handle(sender, incoming)
        if reply:
            notification.answer(reply)
        return
    if incoming:
        if handle_sell_text(notification, settings, sender, incoming):
            return
        if handle_buy_text(notification, settings, sender, incoming):
            return
    logger.info("Получено сообщение от %s: %s", sender, incoming)
    if settings.auto_reply_text and settings.auto_reply_text.strip():
        notification.answer(settings.auto_reply_text)
