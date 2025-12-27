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
                "model": getattr(ad, "model_name", None),
                "region": getattr(ad, "region", None),
                "condition": getattr(ad, "condition", None),
                "status": "активно" if ad.is_active else "в обработке",
                "photo": imgs[0].image_url if imgs else None,
                "sender": ad.sender,
            }
        )
    return summary


async def _filter_public_ads(filters: dict, page: int = 0, page_size: int = 5):
    """Получить срез отфильтрованных активных объявлений с пагинацией."""
    offset = page * page_size
    ads = await crud_manager.ad.filter_ads(
        car_brand_id=filters.get("car_brand_id"),
        min_price=filters.get("min_price"),
        max_price=filters.get("max_price"),
        year_car=filters.get("year"),
        min_year_car=filters.get("min_year"),
        max_year_car=filters.get("max_year"),
        min_mileage=filters.get("min_mileage"),
        max_mileage=filters.get("max_mileage"),
        region=filters.get("region"),
        condition=filters.get("condition"),
        sort_by=filters.get("sort_by"),
        sort_order=filters.get("sort_order") or "desc",
        is_active=True,
        limit=page_size,
        offset=offset,
    )
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
                "model": getattr(ad, "model_name", None),
                "region": getattr(ad, "region", None),
                "condition": getattr(ad, "condition", None),
                "status": "активно" if ad.is_active else "в обработке",
                "photo": imgs[0].image_url if imgs else None,
                "sender": ad.sender,
            }
        )
    return summary


async def _count_filtered_public_ads(filters: dict) -> int:
    """Подсчитать количество объявлений под фильтры."""
    return await crud_manager.ad.count_filtered_ads(
        car_brand_id=filters.get("car_brand_id"),
        min_price=filters.get("min_price"),
        max_price=filters.get("max_price"),
        year_car=filters.get("year"),
        min_year_car=filters.get("min_year"),
        max_year_car=filters.get("max_year"),
        min_mileage=filters.get("min_mileage"),
        max_mileage=filters.get("max_mileage"),
        region=filters.get("region"),
        condition=filters.get("condition"),
        is_active=True,
    )


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
        model_name=data.get("model"),
        mileage_km_car=data["mileage"],
        vin_number=data["vin"],
        region=data.get("region"),
        condition=data.get("condition"),
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


def filter_public_ads(filters: dict, page: int = 0, page_size: int = 5):
    """Отфильтрованные объявления (публично) с пагинацией."""
    return db_runner.run(_filter_public_ads(filters, page, page_size))


def count_filtered_public_ads(filters: dict) -> int:
    """Сколько объявлений подходит под фильтр."""
    return db_runner.run(_count_filtered_public_ads(filters))


async def _count_public_ads() -> int:
    """Вернуть число активных объявлений (публичная витрина)."""
    return await crud_manager.ad.count_active()


async def _get_public_ad(ad_id: int):
    """Получить одно активное объявление по ID (без фильтра по sender)."""
    ad = await crud_manager.ad.get_active_by_id(ad_id)
    if not ad:
        return None
    return {
        "id": ad.id,
        "title": ad.title,
        "price": ad.price,
        "year": ad.year_car,
        "mileage": ad.mileage_km_car,
        "brand_id": ad.car_brand_id,
        "model": getattr(ad, "model_name", None),
        "region": getattr(ad, "region", None),
        "condition": getattr(ad, "condition", None),
        "status": "активно" if ad.is_active else "в обработке",
        "sender": ad.sender,
    }


async def _search_public_ads(query: str, limit: int = 5):
    """Поиск активных объявлений по заголовку (ILIKE %query%)."""
    ads = await crud_manager.ad.search_by_title(query, limit)
    summary: list[dict] = []
    for ad in ads:
        summary.append(
            {
                "id": ad.id,
                "title": ad.title,
                "price": ad.price,
                "year": ad.year_car,
                "mileage": ad.mileage_km_car,
                "brand_id": ad.car_brand_id,
                "model": getattr(ad, "model_name", None),
                "region": getattr(ad, "region", None),
                "condition": getattr(ad, "condition", None),
                "status": "активно" if ad.is_active else "в обработке",
                "sender": ad.sender,
            }
        )
    return summary


def count_public_ads() -> int:
    """Число активных объявлений."""
    return db_runner.run(_count_public_ads())


def get_public_ad(ad_id: int):
    """Одно объявление по ID (если активно)."""
    return db_runner.run(_get_public_ad(ad_id))


async def _get_public_ad_with_images(ad_id: int):
    """Активное объявление и список его изображений (публичный доступ)."""
    ad = await crud_manager.ad.get_active_by_id(ad_id)
    if not ad:
        return None, []
    images = await crud_manager.car_image.get_all_by_ad_id(ad_id)
    return ad, images


def get_public_ad_with_images(ad_id: int):
    """Синхронный фасад: активное объявление и картинки."""
    return db_runner.run(_get_public_ad_with_images(ad_id))


def search_public_ads(query: str, limit: int = 5):
    """Поиск активных объявлений по названию (ILIKE)."""
    return db_runner.run(_search_public_ads(query, limit))


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


async def _get_ads_by_ids(ids: list[int], active_only: bool = True):
    """Асинхронно получить объявления по списку ID."""
    return await crud_manager.ad.get_by_ids(ids, is_active=active_only)


async def _add_favorite(sender: str, ad_id: int):
    """Добавить объявление в избранное."""
    return await crud_manager.favorite.add(sender=sender, ad_id=ad_id)


async def _remove_favorite(sender: str, ad_id: int):
    """Удалить объявление из избранного."""
    return await crud_manager.favorite.delete(sender=sender, ad_id=ad_id)


async def _get_favorites(sender: str):
    """Получить избранные объявления пользователя (активные)."""
    favs = await crud_manager.favorite.get_by_sender(sender)
    ids = [fav.ad_id for fav in favs]
    return await _get_ads_by_ids(ids, active_only=True)


def get_brand_by_name(name: str):
    """Синхронно получить бренд по имени."""
    return db_runner.run(_get_brand_by_name(name))


def add_favorite(sender: str, ad_id: int):
    """Синхронно добавить объявление в избранное."""
    return db_runner.run(_add_favorite(sender, ad_id))


def remove_favorite(sender: str, ad_id: int):
    """Синхронно удалить объявление из избранного."""
    return db_runner.run(_remove_favorite(sender, ad_id))


def get_favorites(sender: str):
    """Синхронно получить активные объявления из избранного отправителя."""
    return db_runner.run(_get_favorites(sender))
