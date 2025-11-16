from __future__ import annotations

import asyncio
import threading
from typing import Awaitable

from ...database.crude import crud_manager
from ...database.db import init_db


class DBRunner:
    """
    Helper для выполнения корутин в выделенном event loop.

    SQLAlchemy async engine не любит, когда event loop постоянно создаётся/закрывается,
    поэтому держим отдельный поток и гоняем все операции через него.
    """

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro: Awaitable):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()


db_runner = DBRunner()


def init_background_loop() -> None:
    """Создать таблицы при старте приложения (алембик пока не подключен)."""
    db_runner.run(init_db())


async def _ensure_user(sender: str, username: str | None) -> None:
    await crud_manager.user.add(sender=sender, username=username)


async def _get_balance(sender: str) -> int:
    user = await crud_manager.user.get_by_sender(sender)
    return user.balance if user else 0


async def _get_user(sender: str):
    return await crud_manager.user.get_by_sender(sender)


async def _get_ads_preview(sender: str, limit: int = 5):
    ads = await crud_manager.ad.get_by_sender(sender)
    total = len(ads)
    active = sum(1 for ad in ads if getattr(ad, "is_active", False))
    return total, active, ads[:limit]


async def _get_brand_by_name(name: str):
    return await crud_manager.car_brand.get_by_name(name)


async def _ensure_brand(name: str):
    brand = await _get_brand_by_name(name)
    if brand:
        return brand
    try:
        return await crud_manager.car_brand.add(name=name)
    except ValueError:
        brand = await _get_brand_by_name(name)
        if brand:
            return brand
        raise


async def _create_ad_from_form(sender: str, data: dict):
    brand = await _ensure_brand(data["brand"])
    ad = await crud_manager.ad.add(
        sender=sender,
        title=data["title"],
        description=data["description"],
        price=data["price"],
        year_car=data["year"],
        car_brand_id=brand.id,
        mileage_km_car=data["mileage"],
        vin_number=data["vin"],
        day_count=7,
        is_active=True,
    )
    photos: list[str] = data.get("photos", [])
    for url in photos:
        await crud_manager.car_image.add(ad.id, url)
    return ad


def ensure_user(sender: str, username: str | None) -> None:
    """Синхронный фасад для добавления пользователя."""
    db_runner.run(_ensure_user(sender, username))


def get_balance(sender: str) -> int:
    """Синхронно вернуть баланс пользователя."""
    return db_runner.run(_get_balance(sender))


def get_user(sender: str):
    """Вернуть ORM-модель пользователя (или None)."""
    return db_runner.run(_get_user(sender))


def get_ads_preview(sender: str, limit: int = 5):
    """Получить количество объявлений и срез последних записей."""
    return db_runner.run(_get_ads_preview(sender, limit))


def create_ad_from_form(sender: str, data: dict):
    """Создать объявление на основе заполненной формы."""
    return db_runner.run(_create_ad_from_form(sender, data))
