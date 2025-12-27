from __future__ import annotations

import logging

import re
from pathlib import Path

from typing import Dict

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import sender_name
from ..services.state import ensure_user, get_ads_preview, get_ad_with_images
from ..services.forms import sell_form_manager
from ..ui.buttons import SELL_MENU_BUTTONS, SELL_TEXT_TO_BUTTON, BACK_MENU_BUTTON
from ..ui.texts import SELL_MENU_TEXT

logger = logging.getLogger("app.bot.handlers.sell")

_LAST_SUMMARIES: Dict[str, list[int]] = {}


def send_sell_menu(notification: Notification, sender: str) -> None:
    """Отправить подменю, связанное с продажей авто."""
    chat_id = notification.chat
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        **SELL_MENU_TEXT,
        "buttons": SELL_MENU_BUTTONS + [BACK_MENU_BUTTON],
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )
    logger.debug("Меню продажи отправлено для %s", sender)


def handle_sell_button(notification: Notification, settings: Settings, sender: str, button_id: str) -> None:
    """Обработать кнопки «Продажи» (создание объявления, список и т.д.)."""
    ensure_user(sender, sender_name(notification))
    if button_id == "sell":
        send_sell_menu(notification, sender)
    elif button_id == "sell_create":
        prompt = sell_form_manager.start(sender)
        notification.answer(prompt)
    elif button_id == "sell_list":
        notification.answer(_sell_list_text(sender))
        _send_back_button(notification)
        notification.answer("Чтобы вернуться в меню, нажми «⬅️ В меню» или напиши «меню».")


def handle_sell_text(notification: Notification, settings: Settings, sender: str, text: str) -> bool:
    """Обработать текстовые команды, относящиеся к продаже."""
    detail_id = _extract_detail_request(sender, text)
    if detail_id is not None:
        _send_ad_detail(notification, sender, detail_id)
        return True
    key = SELL_TEXT_TO_BUTTON.get(text.strip().lower())
    if not key:
        return False
    handle_sell_button(notification, settings, sender, key)
    return True


def _sell_list_text(sender: str) -> str:
    """Подготовить текст списка объявлений и запомнить порядок."""
    total, active, summary = get_ads_preview(sender)
    if total == 0:
        return "У тебя пока нет объявлений. Нажми «Разместить объявление», чтобы добавить первое."
    _LAST_SUMMARIES[sender] = [item["id"] for item in summary]
    lines = [f"Твои объявления: {total} шт. (активных {active})."]
    for idx, item in enumerate(summary, start=1):
        lines.append(
            f"{idx}. {item['title']} — {item['price']} ₽ ({item['status']}) ID#{item['id']}"
        )
    if total > len(summary):
        lines.append("Показаны последние объявления. Напиши цифру из списка или ID#, чтобы открыть карточку.")
    else:
        lines.append("Напиши цифру (1, 2, …) или ID#, чтобы открыть и увидеть фото.")
    return "\n".join(lines)


def _extract_detail_request(sender: str, text: str) -> int | None:
    """Извлечь ID объявления по команде (номер, ID, короткая форма)."""
    cleaned = text.strip().lower()
    if cleaned.startswith("id"):
        digits = re.findall(r"\d+", cleaned)
        if digits:
            return int(digits[0])
        return None
    if cleaned.startswith("объявление"):
        digits = re.findall(r"\d+", cleaned)
        if digits:
            return _resolve_index(sender, int(digits[0]))
        return None
    # если просто цифра
    if cleaned.isdigit():
        return _resolve_index(sender, int(cleaned))
    return None


def _resolve_index(sender: str, idx: int) -> int | None:
    current = _LAST_SUMMARIES.get(sender)
    if current and 1 <= idx <= len(current):
        return current[idx - 1]
    # если нет кэша со списком, пробуем трактовать цифру как прямой ID
    return idx if idx > 0 else None


def _send_ad_detail(notification: Notification, sender: str, ad_id: int) -> None:
    """Отправить карточку объявления и первое фото."""
    ad, images = get_ad_with_images(sender, ad_id)
    if not ad:
        notification.answer("Не нашёл объявление с таким номером.")
        return
    lines = [
        f"Объявление #{ad.id}",
        ad.title or "Без названия",
        f"Статус: {'активно' if ad.is_active else 'в обработке'}",
        f"Цена: {ad.price or 0} ₽",
        f"Марка/модель: {ad.car_brand_id or '-'} / {ad.model_name or '-'}",
        f"Год: {ad.year_car} | Пробег: {ad.mileage_km_car} км",
        f"Регион: {ad.region or '-'} | Состояние: {ad.condition or '-'}",
        f"VIN: {ad.vin_number}",
        "",
        "Описание:",
        (ad.description or "-"),
    ]
    notification.answer("\n".join(lines))
    if images:
        for idx, img in enumerate(images, start=1):
            path = Path(img.image_url)
            if path.exists():
                notification.answer_with_file(str(path), caption=f"Фото {idx}")


def _send_back_button(notification: Notification) -> None:
    """Отправить кнопку назад в главное меню."""
    chat_id = notification.chat
    if not chat_id:
        return
    payload = {
        "chatId": chat_id,
        "header": "Мои объявления",
        "body": "Вернуться в меню",
        "footer": "Нажми, чтобы открыть главное меню",
        "buttons": [{"buttonId": "back_menu", "buttonText": "⬅️ В меню"}],
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )
