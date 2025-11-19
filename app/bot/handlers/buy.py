from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.state import ensure_user
from ..ui.buttons import BUY_MENU_BUTTONS, BUY_TEXT_TO_BUTTON
from ..ui.texts import BUY_MENU_TEXT, BUY_PLACEHOLDER_RESPONSES

logger = logging.getLogger("app.bot.handlers.buy")


def send_buy_menu(notification: Notification, sender: str) -> None:
    """
    Отправить подменю для сценария покупки.

    :param notification: объект Green API с удобными методами ответа.
    :param sender: chatId пользователя, чтобы в логах видеть адресата.
    """
    chat_id = notification.chat
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        **BUY_MENU_TEXT,
        "buttons": BUY_MENU_BUTTONS,
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )
    logger.debug("Меню покупки отправлено для %s", sender)


def handle_buy_button(notification: Notification, settings: Settings, sender: str, button_id: str) -> None:
    """
    Обработать reply-кнопки из подменю «Покупка».

    :param notification: текущие данные события.
    :param settings: объект настроек (на будущее для фильтров/заглушек).
    :param sender: идентификатор отправителя.
    :param button_id: ID выбранной кнопки (buy, buy_all, buy_filter, buy_favorites).
    """
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    if button_id == "buy":
        send_buy_menu(notification, sender)
        return
    notification.answer(BUY_PLACEHOLDER_RESPONSES.get(button_id, "Функция покупки пока в разработке."))


def handle_buy_text(notification: Notification, settings: Settings, sender: str, text: str) -> bool:
    """
    Преобразовать текстовые команды в нажатия кнопок раздела «Покупка».

    :return: True, если сообщение обработано.
    """
    cleaned = text.strip().lower()
    key = BUY_TEXT_TO_BUTTON.get(cleaned)
    if not key:
        if cleaned in {"покупка", "buy"}:
            handle_buy_button(notification, settings, sender, "buy")
            return True
        return False
    handle_buy_button(notification, settings, sender, key)
    return True
