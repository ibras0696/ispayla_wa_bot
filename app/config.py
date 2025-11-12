from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import dotenv

dotenv.load_dotenv()


DEFAULT_BASE_URL = "https://api.green-api.com"
DEFAULT_AUTO_REPLY_TEXT = "Спасибо за сообщение! Мы свяжемся с вами в ближайшее время."


@dataclass(slots=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    id_instance: str
    api_token: str
    base_url: str = DEFAULT_BASE_URL
    webhook_secret: str | None = None
    auto_reply_text: str = DEFAULT_AUTO_REPLY_TEXT


@lru_cache(1)
def get_settings() -> Settings:
    """
    Прочитать переменные окружения и сформировать объект настроек.

    :return: объект Settings с параметрами Green API и текстом автоответа.
    :raises RuntimeError: если ID_INSTANCE или API_TOKEN отсутствуют.
    """
    id_instance = os.getenv("ID_INSTANCE")
    api_token = os.getenv("API_TOKEN")
    if not id_instance or not api_token:
        raise RuntimeError("ID_INSTANCE и API_TOKEN обязательны для работы Green API клиента.")

    return Settings(
        id_instance=id_instance,
        api_token=api_token,
        base_url=os.getenv("GREEN_API_BASE_URL", DEFAULT_BASE_URL),
        webhook_secret=os.getenv("WEBHOOK_SECRET"),
        auto_reply_text=os.getenv("AUTO_REPLY_TEXT", DEFAULT_AUTO_REPLY_TEXT),
    )
