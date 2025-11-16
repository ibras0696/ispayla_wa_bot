from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import delete

from ..models import Ad, AdImage

from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Изображений Объявлений
class CrudeAdImage:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Добавление изображения к объявлению
    async def add(self, ad_id: int, image_url: str) -> AdImage:
        """
        Добавить изображение к объявлению.
        :param ad_id: ID объявления
        :param image_url: URL изображения
        :return: Объект AdImage
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли объявление с таким ID
                stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                existing_ad = stmt.scalar_one_or_none()
                if not existing_ad:
                    raise ValueError("Объявление не найдено.")

                # Вставка через INSERT ... RETURNING чтобы избежать refresh()
                stmt = pg_insert(AdImage).values(ad_id=ad_id, image_url=image_url).returning(AdImage)
                res = await session.execute(stmt)
                await session.commit()
                ad_image = res.scalar_one()
                return ad_image

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Получение всех изображений объявления
    async def get_all_by_ad_id(self, ad_id: int) -> list[AdImage]:
        """
        Получить все изображения объявления по ID.
        :param ad_id: ID объявления
        :return: Список объектов AdImage
        """
        async with self.session() as session:
            result = await session.execute(select(AdImage).where(AdImage.ad_id == ad_id))
            return result.scalars().all()

    async def get_map_by_ad_ids(self, ad_ids: list[int]) -> dict[int, list[AdImage]]:
        """Вернуть словарь {ad_id: [AdImage,...]} для указанного списка."""
        if not ad_ids:
            return {}
        async with self.session() as session:
            result = await session.execute(select(AdImage).where(AdImage.ad_id.in_(ad_ids)))
            images = result.scalars().all()
        mapping: dict[int, list[AdImage]] = {}
        for img in images:
            mapping.setdefault(img.ad_id, []).append(img)
        return mapping

    # Удаление изображения объявления
    async def delete(self, image_id: int) -> bool | None:
        """
        Удалить изображение объявления по ID.
        :param image_id: ID изображения
        :return: True Если удаление успешно, иначе False, None если изображение не найдено
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли изображение с таким ID
                stmt = await session.execute(select(AdImage).where(AdImage.id == image_id))
                existing_image = stmt.scalar_one_or_none()
                if not existing_image:
                    return None  # Изображение не найдено

                # Удаляем изображение
                await session.execute(delete(AdImage).where(AdImage.id == image_id))
                await session.commit()
                return True  # Успешное удаление

            except Exception as e:
                await session.rollback()
                raise e
