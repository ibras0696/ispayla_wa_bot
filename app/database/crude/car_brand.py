from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, delete, func

from ..models import CarBrand
from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Объявлений
class CrudeCarBrand:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Получение всех марок автомобилей
    async def get_all(self) -> list[CarBrand]:
        """
        Получить все марки автомобилей.
        :return: Список объектов CarBrand
        """
        async with self.session() as session:
            result = await session.execute(select(CarBrand))
            return result.scalars().all()

    # Создание новой марки автомобиля (через админку)
    async def add(self, name: str) -> CarBrand:
        """
        Добавить новую марку автомобиля.
        :param name: Название марки
        :return: Объект CarBrand
        """
        async with self.session() as session:
            try:
                stmt = pg_insert(CarBrand).values(name=name).on_conflict_do_nothing(index_elements=[CarBrand.name]).returning(CarBrand)
                res = await session.execute(stmt)
                await session.commit()
                brand = res.scalar_one_or_none()
                if brand:
                    return brand

                # Если уже существует — выбрасываем ошибку (поведение прежнее)
                existing = await session.execute(select(CarBrand).where(CarBrand.name == name))
                if existing.scalar_one_or_none():
                    raise ValueError("Марка с таким названием уже существует.")
                # На всякий случай: если нет — выберем и вернём
                return existing.scalar_one_or_none()

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Удаление марки автомобиля
    async def delete(self, brand_id: int) -> bool | None:
        """
        Удалить марку автомобиля по ID.
        :param brand_id: ID марки
        :return: True Если удаление успешно, иначе False, None если марка не найдена
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли марка с таким ID
                stmt = await session.execute(select(CarBrand).where(CarBrand.id == brand_id))
                existing_brand = stmt.scalar_one_or_none()
                if not existing_brand:
                    return None  # Марка не найдена

                # Удаляем марку
                await session.execute(delete(CarBrand).where(CarBrand.id == brand_id))
                await session.commit()
                return True  # Успешное удаление

            except Exception as e:
                await session.rollback()
                raise e

    # Редактирование марки автомобиля
    async def update(self, brand_id: int, name: str) -> CarBrand:
        """
        Обновить марку автомобиля по ID.
        :param brand_id: ID марки
        :param name: Новое название марки
        :return: Обновленный объект CarBrand
        """
        async with self.session() as session:
            try:
                # Проверяем уникальность нового названия — если совпадает с другим id, ошибаемся
                check_name = await session.execute(select(CarBrand).where(CarBrand.name == name, CarBrand.id != brand_id))
                if check_name.scalar_one_or_none():
                    raise ValueError("Марка с таким названием уже существует.")

                stmt = update(CarBrand).where(CarBrand.id == brand_id).values(name=name).returning(CarBrand)
                res = await session.execute(stmt)
                await session.commit()
                updated = res.scalar_one_or_none()
                if not updated:
                    raise ValueError("Марка не найдена.")
                return updated

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    async def get_by_name(self, name: str) -> CarBrand | None:
        async with self.session() as session:
            result = await session.execute(
                select(CarBrand).where(func.lower(CarBrand.name) == func.lower(name))
            )
            return result.scalar_one_or_none()
