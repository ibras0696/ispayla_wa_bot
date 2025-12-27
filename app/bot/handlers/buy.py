from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from whatsapp_chatbot_python import Notification

from ...config import Settings
from ..services.guard import sender_name
from ..services.state import (
    ensure_user,
    get_recent_public_ads,
    count_public_ads,
    get_public_ad,
    get_public_ad_with_images,
    search_public_ads,
    filter_public_ads,
    count_filtered_public_ads,
    get_brand_by_name,
    add_favorite,
    get_favorites,
)
from ..ui.buttons import BUY_MENU_BUTTONS, BUY_TEXT_TO_BUTTON, BUY_NAV_BUTTONS, BACK_MENU_BUTTON
from ..ui.texts import BUY_MENU_TEXT, BUY_PLACEHOLDER_RESPONSES

logger = logging.getLogger("app.bot.handlers.buy")

# Файл для сохранения фильтров между рестартами
_STATE_FILE = Path("state_filters.json")

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


def _new_filter_state() -> dict:
    """Базовые значения фильтров/пагинации по умолчанию."""
    return {
        "page": 0,
        "page_size": PAGE_SIZE,
        "min_price": None,
        "max_price": None,
        "year": None,
        "min_year": None,
        "max_year": None,
        "min_mileage": None,
        "max_mileage": None,
        "car_brand_id": None,
        "brand_name": None,
        "region": None,
        "condition": None,
        "sort_by": "created",
        "sort_order": "desc",
    }


def _ensure_state(sender: str) -> dict:
    """Вернуть стейт пользователя, дополнив недостающие ключи."""
    template = _new_filter_state()
    state = _FILTER_STATE.setdefault(sender, template.copy())
    for key, default in template.items():
        state.setdefault(key, default)
    return state


_CONDITION_SYNONYMS = {
    "целый": "целый",
    "целая": "целый",
    "без дтп": "целый",
    "не битый": "целый",
    "небитый": "целый",
    "после дтп": "после дтп",
    "битый": "после дтп",
    "битая": "после дтп",
    "ремонт": "после дтп",
    "ремонтировался": "после дтп",
}

_SORT_PRICE_TOKENS = {"цена", "цене", "стоимость", "price"}
_SORT_DATE_TOKENS = {"дата", "датe", "новые", "new", "created"}
_ASC_TOKENS = {"возрастание", "возрастанию", "дешевле", "asc", "min", "минимум"}
_DESC_TOKENS = {"убывание", "убыванию", "дороже", "desc", "max", "максимум", "новые", "сначала новые"}


def _format_phone(sender: str | None) -> str:
    """Вернуть только номер без домена."""
    if not sender:
        return ""
    return sender.split("@", 1)[0]


def _load_filter_state() -> None:
    """Загрузить сохранённые фильтры с диска."""
    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _FILTER_STATE.update({k: v for k, v in data.items() if isinstance(v, dict)})
                for sender in list(_FILTER_STATE.keys()):
                    _ensure_state(sender)
        except Exception as exc:  # pragma: no cover
            logger.warning("Не удалось загрузить состояние фильтров: %s", exc)


