"""Базовые обработчики: /start, баланс и fallback-сценарии."""

from __future__ import annotations

import logging
from collections import deque

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import guard_sender, chat_sender
from ..services.state import ensure_user, get_balance
from ..services.forms import sell_form_manager
from ..ui.texts import START_TEXT
from .sell import handle_sell_text
from .buy import handle_buy_text
from .buy import _reset_filters

logger = logging.getLogger("app.bot.handlers.basic")
# Короткий кэш обработанных idMessage, чтобы не отвечать дважды на outgoing/incoming пары
_PROCESSED_IDS: deque[str] = deque(maxlen=500)


def _message_text(notification: Notification) -> str:
    """
    Возвращает текст сообщения вне зависимости от типа payload'а Green API.

    Приходит либо ``textMessageData``, либо ``extendedTextMessageData`` —
    последовательно проверяем оба варианта и подстраховываемся пустой строкой.
    """
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
    _reset_filters(chat_sender(notification))
    notification.answer(START_TEXT)


def handle_balance(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """
    Возвращает баланс отправителя, предварительно удостоверившись, что он зарегистрирован.

    Для whitelisted пользователя создаёт запись, если её не было, и отвечает суммой в условных единицах.
    """
    if not guard_sender(notification, allowed):
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    balance = get_balance(sender)
    notification.answer(f"Ваш баланс: {balance} ₽")


def handle_fallback(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """
    Универсальный обработчик, который поддерживает мастер продажи и пытается распознать произвольный текст.

    Здесь же происходит загрузка медиа, продолжение сценария продажи, попытка запусков `handle_sell_text` /
    `handle_buy_text` и автосообщение, если ничего не подошло.
    """
    if not guard_sender(notification, allowed):
        return
    if notification.event.get("typeWebhook") not in {"incomingMessageReceived", "outgoingMessageReceived"}:
        return
    msg_id = notification.event.get("idMessage")
    if msg_id:
        if msg_id in _PROCESSED_IDS:
            return
        _PROCESSED_IDS.append(msg_id)
    msg_id = notification.event.get("idMessage")
    if msg_id:
        if msg_id in _PROCESSED_IDS:
            return
        _PROCESSED_IDS.add(msg_id)
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
