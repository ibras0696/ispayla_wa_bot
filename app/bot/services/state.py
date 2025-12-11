from __future__ import annotations

import asyncio
import threading
from typing import Awaitable

from ...database.crude import crud_manager
from ...database.db import init_db


class DBRunner:
    """Выполняет async-корутины в отдельном event loop.

    SQLAlchemy async engine не любит постоянное создание/закрытие event loop,
    поэтому этот helper живёт в отдельном потоке и принимает задачи через
    `run`, возвращая результат синхронно.
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
    """Создать таблицы и подготовить event loop при старте приложения."""
    db_runner.run(init_db())


async def _ensure_user(sender: str, username: str | None) -> None:
    """Асинхронно создать пользователя, если он ещё не существует."""
    await crud_manager.user.add(sender=sender, username=username)


async def _get_balance(sender: str) -> int:
    """Асинхронно получить баланс пользователя."""
    user = await crud_manager.user.get_by_sender(sender)
    return user.balance if user else 0


async def _get_user(sender: str):
    """Асинхронно вернуть объект пользователя или None."""
    return await crud_manager.user.get_by_sender(sender)


async def _get_ads_preview(sender: str, limit: int = 5):
    """Получить статистику по объявлениям конкретного пользователя."""
    ads = await crud_manager.ad.get_by_sender(sender)
    total = len(ads)
    active = sum(1 for ad in ads if getattr(ad, "is_active", False))
    ads_sorted = sorted(ads, key=lambda ad: getattr(ad, "created_at", None) or 0, reverse=True)
    subset = ads_sorted[:limit]
    images_map = await crud_manager.car_image.get_map_by_ad_ids([ad.id for ad in subset])
    summary = []
    for ad in subset:
        imgs = images_map.get(ad.id) or []
        summary.append({
            "id": ad.id,
            "title": getattr(ad, "title", None) or f"Объявление #{ad.id}",
            "price": getattr(ad, "price", 0),
            "status": "активно" if getattr(ad, "is_active", False) else "в обработке",
            "photo": imgs[0].image_url if imgs else None,
            "ad": ad,
        })
    return total, active, summary


async def _get_recent_public_ads(limit: int = 5):
    """Получить несколько последних активных объявлений для витрины."""
    ads = await crud_manager.ad.get_recent_active(limit)
    ad_ids = [ad.id for ad in ads]
    images_map = await crud_manager.car_image.get_map_by_ad_ids(ad_ids)
    summary: list[dict] = []
    for ad in ads:
        imgs = images_map.get(ad.id) or []
        summary.append(
            {
                "id": ad.id,
                "title": ad.title,
                "price": ad.price,
                "year": ad.year_car,
                "mileage": ad.mileage_km_car,
                "brand_id": ad.car_brand_id,
                "status": "активно" if ad.is_active else "в обработке",
                "photo": imgs[0].image_url if imgs else None,
                "sender": ad.sender,
            }
        )
    return summary


async def _get_brand_by_name(name: str):
    """Найти марку авто по названию."""
    return await crud_manager.car_brand.get_by_name(name)


async def _ensure_brand(name: str):
    """Создать марку авто, если она ещё не сохранена."""
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
    """Создать объявление и сохранить фотографии из формы."""
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
    """Получить статистику и срез последних объявлений."""
    return db_runner.run(_get_ads_preview(sender, limit))


def get_recent_public_ads(limit: int = 5):
    """Вернуть последние активные объявления без привязки к пользователю."""
    return db_runner.run(_get_recent_public_ads(limit))


async def _get_ad_with_images(sender: str, ad_id: int):
    """Получить объявление и его фотографии, если sender совпадает."""
    ad = await crud_manager.ad.get_by_id(ad_id)
    if not ad or ad.sender != sender:
        return None, []
    images = await crud_manager.car_image.get_all_by_ad_id(ad_id)
    return ad, images


def get_ad_with_images(sender: str, ad_id: int):
    """Вернуть объявление и список его изображений."""
    return db_runner.run(_get_ad_with_images(sender, ad_id))


def create_ad_from_form(sender: str, data: dict):
    """Создать объявление на основе заполненной формы."""
    return db_runner.run(_create_ad_from_form(sender, data))
