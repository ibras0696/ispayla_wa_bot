from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import guard_sender, chat_sender, sender_name
from ..services.state import ensure_user
from ..services.forms import sell_form_manager
from ..ui.buttons import MAIN_MENU_BUTTONS, TEXT_TO_BUTTON
from ..ui.texts import MAIN_MENU_TEXT
from .profile import build_profile_text
from .sell import send_sell_menu, handle_sell_button, handle_sell_text
from .buy import handle_buy_button, handle_buy_text

logger = logging.getLogger("app.bot.handlers.menu")


def handle_main_menu(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Показать базовое меню (профиль/продажа/покупка)."""
    if not guard_sender(notification, allowed):
        return
    sender = chat_sender(notification)
    ensure_user(sender, sender_name(notification))
    if sell_form_manager.has_state(sender):
        sell_form_manager.cancel(sender)
        notification.answer("Остановил создание объявления. Ты в главном меню.")
    chat_id = notification.chat
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        **MAIN_MENU_TEXT,
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
    _dispatch_button(notification, settings, allowed, button_id)


def handle_menu_text(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    """Обработать текстовые команды, соответствующие кнопкам."""
    if not guard_sender(notification, allowed):
        return
    text = notification.message_text
    if not text:
        return
    sender = chat_sender(notification)
    ensure_user(sender, sender_name(notification))

    normalized = text.strip().lower()
    key = TEXT_TO_BUTTON.get(normalized)
    if key:
        _dispatch_button(notification, settings, allowed, key)
        return
    if handle_buy_text(notification, settings, sender, text):
        return
    if handle_sell_text(notification, settings, sender, text):
        return


def _dispatch_button(notification: Notification, settings: Settings, allowed: set[str] | None, button_id: str) -> None:
    sender = chat_sender(notification)
    ensure_user(sender, sender_name(notification))
    if button_id == "profile":
        _send_profile_screen(notification, sender)
    elif button_id.startswith("sell") or button_id == "sell":
        handle_sell_button(notification, settings, sender, button_id)
    elif button_id == "buy":
        handle_buy_button(notification, settings, sender, button_id)
    elif button_id.startswith("buy_"):
        handle_buy_button(notification, settings, sender, button_id)
    elif button_id == "back_menu":
        handle_main_menu(notification, settings, allowed)


def _send_profile_screen(notification: Notification, sender: str) -> None:
    """Отправить профиль с интерактивной кнопкой возврата."""
    chat_id = chat_sender(notification)
    profile_text = build_profile_text(sender)
    if not chat_id:
        notification.answer(profile_text)
        notification.answer("Напиши 0 или 000, чтобы вернуться в меню.")
        return
    payload = {
        "chatId": chat_id,
        "header": "Профиль",
        "body": profile_text,
        "footer": "⬅️ Нажми «Назад» или отправь 0/000",
        "buttons": [{"buttonId": "back_menu", "buttonText": "⬅️ Назад"}],
    }
    try:
        notification.api.request(
            "POST",
            "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
            payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось отправить профиль с кнопкой: chat_id=%s err=%s", chat_id, exc)
        notification.answer(profile_text)
        _send_back_button(notification, title="Профиль")
    else:
        logger.debug("Профиль с кнопкой отправлен для %s", sender)


def _send_back_button(notification: Notification, title: str = "Меню") -> None:
    """Отправить кнопку «Назад» к главному меню."""
    # Берём chatId так же, как и в guard_sender/chat_sender — надёжнее, чем поле chat.
    from ..services.guard import chat_sender

    chat_id = chat_sender(notification)
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        "header": title,
        "body": "Вернуться в главное меню",
        "footer": "Нажми, чтобы открыть меню",
        "buttons": [{"buttonId": "back_menu", "buttonText": "⬅️ Назад"}],
    }
    try:
        notification.api.request(
            "POST",
            "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
            payload,
        )
        logger.debug("Отправил кнопку Назад: chat_id=%s payload=%s", chat_id, payload)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось отправить кнопку Назад: chat_id=%s payload=%s err=%s", chat_id, payload, exc)
