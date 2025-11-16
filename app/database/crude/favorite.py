from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import delete

from ..models import User, Ad, Favorite
from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Избранных Объявлений
class CrudeFavorite:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Добавление объявления в избранное
    async def add(self, sender: str, ad_id: int) -> Favorite:
        """
        Добавить объявление в избранное.
        :param sender: Whatsapp sender ID пользователя
        :param ad_id: ID объявления
        :return: Объект Favorite
        """
        async with self.session() as session:
            try:
                # Проверка существования пользователя и объявления
                user_stmt = await session.execute(select(User).where(User.sender == sender))
                if not user_stmt.scalar_one_or_none():
                    raise ValueError("Пользователь не найден.")

                ad_stmt = await session.execute(select(Ad).where(Ad.id == ad_id))
                if not ad_stmt.scalar_one_or_none():
                    raise ValueError("Объявление не найдено.")

                # Попытка вставки: если уже есть — ничего не делаем
                stmt = pg_insert(Favorite).values(sender=sender, ad_id=ad_id)
                stmt = stmt.on_conflict_do_nothing(index_elements=[Favorite.sender, Favorite.ad_id]).returning(Favorite)
                res = await session.execute(stmt)
                await session.commit()
                fav = res.scalar_one_or_none()
                if fav:
                    return fav

                # Если вставка не вернула — значит уже есть запись
                existing = await session.execute(select(Favorite).where(Favorite.sender == sender, Favorite.ad_id == ad_id))
                return existing.scalar_one_or_none()

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Удаление объявления из избранного
    async def delete(self, sender: str, ad_id: int) -> bool | None:
        """
        Удалить объявление из избранного.
        :param sender: Whatsapp sender ID пользователя
        :param ad_id: ID объявления
        :return: True Если удаление успешно, иначе False, None если избранное не найдено
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли избранное с таким sender и ad_id
                stmt = await session.execute(
                    select(Favorite).where(Favorite.sender == sender, Favorite.ad_id == ad_id)
                )
                existing_favorite = stmt.scalar_one_or_none()
                if not existing_favorite:
                    return None  # Избранное не найдено

                # Удаляем избранное
                await session.execute(delete(Favorite).where(Favorite.sender == sender, Favorite.ad_id == ad_id))
                await session.commit()
                return True  # Успешное удаление

            except Exception as e:
                await session.rollback()
                raise e

    # Получение избранных объявлений пользователя
    async def get_by_sender(self, sender: str) -> list[Favorite]:
        """
        Получить избранные объявления пользователя по sender.
        :param sender: Whatsapp sender ID
        :return: Список объектов Favorite
        """
        async with self.session() as session:
            result = await session.execute(select(Favorite).where(Favorite.sender == sender))
            return result.scalars().all()
