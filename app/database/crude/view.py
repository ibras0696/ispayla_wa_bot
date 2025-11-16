from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func

from ..models import Ad, ViewLog
from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Просмотров Объявлений
class CrudeViewLog:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Добавление записи о просмотре
    async def add(self, ad_id: int, sender: str) -> ViewLog:
        """
        Добавить запись о просмотре объявления.
        :param ad_id: ID объявления
        :param sender: Whatsapp sender ID пользователя
        :return: Объект ViewLog
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли объявление с таким ID
                stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                if not stmt.scalar_one_or_none():
                    raise ValueError("Объявление не найдено.")

                ins = pg_insert(ViewLog).values(ad_id=ad_id, sender=sender).returning(ViewLog)
                res = await session.execute(ins)
                await session.commit()
                return res.scalar_one()

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Получение количества просмотров объявления
    async def get_view_count(self, ad_id: int) -> int:
        """
        Получить количество просмотров объявления по ID.
        :param ad_id: ID объявления
        :return: Количество просмотров
        """
        async with self.session() as session:
            result = await session.execute(
                select(func.count(ViewLog.id)).where(ViewLog.ad_id == ad_id)
            )
            return result.scalar_one_or_none() or 0

    # Получение всех просмотров пользователя
    async def get_by_sender(self, sender: str) -> list[ViewLog]:
        """
        Получить все просмотры пользователя по sender.
        :param sender: Whatsapp sender ID
        :return: Список объектов ViewLog
        """
        async with self.session() as session:
            result = await session.execute(select(ViewLog).where(ViewLog.sender == sender))
            return result.scalars().all()

    # Аналитика: кто что смотрит
    async def get_view_analytics(self) -> list[tuple[str, int]]:
        """
        Получить аналитику просмотров: кто что смотрит.
        :return: Список кортежей (sender, ad_id, view_count)
        """
        async with self.session() as session:
            result = await session.execute(
                select(ViewLog.sender, ViewLog.ad_id, func.count(ViewLog.id).label("view_count"))
                .group_by(ViewLog.sender, ViewLog.ad_id)
            )
            return [(row.sender, int(row.ad_id), int(row.view_count)) for row in result.fetchall()]

    # Аналитика: что самое популярное
    async def get_popular_ads(self, limit: int = 10) -> list[tuple[int, int]]:
        """
        Получить топ популярных объявлений по количеству просмотров.
        :param limit: Количество топ объявлений (по умолчанию 10)
        :return: Список кортежей (ad_id, view_count)
        """
        async with self.session() as session:
            result = await session.execute(
                select(ViewLog.ad_id, func.count(ViewLog.id).label("view_count"))
                .group_by(ViewLog.ad_id)
                .order_by(func.count(ViewLog.id).desc())
                .limit(limit)
            )
            return [(int(row.ad_id), int(row.view_count)) for row in result.fetchall()]

    # Фильтрация по дате
    async def filter_by_date(self, start_date: datetime, end_date: datetime) -> list[ViewLog]:
        """
        Получить просмотры в заданном диапазоне дат.
        :param start_date: Начальная дата
        :param end_date: Конечная дата
        :return: Список объектов ViewLog
        """
        async with self.session() as session:
            result = await session.execute(
                select(ViewLog).where(ViewLog.viewed_at.between(start_date, end_date))
            )
            return result.scalars().all()
