from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import guard_sender, chat_sender
from ..services.state import ensure_user
from ..ui.buttons import MAIN_MENU_BUTTONS, TEXT_TO_BUTTON
from .profile import build_profile_text
from .sell import send_sell_menu, handle_sell_button, handle_sell_text
from .buy import handle_buy_option, handle_buy_text

logger = logging.getLogger("app.bot.handlers.menu")


def handle_main_menu(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Показать базовое меню (профиль/продажа/покупка)."""
    if not guard_sender(notification, allowed):
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    chat_id = notification.chat
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        "body": "Выберите действие:",
        "header": "Меню действий",
        "footer": "Выберите одну из опций",
        "buttons": MAIN_MENU_BUTTONS,
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )
    logger.debug("Главное меню отправлено для %s", sender)


def handle_menu_selection(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Обработчик reply-кнопок основного меню."""
    if not guard_sender(notification, allowed):
        return
    message_data = notification.event.get("messageData", {})
    button_data = (
        message_data.get("interactiveButtonsResponse")
        or message_data.get("buttonsResponseMessage")
        or message_data.get("templateButtonsReplyMessage")
    )
    if not button_data:
        return
    button_id = button_data.get("selectedButtonId") or button_data.get("selectedId")
    if not button_id:
        return
    _dispatch_button(notification, settings, button_id)


def handle_menu_text(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Обработать текстовые команды, соответствующие кнопкам."""
    if not guard_sender(notification, allowed):
        return
    text = notification.message_text
    if not text:
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))

    key = TEXT_TO_BUTTON.get(text.strip().lower())
    if key:
        _dispatch_button(notification, settings, key)
        return
    if handle_sell_text(notification, settings, sender, text):
        return
    if handle_buy_text(notification, settings, sender, text):
        return


def _dispatch_button(notification: Notification, settings: Settings, button_id: str) -> None:
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    if button_id == "profile":
        notification.answer(build_profile_text(sender))
    elif button_id.startswith("sell") or button_id == "sell":
        handle_sell_button(notification, settings, sender, button_id)
    elif button_id == "buy":
        handle_buy_option(notification, settings, sender, button_id)
