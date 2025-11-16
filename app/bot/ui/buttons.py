from __future__ import annotations

MAIN_MENU_BUTTONS = [
    {"buttonId": "profile", "buttonText": "Профиль"},
    {"buttonId": "sell", "buttonText": "Продажа"},
    {"buttonId": "buy", "buttonText": "Покупка"},
]

SELL_MENU_BUTTONS = [
    {"buttonId": "sell_create", "buttonText": "Разместить объявление"},
    {"buttonId": "sell_list", "buttonText": "Мои объявления"},
]

TEXT_TO_BUTTON = {
    "профиль": "profile",
    "profile": "profile",
    "продажа": "sell",
    "sell": "sell",
    "покупка": "buy",
    "buy": "buy",
}

SELL_TEXT_TO_BUTTON = {
    "разместить объявление": "sell_create",
    "мои объявления": "sell_list",
    "sell_create": "sell_create",
    "sell_list": "sell_list",
}
