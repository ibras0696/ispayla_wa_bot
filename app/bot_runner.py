from __future__ import annotations

import asyncio
import logging
from typing import Any

from whatsapp_chatbot_python import GreenAPIBot, Notification

from .config import get_settings
from .database.crude import crud_manager

logger = logging.getLogger("app.bot")
logging.basicConfig(level=logging.INFO)

# Глобально подгружаем настройки один раз и создаём экземпляр бота.
settings = get_settings()

bot = GreenAPIBot(
    settings.id_instance,
    settings.api_token,
    bot_debug_mode=True,
)


def _safe_get(data: dict[str, Any], *keys: str) -> Any | None:
    """
    Безопасно пройти по цепочке ключей в словаре.

    :param data: исходный словарь.
    :param keys: последовательность ключей для доступа.
    :return: найденное значение или None, если что-то отсутствует.
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _chat_sender(notification: Notification) -> str:
    """
    Извлечь идентификатор отправителя из уведомления.

    :param notification: объект уведомления Green API.
    :return: sender/chatId или строка 'unknown'.
    """
    sender_data = notification.event.get("senderData", {}) or {}
    return sender_data.get("sender") or sender_data.get("chatId") or "unknown"


def _sender_name(notification: Notification) -> str | None:
    """
    Достать человекочитаемое имя отправителя.

    :param notification: объект уведомления.
    :return: имя отправителя или None.
    """
    sender_data = notification.event.get("senderData", {}) or {}
    return sender_data.get("senderName")


async def _ensure_user(sender: str, username: str | None) -> None:
    """
    Убедиться, что пользователь присутствует в таблице users.

    :param sender: WhatsApp sender/chatId.
    :param username: имя пользователя, если известно.
    """
    try:
        await crud_manager.user.add(sender=sender, username=username)
    except Exception:
        logger.exception("Не удалось создать/обновить пользователя %s", sender)


async def _get_balance(sender: str) -> int:
    """
    Вернуть текущий баланс пользователя.

    :param sender: WhatsApp sender/chatId.
    :return: баланс пользователя или 0, если запись не найдена.
    """
    user = await crud_manager.user.get_by_sender(sender)
    return user.balance if user else 0


def ensure_user(notification: Notification) -> None:
    """
    Синхронная обёртка, которая вызывает асинхронное создание пользователя.

    :param notification: входящее уведомление.
    """
    sender = _chat_sender(notification)
    if sender == "unknown":
        logger.warning("Не удалось определить отправителя из уведомления: %s", notification.event)
        return
    name = _sender_name(notification)
    asyncio.run(_ensure_user(sender, name))


def get_balance(sender: str) -> int:
    """
    Синхронно получить баланс пользователя.

    :param sender: WhatsApp sender/chatId.
    :return: текущее значение баланса.
    """
    if sender == "unknown":
        return 0
    return asyncio.run(_get_balance(sender))


def message_text(notification: Notification) -> str:
    """
    Извлечь текстовую часть сообщения из уведомления.

    :param notification: объект Notification.
    :return: текст сообщения или пустая строка.
    """
    text = _safe_get(notification.event, "messageData", "textMessageData", "textMessage")
    return text or ""


@bot.router.message(command="start")
def start_handler(notification: Notification) -> None:
    """
    Обработчик команды /start.

    :param notification: входящее уведомление.
    """
    ensure_user(notification)
    notification.answer(
        "Привет! Это базовый бот на Green API. "
        "Напишите `баланс`, чтобы увидеть тестовые данные."
    )


@bot.router.message(text_message="баланс")
def balance_handler(notification: Notification) -> None:
    """
    Ответить на сообщение 'баланс' значением из базы.

    :param notification: входящее уведомление.
    """
    ensure_user(notification)
    sender = _chat_sender(notification)
    balance = get_balance(sender)
    notification.answer(f"Ваш баланс: {balance} ₽")


@bot.router.message()
def fallback_handler(notification: Notification) -> None:
    """
    Обработчик по умолчанию для всех остальных сообщений.

    :param notification: входящее уведомление.
    """
    ensure_user(notification)
    incoming = message_text(notification)
    logger.info("Получено сообщение от %s: %s", _chat_sender(notification), incoming)
    notification.answer(settings.auto_reply_text)


def main() -> None:
    """Точка входа для запуска Green API бота."""
    logger.info("Запускаем бота Green API (инстанс %s).", settings.id_instance)
    bot.run_forever()


if __name__ == "__main__":
    main()