def _persist_filter_state() -> None:
    """Сохранить фильтры на диск (простая JSON-персистенция)."""
    try:
        _STATE_FILE.write_text(json.dumps(_FILTER_STATE), encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        logger.warning("Не удалось сохранить состояние фильтров: %s", exc)


_load_filter_state()


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
        "buttons": BUY_MENU_BUTTONS + [BACK_MENU_BUTTON],
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
    ensure_user(sender, sender_name(notification))
    if button_id == "buy":
        _reset_filters(sender)
        send_buy_menu(notification, sender)
        return
    if button_id == "buy_all":
        _reset_filters(sender)
        logger.info("Кнопка buy_all: sender=%s state=%s", sender, _FILTER_STATE.get(sender))
        _send_catalog(notification, sender)
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
    if button_id == "buy_next":
        _shift_page(sender, 1)
        _send_catalog(notification, sender)
        return
    if button_id == "buy_prev":
        _shift_page(sender, -1)
        _send_catalog(notification, sender)
        return
    if button_id == "buy_refresh":
        logger.info("Кнопка buy_refresh: sender=%s state=%s", sender, _FILTER_STATE.get(sender))
        _send_catalog(notification, sender)
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
        logger.info("Запрос детали объявления: chat=%s id=%s, cache_ids=%s", sender, detail_id, _LAST_CATALOG.get(sender))
        detail_text, image_paths = _build_ad_detail(sender, detail_id)
        notification.answer(detail_text)
        for idx, path in enumerate(image_paths[:3], start=1):
            notification.answer_with_file(str(path), caption=f"Фото {idx}")
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
        _send_catalog(notification, sender)
        return True
    if cleaned in {"дальше", "вперед", "вперёд", "next"}:
        _shift_page(sender, 1)
        _send_catalog(notification, sender)
        return True
    if cleaned in {"назад", "prev", "пред", "предыдущая"}:
        _shift_page(sender, -1)
        _send_catalog(notification, sender)
        return True

    # Установка фильтров (цена/год/пробег/марка)
    if cleaned.startswith("цена"):
        notification.answer(_update_price_filter(sender, cleaned))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned.startswith("год"):
        notification.answer(_update_year_filter(sender, cleaned))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned.startswith("пробег"):
        notification.answer(_update_mileage_filter(sender, cleaned))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned.startswith("марка"):
        notification.answer(_update_brand_filter(sender, cleaned))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned.startswith("регион"):
        notification.answer(_update_region_filter(sender, text))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned.startswith("состояние"):
        notification.answer(_update_condition_filter(sender, text))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned.startswith("сорт"):
        notification.answer(_update_sorting(sender, text))
        _send_nav_buttons(notification, sender)
        return True
    if cleaned == "сброс":
        _reset_filters(sender)
        _send_catalog(notification, sender)
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
    Сформировать текстовую витрину объявлений с пагинацией.
    """
    return _render_filtered(sender)


def _build_ad_detail(viewer: str, ad_id: int) -> tuple[str, list[Path]]:
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

    if not ad:
        logger.info(
            "Не нашли объявление ad_id=%s viewer=%s keys=%s cache_for_viewer=%s",
            ad_id,
            viewer,
            list(_LAST_DETAILS.keys()),
            _LAST_DETAILS.get(viewer),
        )
        # Попробуем заново построить каталог для этого пользователя и взять из кэша
        refreshed = _render_filtered(viewer)
        ad = _LAST_DETAILS.get(viewer, {}).get(ad_id)
        if not ad:
            return "Не нашёл активное объявление с таким ID.", []
    _LAST_VIEWED[viewer] = ad["id"]
    contact_phone = _format_phone(ad.get("sender"))
    lines = [
        f"Объявление #{ad['id']}",
        ad["title"] or "Без названия",
        f"Модель: {ad.get('model') or '-'}",
        f"Цена: {ad['price']} ₽",
        f"Год: {ad['year']} | Пробег: {ad['mileage']} км",
        f"Состояние: {ad.get('condition') or '-'} | Регион: {ad.get('region') or '-'}",
        f"Статус: {ad['status']}",
        f"Контакты: {contact_phone or '—'}",
        f"WhatsApp: https://wa.me/{contact_phone}" if contact_phone else "",
    ]
    detail_text = "\n".join([ln for ln in lines if ln])

    # Попытка получить фото из БД (первые несколько изображений)
    ad_obj, images = get_public_ad_with_images(ad["id"])
    if images:
        paths = [Path(img.image_url) for img in images]
        existing = [p for p in paths if p.exists()]
        if not existing and paths:
            logger.info("Нет доступных файлов для фото объявления id=%s paths=%s", ad_id, paths)
        if existing:
            return detail_text, existing
    return detail_text, []


def _build_search_text(sender: str, query: str, limit: int = 5) -> str:
    if len(query) < 2:
        return "Введите хотя бы 2 символа для поиска."
    ads = search_public_ads(query, limit)
    if not ads:
        return "Не нашёл объявлений по такому запросу."
    _LAST_CATALOG[sender] = [ad["id"] for ad in ads]
    _LAST_DETAILS[sender] = {ad["id"]: ad for ad in ads}
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
        if num <= 0:
            return None
        # если был предыдущий список — позволяем выбирать по номеру
        ids = _LAST_CATALOG.get(sender) or []
        if (not ids) or num > len(ids):
            # Попробуем обновить кэш из базы (без отправки текста пользователю)
            _render_filtered(sender)
            ids = _LAST_CATALOG.get(sender) or []
        # приоритет: позиция в списке, потом прямой ID
        if ids and 1 <= num <= len(ids):
            return ids[num - 1]
        return num
    return None


def _build_filter_text(sender: str) -> str:
    state = _ensure_state(sender)
    year_desc = state.get("year", "любой")
    if state.get("min_year") or state.get("max_year"):
        year_desc = f"{state.get('min_year', 'от')} - {state.get('max_year', 'до')}"
    sort_label = "дате (новые сверху)"
    if state.get("sort_by") == "price":
        sort_label = "цене"
        if state.get("sort_order") == "asc":
            sort_label += " (дешевле → дороже)"
        else:
            sort_label += " (дороже → дешевле)"
    lines = [
        "⚙️ Текущие фильтры:",
        f"• Марка: {state.get('brand_name') or 'любая'}",
        f"• Цена: {state.get('min_price', 'от')} — {state.get('max_price', 'до')}",
        f"• Год: {year_desc}",
        f"• Пробег: {state.get('min_mileage', 'от')} — {state.get('max_mileage', 'до')}",
        f"• Регион: {state.get('region') or 'любой'}",
        f"• Состояние: {state.get('condition') or 'любое'}",
        f"• Сортировка: {sort_label}",
        "",
        "Примеры команд:",
        "цена 100000-500000",
        "год 2010  или  год 2010-2015",
        "пробег 0-150000",
        "марка Toyota",
        "регион Грозный  (или «регион любой» для сброса)",
        "состояние целый  или  состояние после ДТП",
        "сортировка цена дешевле (или «сортировка дата»)",
        "",
        "Дополнительно: «показать» — применить фильтры, «дальше/назад» — листать, «сброс» — очистить.",
    ]
    return "\n".join(lines)


def _render_filtered(sender: str) -> str:
    state = _ensure_state(sender)
    page = state.get("page", 0)
    size = state.get("page_size", PAGE_SIZE)
    total = count_filtered_public_ads(state)
    ads = filter_public_ads(state, page=page, page_size=size)
    _LAST_CATALOG[sender] = [ad["id"] for ad in ads]
    _LAST_DETAILS[sender] = {ad["id"]: ad for ad in ads}
    logger.info("Рендер каталога: sender=%s page=%s total=%s ids=%s", sender, page, total, _LAST_CATALOG.get(sender))
    if not ads:
        return "Пока нет объявлений под эти фильтры. Напиши «сброс» или «покупка», чтобы начать заново."
    total_pages = max(1, (total + size - 1) // size)
    sort_desc = "новые сверху"
    if state.get("sort_by") == "price":
        sort_desc = "дороже → дешевле"
        if state.get("sort_order") == "asc":
            sort_desc = "дешевле → дороже"
    lines = [
        f"Каталог: {total} шт. Страница {page + 1}/{total_pages} | Сортировка: {sort_desc}",
    ]
    for idx, ad in enumerate(ads, start=1):
        lines.append(f"{idx}. {ad['title']} — {ad['price']} ₽, {ad['year']} г., {ad['mileage']} км (ID#{ad['id']})")
    lines.append("Напиши номер из списка или ID#, чтобы открыть. «дальше/назад» — листать, «сброс» — очистить.")
    return "\n".join(lines)


def _send_catalog(notification: Notification, sender: str) -> None:
    """
    Отправить текущую страницу каталога и кнопки навигации.

    :param notification: текущий апдейт для доступа к API.
    :param sender: идентификатор чата.
    """
    chat_id = notification.chat
    if not chat_id:
        return
    text = _render_filtered(sender)
    buttons = _nav_buttons(sender)
    if not buttons:
        notification.answer(text)
        return
    payload = {
        "chatId": chat_id,
        "body": text,
        "header": "Каталог объявлений",
        "footer": "Используй кнопки для навигации",
        "buttons": buttons,
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )


def _send_nav_buttons(notification: Notification, sender: str) -> None:
    """Отправить только кнопки навигации (после изменения фильтра)."""
    chat_id = notification.chat
    if not chat_id:
        return
    buttons = _nav_buttons(sender)
    if not buttons:
        return
    payload = {
        "chatId": chat_id,
        "body": "Фильтры обновлены. Используй кнопки, чтобы листать каталог.",
        "header": "Навигация каталога",
        "footer": "⬅️ Назад / ➡️ Дальше / Обновить",
        "buttons": buttons,
    }
    notification.api.request(
        "POST",
        "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
        payload,
    )


def _nav_buttons(sender: str) -> list[dict]:
    """Сформировать кнопки навигации (prev/next/refresh) исходя из числа страниц."""
    state = _ensure_state(sender)
    page = state.get("page", 0)
    size = state.get("page_size", PAGE_SIZE)
    total = count_filtered_public_ads(state)
    total_pages = max(1, (total + size - 1) // size)
    buttons: list[dict] = []
    if page > 0:
        buttons.append(BUY_NAV_BUTTONS[0])  # prev
    if page + 1 < total_pages:
        buttons.append(BUY_NAV_BUTTONS[1])  # next
    buttons.append(BUY_NAV_BUTTONS[2])  # refresh
    buttons.append(BACK_MENU_BUTTON)
    return buttons


def _shift_page(sender: str, delta: int) -> None:
    state = _ensure_state(sender)
    page = state.get("page", 0) + delta
    state["page"] = max(0, page)
    _persist_filter_state()


def _parse_range(text: str) -> tuple[int | None, int | None]:
    numbers = [int(x) for x in re.findall(r"\d+", text)]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], None
    return numbers[0], numbers[1]


def _update_price_filter(sender: str, text: str) -> str:
    low, high = _parse_range(text)
    state = _ensure_state(sender)
    state["min_price"], state["max_price"] = low, high
    state["page"] = 0
    _persist_filter_state()
    return _render_filtered(sender)


def _reset_filters(sender: str) -> None:
    """Сбросить фильтры и вернуть пользователя на первую страницу каталога."""
    _FILTER_STATE[sender] = _new_filter_state()
    _LAST_CATALOG.pop(sender, None)
    _LAST_DETAILS.pop(sender, None)
    _LAST_VIEWED.pop(sender, None)
    _SEARCH_WAIT.pop(sender, None)
    _persist_filter_state()


def _update_year_filter(sender: str, text: str) -> str:
    low, high = _parse_range(text)
    state = _ensure_state(sender)
    if low and high and low != high:
        # если диапазон — используем как min/max года через mileage поля, но храним как год для простоты
        state["year"] = None
        state["min_year"], state["max_year"] = low, high
    else:
        state["year"] = low
        state.pop("min_year", None)
        state.pop("max_year", None)
    state["page"] = 0
    _persist_filter_state()
    return _render_filtered(sender)


def _update_mileage_filter(sender: str, text: str) -> str:
    low, high = _parse_range(text)
    state = _ensure_state(sender)
    state["min_mileage"], state["max_mileage"] = low, high
    state["page"] = 0
    _persist_filter_state()
    return _render_filtered(sender)


def _update_brand_filter(sender: str, text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "Укажите марку после слова «марка», например: марка Toyota"
    name = parts[1].strip()
    brand = get_brand_by_name(name)
    if not brand:
        return "Марка не найдена в базе. Попробуйте другое название."
    state = _ensure_state(sender)
    state["car_brand_id"] = brand.id
    state["brand_name"] = brand.name
    state["page"] = 0
    _persist_filter_state()
    return _render_filtered(sender)


def _update_region_filter(sender: str, text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "Укажите регион после слова «регион», например: регион Грозный"
    region = parts[1].strip()
    state = _ensure_state(sender)
    if not region or region in {"любой", "-", "any"}:
        state["region"] = None
    else:
        if len(region) < 2:
            return "Название региона должно быть длиннее 1 символа."
        state["region"] = region.title()
    state["page"] = 0
    _persist_filter_state()
    return _render_filtered(sender)


def _normalize_condition(value: str) -> tuple[str | None, bool]:
    cleaned = value.strip().lower()
    if not cleaned or cleaned in {"любой", "-", "any"}:
        return None, True
    canonical = _CONDITION_SYNONYMS.get(cleaned)
    return canonical, canonical is not None


def _update_condition_filter(sender: str, text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "Укажите состояние после слова «состояние»: целый или после ДТП."
    canonical, ok = _normalize_condition(parts[1])
    if not ok:
        return "Не понял состояние. Напишите «состояние целый» или «состояние после ДТП»."
    state = _ensure_state(sender)
    state["condition"] = canonical
    state["page"] = 0
    _persist_filter_state()
    return _render_filtered(sender)


def _strip_sort_command(text: str) -> str:
    cleaned = text.strip().lower()
    for prefix in ("сортировка", "сорт"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    if cleaned.startswith("по "):
        cleaned = cleaned[3:]
    return cleaned


def _update_sorting(sender: str, text: str) -> str:
    body = _strip_sort_command(text)
    if not body:
        return "Укажите что сортировать: «сорт цена» или «сорт дата»."
    tokens = body.split()
    key_token = tokens[0]
    sort_by = "created"
    if key_token in _SORT_PRICE_TOKENS:
        sort_by = "price"
    elif key_token in _SORT_DATE_TOKENS:
        sort_by = "created"
    else:
        # неизвестный ключ — оставляем прежний и подсказываем пользователю
        return "Пишите «сорт цена» или «сорт дата» (по умолчанию новые сверху)."

    sort_order = "desc"
    if any(tok in _ASC_TOKENS for tok in tokens[1:]):
        sort_order = "asc"
    elif any(tok in _DESC_TOKENS for tok in tokens[1:]):
        sort_order = "desc"
    else:
        # если пользователь выбрал цену, но не указал направление — оставляем дороже→дешевле
        sort_order = "desc" if sort_by == "created" else "desc"

    state = _ensure_state(sender)
    state["sort_by"] = sort_by
    state["sort_order"] = sort_order
    state["page"] = 0
    _persist_filter_state()
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
