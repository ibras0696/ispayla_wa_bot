from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime
from pathlib import Path
import logging
import uuid

import requests

from .state import create_ad_from_form

CANCEL_WORDS = {"отмена", "cancel", "стоп", "stop", "меню", "menu"}
MEDIA_MESSAGE_TYPES = {"imageMessage", "documentMessage"}
MAX_PHOTOS = 3
POSTGRES_INT_MAX = 2_147_483_647

logger = logging.getLogger("app.bot.forms")


UPLOAD_DIR = Path("media/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SellFormState:
    """Хранит ответы пользователя и список фото."""

    step_index: int = 0
    data: dict = field(default_factory=dict)
    photos: list[str] = field(default_factory=list)


class SellFormManager:
    """Простейшее состояние мастера продажи."""

    def __init__(self) -> None:
        self._states: Dict[str, SellFormState] = {}

    def start(self, sender: str) -> str:
        """Создать состояние и вернуть первый вопрос."""
        state = SellFormState()
        self._states[sender] = state
        return (
            "Запускаем оформление продажи. Можно написать 'отмена', чтобы выйти.\n"
            f"{SELL_FORM_STEPS[0]['prompt']}"
        )

    def cancel(self, sender: str) -> None:
        """Сбросить мастер."""
        self._states.pop(sender, None)

    def has_state(self, sender: str) -> bool:
        """Есть ли активный мастер у пользователя."""
        return sender in self._states

    def handle(self, sender: str, message: str | None) -> str:
        """Обработать текстовые ответы."""
        if sender not in self._states:
            return ""
        if not message:
            return "Нужно ответить текстом. Повтори, пожалуйста."

        text = message.strip()
        if text.lower() in CANCEL_WORDS:
            self.cancel(sender)
            return "Окей, отменили создание объявления. Напиши «меню», чтобы вернуться в главное меню."

        state = self._states[sender]
        step = SELL_FORM_STEPS[state.step_index]
        if step.get("type") == "photos":
            if text.lower() in {"готово", "done"}:
                if not state.photos:
                    return "Добавь хотя бы одно фото перед завершением."
                state.data["photos"] = list(state.photos)
                state.data["photos"] = list(state.photos)
                state.step_index += 1
            else:
                return "Отправь фотографию (как вложение) или напиши 'готово', когда закончишь."
        else:
            validator = step["validator"]
            try:
                value = validator(text)
            except ValueError as err:
                return f"Ошибка: {err}. {step['prompt']}"
            state.data[step["key"]] = value
            state.step_index += 1

        if state.step_index >= len(SELL_FORM_STEPS):
            try:
                ad = create_ad_from_form(sender, state.data)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Ошибка при сохранении объявления для %s", sender)
                self.cancel(sender)
                return f"Не удалось сохранить объявление: {exc}. Попробуй позже."
            else:
                self.cancel(sender)
                return (
                    "Объявление сохранено!\n"
                    f"ID: {ad.id}. Статус: {'активно' if ad.is_active else 'на модерации'}.\n"
                    "В ближайшее время модератор проверит данные.\n"
                    "Чтобы вернуться в меню, нажми кнопку «⬅️ В меню» или напиши «меню»."
                )

        next_prompt = SELL_FORM_STEPS[state.step_index]["prompt"]
        return next_prompt

    def handle_media(self, sender: str, message_data: dict) -> str:
        """Сохранить фото, если мастер ждёт вложение."""
        state = self._states.get(sender)
        if not state:
            return ""
        step = SELL_FORM_STEPS[state.step_index]
        if step.get("type") != "photos":
            return ""
        if message_data.get("typeMessage") not in MEDIA_MESSAGE_TYPES:
            return ""
        download_url, filename = _extract_media(message_data)
        if not download_url:
            return "Не смог прочитать вложение. Пришли фото ещё раз."
        try:
            saved_path = _save_media(download_url, filename, sender)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка загрузки фото: %s", exc)
            return "Не удалось сохранить фото. Попробуй ещё раз."
        state.photos.append(str(saved_path))
        if len(state.photos) >= MAX_PHOTOS:
            state.data["photos"] = list(state.photos)
            state.step_index += 1
            return "Достаточно фото, напиши 'готово' для завершения."
        return f"Фото сохранено ({len(state.photos)}). Отправь ещё или напиши 'готово'."

sell_form_manager = SellFormManager()


def _validate_text(value: str, field_name: str, min_length: int = 3) -> str:
    """Убедиться, что строка не короче минимального порога."""
    cleaned = value.strip()
    if len(cleaned) < min_length:
        raise ValueError(f"{field_name} слишком короткий")
    return cleaned


def _validate_price(value: str) -> int:
    """Преобразовать цену в int и проверить допустимый диапазон."""
    try:
        price = int(value.replace(" ", ""))
    except ValueError:
        raise ValueError("Цена должна быть числом")
    if price <= 0:
        raise ValueError("Цена должна быть больше 0")
    if price > POSTGRES_INT_MAX:
        raise ValueError("Цена должна быть меньше или равна 2 147 483 647.")
    return price


def _validate_year(value: str) -> int:
    """Проверить, что год в разумных пределах."""
    try:
        year = int(value)
    except ValueError:
        raise ValueError("Год должен быть числом")
    current_year = datetime.utcnow().year + 1
    if not (1950 <= year <= current_year):
        raise ValueError("Год вне допустимого диапазона")
    return year


def _validate_mileage(value: str) -> int:
    """Парсинг пробега."""
    try:
        mileage = int(value.replace(" ", ""))
    except ValueError:
        raise ValueError("Пробег должен быть числом")
    if mileage < 0:
        raise ValueError("Пробег не может быть отрицательным")
    if mileage > POSTGRES_INT_MAX:
        raise ValueError("Mileage must be less than or equal to 2 147 483 647 km.")
    return mileage


def _validate_photos(value: str) -> list[str]:
    raise ValueError("Отправь фотографию как вложение, не текстом.")

def _validate_region(value: str) -> str:
    """Проверить регион."""
    return _validate_text(value, "Регион", 2)


def _validate_condition(value: str) -> str:
    """Привести состояние к каноническому виду."""
    cleaned = value.strip().lower()
    if cleaned in {"целый", "целая", "без дтп", "не битый", "небитый"}:
        return "целый"
    if cleaned in {"после дтп", "битый", "битая", "ремонт", "ремонтировался"}:
        return "после дтп"
    raise ValueError("Укажи состояние: целый или после ДТП")


SELL_FORM_STEPS = [
    {"key": "title", "prompt": "1️⃣ Введи заголовок объявления:", "validator": lambda v: _validate_text(v, "Заголовок")},
    {"key": "description", "prompt": "2️⃣ Опиши автомобиль (комплектация, состояние):", "validator": lambda v: _validate_text(v, "Описание", 10)},
    {"key": "price", "prompt": "3️⃣ Укажи цену в рублях:", "validator": _validate_price},
    {"key": "brand", "prompt": "4️⃣ Марка (например, Toyota):", "validator": lambda v: _validate_text(v, "Марка", 2)},
    {"key": "model", "prompt": "5️⃣ Модель (например, Camry):", "validator": lambda v: _validate_text(v, "Модель", 1)},
    {"key": "year", "prompt": "6️⃣ Год выпуска:", "validator": _validate_year},
    {"key": "mileage", "prompt": "7️⃣ Пробег (км):", "validator": _validate_mileage},
    {"key": "vin", "prompt": "8️⃣ VIN-номер (17 символов):", "validator": lambda v: _validate_text(v, "VIN", 5)},
    {"key": "region", "prompt": "9️⃣ Регион продажи (например, Грозный):", "validator": _validate_region},
    {"key": "condition", "prompt": "🔟 Состояние авто (целый / после ДТП):", "validator": _validate_condition},
    {
        "key": "photos",
        "prompt": "1️⃣1️⃣ Прикрепи фото автомобиля (до 3 шт, можно по одному). Когда закончишь, напиши 'готово'.",
        "validator": _validate_photos,
        "type": "photos",
    },
]


def _extract_media(message_data: dict) -> tuple[str | None, str | None]:
    """Вернуть URL и исходное имя файла из сообщения."""
    file_data = message_data.get("fileMessageData") or message_data.get("imageMessageData")
    if not file_data:
        return None, None
    return file_data.get("downloadUrl"), file_data.get("fileName")


def _save_media(url: str, filename: str | None, sender: str) -> Path:
    """Скачать файл и сохранить в локальную папку uploads."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    ext = Path(filename).suffix if filename else ".jpg"
    clean_ext = ext if ext else ".jpg"
    new_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}{clean_ext}"
    path = UPLOAD_DIR / new_name
    path.write_bytes(response.content)
    return path
