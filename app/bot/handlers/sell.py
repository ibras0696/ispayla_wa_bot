from __future__ import annotations

import logging

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.state import ensure_user, get_ads_preview
from ..services.forms import sell_form_manager
from ..ui.buttons import SELL_MENU_BUTTONS, SELL_TEXT_TO_BUTTON

logger = logging.getLogger("app.bot.handlers.sell")


def send_sell_menu(notification: Notification, sender: str) -> None:
    """Отправить подменю, связанное с продажей авто."""
    chat_id = notification.chat
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        "body": "Продажа авто",
        "header": "Продажа",
        "footer": "Выберите действие",
        "buttons": SELL_MENU_BUTTONS,
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )
    logger.debug("Меню продажи отправлено для %s", sender)


def handle_sell_button(notification: Notification, settings: Settings, sender: str, button_id: str) -> None:
    """Обработать кнопки «Продажи» (создание объявления, список и т.д.)."""
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    if button_id == "sell":
        send_sell_menu(notification, sender)
    elif button_id == "sell_create":
        prompt = sell_form_manager.start(sender)
        notification.answer(prompt)
    elif button_id == "sell_list":
        notification.answer(_sell_list_text(sender))


def handle_sell_text(notification: Notification, settings: Settings, sender: str, text: str) -> bool:
    """Обработать текстовые команды, относящиеся к продаже."""
    key = SELL_TEXT_TO_BUTTON.get(text.strip().lower())
    if not key:
        return False
    handle_sell_button(notification, settings, sender, key)
    return True


def _sell_list_text(sender: str) -> str:
    total, active, ads = get_ads_preview(sender)
    if total == 0:
        return "У тебя пока нет объявлений. Нажми «Разместить объявление», чтобы добавить первое."
    lines = [f"Твои объявления: {total} шт. (активных {active})."]
    for idx, ad in enumerate(ads, start=1):
        title = getattr(ad, "title", None) or f"Объявление #{ad.id}"
        price = getattr(ad, "price", 0)
        status = "активно" if getattr(ad, "is_active", False) else "в обработке"
        lines.append(f"{idx}. {title} — {price} ₽ ({status}) ID#{ad.id}")
    if total > len(ads):
        lines.append("…Показаны последние объявления. Ответь номером или ID — скоро добавим переход.")
    return "\n".join(lines)
