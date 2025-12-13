from __future__ import annotations

MAIN_MENU_BUTTONS = [
    {"buttonId": "profile", "buttonText": "Профиль"},
    {"buttonId": "sell", "buttonText": "Продажа"},
    {"buttonId": "buy", "buttonText": "Покупка"},
]

BUY_MENU_BUTTONS = [
    {"buttonId": "buy_all", "buttonText": "Все объявления"},
    {"buttonId": "buy_filter", "buttonText": "Фильтры"},
    {"buttonId": "buy_search", "buttonText": "Поиск авто"},
    {"buttonId": "buy_favorites", "buttonText": "Избранное"},
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

BUY_TEXT_TO_BUTTON = {
    "все объявления": "buy_all",
    "фильтры": "buy_filter",
    "поиск авто": "buy_search",
    "избранное": "buy_favorites",
    "buy_all": "buy_all",
    "buy_filter": "buy_filter",
    "buy_search": "buy_search",
    "buy_favorites": "buy_favorites",
}
