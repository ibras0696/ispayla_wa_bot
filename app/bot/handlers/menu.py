from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import guard_sender, chat_sender
from ..services.state import ensure_user, get_balance, get_user
from ..ui.buttons import MAIN_MENU_BUTTONS, TEXT_TO_BUTTON

logger = logging.getLogger("app.bot.handlers.menu")



def handle_main_menu(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
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
    logger.debug("Меню отправлено для %s", sender)


def _profile_text(sender: str) -> str:
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


def _send_menu_reply(notification: Notification, settings: Settings, sender: str, button_id: str | None) -> None:
    responses = {
        "profile": _profile_text(sender),
        "sell": (
            "Продажа авто (демо)\n"
            "- VIN: WBA00000000000000\n"
            "- Марка/модель: BMW 3-Series\n"
            "- Цена: 1 200 000 ₽\n"
            "- Статус: готовим форму публикации."
        ),
        "buy": (
            "Покупка авто (демо)\n"
            "- Бюджет: до 1 500 000 ₽\n"
            "- Пожелания: пробег < 100 тыс., не старше 2016 г.\n"
            "- Статус: подбор скоро станет доступен."
        ),
    }
    reply = responses.get(button_id, settings.auto_reply_text)
    if reply:
        logger.debug("Меню: %s выбрал %s", sender, button_id)
        notification.answer(reply)


def handle_menu_selection(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
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
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    _send_menu_reply(notification, settings, sender, button_id)


def handle_menu_text(notification: Notification, settings: Settings, allowed: set[str] | None) -> None:
    if not guard_sender(notification, allowed):
        return
    text = notification.message_text
    if not text:
        return
    button_id = TEXT_TO_BUTTON.get(text.strip().lower())
    if not button_id:
        return
    sender = chat_sender(notification)
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    _send_menu_reply(notification, settings, sender, button_id)
