from __future__ import annotations

import logging

from whatsapp_chatbot_python import GreenAPIBot

from ..config import Settings, get_settings
from .handlers import (
    handle_start,
    handle_balance,
    handle_fallback,
    handle_main_menu,
    handle_menu_selection,
    handle_menu_text,
)
from .services.state import init_background_loop


def create_bot(settings: Settings | None = None) -> GreenAPIBot:
    settings = settings or get_settings()
    init_background_loop()

    bot = GreenAPIBot(
        settings.id_instance,
        settings.api_token,
        bot_debug_mode=True,
    )

    allowed = settings.allowed_senders

    def wrap(handler):
        def _inner(notification):
            return handler(notification, settings, allowed)
        return _inner

    bot.router.message(command="start")(wrap(handle_start))
    bot.router.outgoing_message(command="start")(wrap(handle_start))
    bot.router.outgoing_api_message(command="start")(wrap(handle_start))

    bot.router.message(text_message="баланс")(wrap(handle_balance))
    bot.router.outgoing_message(text_message="баланс")(wrap(handle_balance))
    bot.router.outgoing_api_message(text_message="баланс")(wrap(handle_balance))

    bot.router.message(text_message=["0", "00", "000"])(wrap(handle_main_menu))
    bot.router.outgoing_message(text_message=["0", "00", "000"])(wrap(handle_main_menu))

    bot.router.message(type_message=["buttonsResponseMessage", "templateButtonsReplyMessage", "interactiveButtonsResponse"])(wrap(handle_menu_selection))
    bot.router.outgoing_message(type_message=["buttonsResponseMessage", "templateButtonsReplyMessage", "interactiveButtonsResponse"])(wrap(handle_menu_selection))

    menu_text_triggers = ["профиль", "profile", "продажа", "sell", "покупка", "buy"]
    bot.router.message(text_message=menu_text_triggers)(wrap(handle_menu_text))
    bot.router.outgoing_message(text_message=menu_text_triggers)(wrap(handle_menu_text))

    bot.router.message()(wrap(handle_fallback))
    bot.router.outgoing_message()(wrap(handle_fallback))

    return bot
