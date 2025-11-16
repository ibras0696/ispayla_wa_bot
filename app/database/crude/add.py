from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, delete

from ..models import Ad, Moderation

from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Объявлений
class CrudeAdd:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Создание объявления
    async def add(self,
                  sender: str,  # Whatsapp sender ID владельца объявления
                  title: str,  # Название объявления
                  description: str,  # Описание объявления
                  price: int,  # Цена объявления
                  year_car: int,  # Год выпуска автомобиля
                  car_brand_id: int,  # ID марки автомобиля
                  mileage_km_car: int,  # Пробег в км
                  vin_number: str,  # Уникальный VIN-номер
                  day_count: int = 7,  # Количество дней публикации по умолчанию 7
                  is_active: bool = True  # Активно ли объявление
                  ) -> Ad:
        """
        Добавить объявление.
        :param sender: Whatsapp sender ID владельца объявления
        :param title: Название объявления
        :param description: Описание объявления
        :param price: Цена объявления
        :param year_car: Год выпуска автомобиля
        :param car_brand_id: ID марки автомобиля
        :param mileage_km_car: Пробег в км
        :param vin_number: Уникальный VIN-номер
        :param day_count: Количество дней публикации (по умолчанию 7)
        :param is_active: Активно ли объявление (по умолчанию False)
        :return: Объект объявления Ad
        """
        async with self.session() as session:
            try:
                # Вставка с ON CONFLICT по vin_number — безопасный upsert для race conditions.
                stmt = pg_insert(Ad).values(
                    sender=sender,
                    title=title,
                    description=description,
                    price=price,
                    year_car=year_car,
                    car_brand_id=car_brand_id,
                    mileage_km_car=mileage_km_car,
                    vin_number=vin_number,
                    day_count=day_count,
                    is_active=is_active,
                )
                # Если уже существует — не делать обновление (можно менять на DO UPDATE при необходимости)
                stmt = stmt.on_conflict_do_nothing(index_elements=[Ad.vin_number]).returning(Ad)
                res = await session.execute(stmt)
                await session.commit()
                ad = res.scalar_one_or_none()
                if not ad:
                    # Если вставка не произошла (уже есть), выбрасываем ошибку
                    raise ValueError("Объявление с таким VIN-номером уже существует.")
                return ad

            except ValueError:
                await session.rollback()
                raise

            except Exception:
                await session.rollback()
                raise

    # Обновления объявления
    async def update(self,
                     ad_id: int,  # ID объявления
                     title: str | None = None,  # Название объявления
                     description: str | None = None,  # Описание объявления
                     price: int | None = None,  # Цена объявления
                     year_car: int | None = None,  # Год выпуска автомобиля
                     car_brand_id: int | None = None,  # ID марки автомобиля
                     mileage_km_car: int | None = None,  # Пробег в км
                     vin_number: str | None = None,  # Уникальный VIN-номер
                     day_count: int | None = None,  # Количество дней публикации по умолчанию 7
                     is_active: bool | None = None  # Активно ли объявление
                     ) -> Ad:
        """
        Обновить объявление по ID.
        :param ad_id: ID объявления
        :param title: Заголовок объявления
        :param description: Описание объявления
        :param price: Цена автомобиля
        :param year_car: Год выпуска автомобиля
        :param car_brand_id: Бренд автомобиля
        :param mileage_km_car: Пробег автомобиля в км
        :param vin_number: Уникальный VIN-номер автомобиля
        :param day_count: Количество дней публикации объявления
        :param is_active: Статус активности объявления
        :return:
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли объявление с таким ID
                stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                existing_ad = stmt.scalar_one_or_none()
                if not existing_ad:
                    raise ValueError("Объявление не найдено.")
                # Проверяем есть ли VIN номер и если есть, то проверяем его уникальность
                if vin_number:
                    check_vin = await session.execute(select(Ad).where(Ad.vin_number == vin_number))
                    if check_vin.scalar_one_or_none():
                        raise ValueError("Объявление с таким VIN-номером уже существует.")

                # Обновляем поля объявления
                update_data = {
                    "title": title,
                    "description": description,
                    "price": price,
                    "year_car": year_car,
                    "car_brand_id": car_brand_id,
                    "mileage_km_car": mileage_km_car,
                    "vin_number": vin_number,
                    "day_count": day_count,
                    "is_active": is_active
                }
                # Удаляем None значения из словаря
                update_data = {k: v for k, v in update_data.items() if v is not None}

                await session.execute(update(Ad).where(Ad.id == ad_id).values(**update_data))
                await session.commit()
                return existing_ad

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception as e:
                await session.rollback()
                raise e

    # Удаление объявления
    async def delete(self, ad_id: int) -> bool | None:
        """
        Удалить объявление по ID.
        :param ad_id: ID объявления
        :return: True Если удаление успешно, иначе False, None если объявление не найдено
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли объявление с таким ID
                stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                existing_ad = stmt.scalar_one_or_none()
                if not existing_ad:
                    return None  # Объявление не найдено

                # Удаляем объявление
                await session.execute(delete(Ad).where(Ad.id == ad_id))
                await session.commit()
                return True  # Успешное удаление

            except Exception as e:
                await session.rollback()
                raise e

    # Получение всех активных объявлений
    async def get_all_active(self) -> list[Ad]:
        """
        Получить все активные объявления.
        :return: Список объектов Ad
        """
        async with self.session() as session:
            result = await session.execute(select(Ad).where(Ad.is_active.is_(True)))
            return result.scalars().all()

    # Получение объявления конкретного пользователя по sender
    async def get_by_sender(self, sender: str) -> list[Ad]:
        """
        Получить все объявления пользователя по sender.
        :param sender: Whatsapp sender ID
        :return: Список объектов Ad
        """
        async with self.session() as session:
            result = await session.execute(select(Ad).where(Ad.sender == sender))
            return result.scalars().all()

    # Фильтрация по: Марке, Цене, Году, Пробегу
    async def filter_ads(self,
                         car_brand_id: int | None = None,  # ID марки автомобиля
                         min_price: int | None = None,  # Минимальная цена
                         max_price: int | None = None,  # Максимальная цена
                         year_car: int | None = None,  # Год выпуска автомобиля
                         min_mileage: int | None = None,  # Минимальный пробег в км
                         max_mileage: int | None = None  # Максимальный пробег в км
                         ) -> list[Ad]:
        """
        Фильтрация объявлений по различным параметрам.
        :param car_brand_id: ID марки автомобиля (необязательно)
        :param min_price: Минимальная цена (необязательно)
        :param max_price: Максимальная цена (необязательно)
        :param year_car: Год выпуска автомобиля (необязательно)
        :param min_mileage: Минимальный пробег в км (необязательно)
        :param max_mileage: Максимальный пробег в км (необязательно)
        :return: Список отфильтрованных объектов Ad
        """
        async with self.session() as session:
            query = select(Ad)

            # Добавляем условия фильтрации
            if car_brand_id is not None:
                query = query.where(Ad.car_brand_id == car_brand_id)
            if min_price is not None:
                query = query.where(Ad.price >= min_price)
            if max_price is not None:
                query = query.where(Ad.price <= max_price)
            if year_car is not None:
                query = query.where(Ad.year_car == year_car)
            if min_mileage is not None:
                query = query.where(Ad.mileage_km_car >= min_mileage)
            if max_mileage is not None:
                query = query.where(Ad.mileage_km_car <= max_mileage)

            result = await session.execute(query)
            return result.scalars().all()

    # Получение объявления в модерации
    async def get_moderation(self, ad_id: int) -> Moderation | None:
        """
        Получить информацию о модерации объявления по ID.
        :param ad_id: ID объявления
        :return: Объект Moderation или None, если не найдено
        """
        async with self.session() as session:
            result = await session.execute(select(Moderation).where(Moderation.ad_id == ad_id))
            return result.scalar_one_or_none()

    # Поиск по VIN номеру
    async def get_by_vin(self, vin_number: str) -> Ad | None:
        """
        Получить объявление по VIN номеру.
        :param vin_number: Уникальный VIN-номер
        :return: Объект Ad или None, если не найдено
        """
        async with self.session() as session:
            result = await session.execute(select(Ad).where(Ad.vin_number == vin_number))
            return result.scalar_one_or_none()

    # Изменение статуса объявления
    async def change_status(self, ad_id: int, is_active: bool) -> Ad:
        """
        Изменить статус объявления (активно/неактивно).
        :param ad_id: ID объявления
        :param is_active: Новый статус объявления
        :return: Обновленный объект Ad
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли объявление с таким ID
                stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                existing_ad = stmt.scalar_one_or_none()
                if not existing_ad:
                    raise ValueError("Объявление не найдено.")

                # Обновляем статус объявления
                await session.execute(update(Ad).where(Ad.id == ad_id).values(is_active=is_active))
                await session.commit()
                return existing_ad

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception as e:
                await session.rollback()
                raise e

    # Продление времени публикации объявления
    async def extend_ad(self, ad_id: int, additional_days: int) -> Ad:
        """
        Продлить время публикации объявления.
        :param ad_id: ID объявления
        :param additional_days: Количество дополнительных дней для продления
        :return: Обновленный объект Ad
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли объявление с таким ID
                stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                existing_ad = stmt.scalar_one_or_none()
                if not existing_ad:
                    raise ValueError("Объявление не найдено.")

                # Продлеваем время публикации
                new_day_count = existing_ad.day_count + additional_days
                await session.execute(update(Ad).where(Ad.id == ad_id).values(day_count=new_day_count))
                await session.commit()
                return existing_ad

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception as e:
                await session.rollback()
                raise e
