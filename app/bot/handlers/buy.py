from __future__ import annotations

import logging
import re

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.state import (
    ensure_user,
    get_recent_public_ads,
    count_public_ads,
    get_public_ad,
    search_public_ads,
    filter_public_ads,
    count_filtered_public_ads,
    get_brand_by_name,
    add_favorite,
    get_favorites,
)
from ..ui.buttons import BUY_MENU_BUTTONS, BUY_TEXT_TO_BUTTON
from ..ui.texts import BUY_MENU_TEXT, BUY_PLACEHOLDER_RESPONSES

logger = logging.getLogger("app.bot.handlers.buy")

# Флаг ожидания текста поиска по пользователю
_SEARCH_WAIT: dict[str, bool] = {}
# Последний показанный список (для выбора по номеру) и кэш деталей
_LAST_CATALOG: dict[str, list[int]] = {}
_LAST_DETAILS: dict[str, dict[int, dict]] = {}
# Последний просмотренный ID для добавления в избранное
_LAST_VIEWED: dict[str, int] = {}
# Состояние фильтров и пагинации
_FILTER_STATE: dict[str, dict] = {}
PAGE_SIZE = 5


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
    :param button_id: ID выбранной кнопки (buy, buy_all, buy_filter, buy_favorites, buy_search).
    """
    ensure_user(sender, notification.event.get("senderData", {}).get("senderName"))
    if button_id == "buy":
        send_buy_menu(notification, sender)
        return
    if button_id == "buy_all":
        notification.answer(_build_catalog_text(sender))
        return
    if button_id == "buy_filter":
        notification.answer(_build_filter_text(sender))
        return
    if button_id == "buy_search":
        _SEARCH_WAIT[sender] = True
        notification.answer("Введите название авто для поиска (например, Toyota или Camry).")
        return
    if button_id == "buy_favorites":
        notification.answer(_build_favorites_text(sender))
        return
    notification.answer(BUY_PLACEHOLDER_RESPONSES.get(button_id, "Функция покупки пока в разработке."))


def handle_buy_text(notification: Notification, settings: Settings, sender: str, text: str) -> bool:
    """
    Преобразовать текстовые команды в нажатия кнопок раздела «Покупка».

    :return: True, если сообщение обработано.
    """
    cleaned = text.strip().lower()

    # Ожидание поискового запроса
    if _SEARCH_WAIT.pop(sender, False):
        notification.answer(_build_search_text(sender, cleaned))
        return True

    # Попытка открыть объявление по ID/номеру
    detail_id = _extract_public_id(sender, text)
    if detail_id is not None:
        notification.answer(_build_ad_detail(sender, detail_id))
        return True

    # Добавление в избранное после просмотра
    if cleaned in {"в избранное", "избранное", "добавить в избранное", "fav", "f+"}:
        last = _LAST_VIEWED.get(sender)
        if not last:
            notification.answer("Сначала откройте объявление по ID, потом можно добавить в избранное.")
            return True
        try:
            add_favorite(sender, last)
            notification.answer("Добавил в избранное.")
        except Exception:
            notification.answer("Не удалось добавить в избранное.")
        return True

    # Навигация по фильтрам/пагинации
    if cleaned in {"фильтры", "filter"}:
        notification.answer(_build_filter_text(sender))
        return True
    if cleaned in {"показать", "обновить"}:
        notification.answer(_render_filtered(sender))
        return True
    if cleaned in {"дальше", "вперед", "вперёд", "next"}:
        _shift_page(sender, 1)
        notification.answer(_render_filtered(sender))
        return True
    if cleaned in {"назад", "prev", "пред", "предыдущая"}:
        _shift_page(sender, -1)
        notification.answer(_render_filtered(sender))
        return True

    # Установка фильтров (цена/год/пробег/марка)
    if cleaned.startswith("цена"):
        notification.answer(_update_price_filter(sender, cleaned))
        return True
    if cleaned.startswith("год"):
        notification.answer(_update_year_filter(sender, cleaned))
        return True
    if cleaned.startswith("пробег"):
        notification.answer(_update_mileage_filter(sender, cleaned))
        return True
    if cleaned.startswith("марка"):
        notification.answer(_update_brand_filter(sender, cleaned))
        return True
    if cleaned == "сброс":
        _FILTER_STATE.pop(sender, None)
        notification.answer("Сбросил фильтры. Напиши «показать», чтобы увидеть все объявления.")
        return True

    key = BUY_TEXT_TO_BUTTON.get(cleaned)
    if not key:
        if cleaned in {"покупка", "buy"}:
            handle_buy_button(notification, settings, sender, "buy")
            return True
        return False
    handle_buy_button(notification, settings, sender, key)
    return True


def _build_catalog_text(sender: str, limit: int = 5) -> str:
    """
    Сформировать текстовую витрину объявлений.

    :param limit: Сколько записей показать пользователю.
    """
    total = count_public_ads()
    ads = get_recent_public_ads(limit)
    _LAST_CATALOG[sender] = [ad["id"] for ad in ads]
    _LAST_DETAILS[sender] = {ad["id"]: ad for ad in ads}
    if not ads:
        return "Пока нет активных объявлений. Как только они появятся, я пришлю список."
    lines = [f"Всего активных объявлений: {total}. Показываю последние {len(ads)}:"]
    for idx, ad in enumerate(ads, start=1):
        lines.append(
            f"{idx}. {ad['title']} — {ad['price']} ₽, {ad['year']} г., {ad['mileage']} км (ID#{ad['id']})"
        )
    lines.append("Чтобы открыть карточку — пришлите ID#, например ID42, или номер из списка.")
    return "\n".join(lines)


def _build_ad_detail(viewer: str, ad_id: int) -> str:
    # 1) сначала смотрим в кеш последней выдачи
    ad = None
    if viewer in _LAST_DETAILS and ad_id in _LAST_DETAILS[viewer]:
        ad = _LAST_DETAILS[viewer][ad_id]
    else:
        for cached in _LAST_DETAILS.values():
            if ad_id in cached:
                ad = cached[ad_id]
                break

    # 2) пробуем взять из БД
    if not ad:
        ad = get_public_ad(ad_id)

    # 3) если всё ещё нет — обновляем витрину и ищем среди последних
    if not ad:
        fresh = get_recent_public_ads(PAGE_SIZE)
        cache = _LAST_DETAILS.setdefault(viewer, {})
        for item in fresh:
            cache[item["id"]] = item
        ad = cache.get(ad_id)

    if not ad:
        return "Не нашёл активное объявление с таким ID."
    _LAST_VIEWED[viewer] = ad["id"]
    lines = [
        f"Объявление #{ad['id']}",
        ad["title"] or "Без названия",
        f"Цена: {ad['price']} ₽",
        f"Год: {ad['year']} | Пробег: {ad['mileage']} км",
        f"Статус: {ad['status']}",
    ]
    return "\n".join(lines)


def _build_search_text(sender: str, query: str, limit: int = 5) -> str:
    if len(query) < 2:
        return "Введите хотя бы 2 символа для поиска."
    ads = search_public_ads(query, limit)
    if not ads:
        return "Не нашёл объявлений по такому запросу."
    _LAST_CATALOG[sender] = [ad["id"] for ad in ads]
    lines = [f"Нашёл {len(ads)} объявлений:"]
    for idx, ad in enumerate(ads, start=1):
        lines.append(f"{idx}. {ad['title']} — {ad['price']} ₽, {ad['year']} г., {ad['mileage']} км (ID#{ad['id']})")
    lines.append("Пришлите номер из списка или ID#, чтобы открыть карточку.")
    return "\n".join(lines)


def _extract_public_id(sender: str, text: str) -> int | None:
    cleaned = text.strip().lower()
    if cleaned.startswith("id"):
        digits = re.findall(r"\d+", cleaned)
        if digits:
            return int(digits[0])
        return None
    if cleaned.isdigit():
        num = int(cleaned)
        # если был предыдущий список — позволяем выбирать по номеру
        ids = _LAST_CATALOG.get(sender) or []
        if 1 <= num <= len(ids):
            return ids[num - 1]
        return num
    return None


def _build_filter_text(sender: str) -> str:
    state = _FILTER_STATE.get(sender, {})
    year_desc = state.get("year", "любой")
    if state.get("min_year") or state.get("max_year"):
        year_desc = f"{state.get('min_year', 'от')} - {state.get('max_year', 'до')}"
    lines = [
        "Фильтры по объявлениям:",
        f"- Марка: {state.get('brand_name', 'любая')}",
        f"- Цена: {state.get('min_price', 'от')} - {state.get('max_price', 'до')}",
        f"- Год: {year_desc}",
        f"- Пробег: {state.get('min_mileage', 'от')} - {state.get('max_mileage', 'до')}",
        "",
        "Команды:",
        "• цена 100000-500000",
        "• год 2010   или   год 2010-2015",
        "• пробег 0-150000",
        "• марка Toyota",
        "• показать — применить фильтр, дальше/назад — листать страницы, сброс — очистить.",
    ]
    return "\n".join(lines)


def _render_filtered(sender: str) -> str:
    state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
    page = state.get("page", 0)
    size = state.get("page_size", PAGE_SIZE)
    total = count_filtered_public_ads(state)
    ads = filter_public_ads(state, page=page, page_size=size)
    _LAST_CATALOG[sender] = [ad["id"] for ad in ads]
    _LAST_DETAILS[sender] = {ad["id"]: ad for ad in ads}
    if not ads:
        return "По текущим фильтрам ничего не нашлось. Попробуйте «сброс» или измените параметры."
    total_pages = max(1, (total + size - 1) // size)
    lines = [f"Найдено: {total}. Страница {page + 1}/{total_pages}:"]
    for idx, ad in enumerate(ads, start=1):
        lines.append(f"{idx}. {ad['title']} — {ad['price']} ₽, {ad['year']} г., {ad['mileage']} км (ID#{ad['id']})")
    lines.append("Напиши номер или ID#, чтобы открыть, «дальше/назад» — листать, «сброс» — очистить фильтры.")
    return "\n".join(lines)


def _shift_page(sender: str, delta: int) -> None:
    state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
    page = state.get("page", 0) + delta
    state["page"] = max(0, page)


def _parse_range(text: str) -> tuple[int | None, int | None]:
    numbers = [int(x) for x in re.findall(r"\d+", text)]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], None
    return numbers[0], numbers[1]


def _update_price_filter(sender: str, text: str) -> str:
    low, high = _parse_range(text)
    state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
    state["min_price"], state["max_price"] = low, high
    state["page"] = 0
    return _render_filtered(sender)


def _update_year_filter(sender: str, text: str) -> str:
    low, high = _parse_range(text)
    state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
    if low and high and low != high:
        # если диапазон — используем как min/max года через mileage поля, но храним как год для простоты
        state["year"] = None
        state["min_year"], state["max_year"] = low, high
    else:
        state["year"] = low
        state.pop("min_year", None)
        state.pop("max_year", None)
    state["page"] = 0
    return _render_filtered(sender)


def _update_mileage_filter(sender: str, text: str) -> str:
    low, high = _parse_range(text)
    state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
    state["min_mileage"], state["max_mileage"] = low, high
    state["page"] = 0
    return _render_filtered(sender)


def _update_brand_filter(sender: str, text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "Укажите марку после слова «марка», например: марка Toyota"
    name = parts[1].strip()
    brand = get_brand_by_name(name)
    if not brand:
        return "Марка не найдена в базе. Попробуйте другое название."
    state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
    state["car_brand_id"] = brand.id
    state["brand_name"] = brand.name
    state["page"] = 0
    return _render_filtered(sender)


def _build_favorites_text(sender: str) -> str:
    ads = get_favorites(sender)
    if not ads:
        return "В избранном пусто. Откройте объявление и напишите «в избранное», чтобы сохранить."
    _LAST_CATALOG[sender] = [ad.id for ad in ads]
    _LAST_DETAILS[sender] = {ad.id: {
        "id": ad.id,
        "title": ad.title,
        "price": ad.price,
        "year": ad.year_car,
        "mileage": ad.mileage_km_car,
        "sender": ad.sender,
        "status": "активно" if ad.is_active else "в обработке",
    } for ad in ads}
    lines = ["Избранное:"]
    for idx, ad in enumerate(ads, start=1):
        lines.append(f"{idx}. {ad.title} — {ad.price} ₽, {ad.year_car} г., {ad.mileage_km_car} км (ID#{ad.id})")
    lines.append("Пришлите номер или ID#, чтобы открыть карточку.")
    return "\n".join(lines)
