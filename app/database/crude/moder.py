from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, func

from ..models import Ad, Moderation, Moderator
from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Модерации
class CrudeModeration:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Получение всех объявлений со статусом `pending`
    async def get_pending_ads(self) -> list[Ad]:
        """
        Получить все объявления со статусом `pending`.
        :return: Список объектов Ad
        """
        async with self.session() as session:
            result = await session.execute(select(Ad).where(Ad.moderation.has(status="pending")))
            return result.scalars().all()

    # Обновление статуса (`approved` / `rejected`)
    async def update_status(self, ad_id: int, status: str, comment: str | None = None) -> Moderation:
        """
        Обновить статус модерации объявления.
        :param ad_id: ID объявления
        :param status: Новый статус (approved / rejected)
        :param comment: Комментарий к статусу (необязательно)
        :return: Объект Moderation
        """
        async with self.session() as session:
            try:
                stmt = update(Moderation).where(Moderation.ad_id == ad_id).values(status=status, comment=comment).returning(Moderation)
                res = await session.execute(stmt)
                await session.commit()
                moderation = res.scalar_one_or_none()
                if not moderation:
                    raise ValueError("Модерация не найдена.")
                return moderation

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Привязка модератора к объявлению
    async def assign_moderator(self, ad_id: int, moderator_id: int) -> Moderation:
        """
        Привязать модератора к объявлению.
        :param ad_id: ID объявления
        :param moderator_id: ID модератора
        :return: Объект Moderation
        """
        async with self.session() as session:
            try:
                # Убедимся, что модератор существует
                mod_stmt = await session.execute(select(Moderator).where(Moderator.id == moderator_id))
                if not mod_stmt.scalar_one_or_none():
                    raise ValueError("Модератор не найден.")

                stmt = update(Moderation).where(Moderation.ad_id == ad_id).values(moderator_id=moderator_id).returning(Moderation)
                res = await session.execute(stmt)
                await session.commit()
                moderation = res.scalar_one_or_none()
                if not moderation:
                    raise ValueError("Модерация не найдена.")
                return moderation

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Получение истории модерации по модератору
    async def get_moderation_history(self, moderator_id: int) -> list[Moderation]:
        """
        Получить историю модерации по ID модератора.
        :param moderator_id: ID модератора
        :return: Список объектов Moderation
        """
        async with self.session() as session:
            result = await session.execute(
                select(Moderation).where(Moderation.moderator_id == moderator_id)
            )
            return result.scalars().all()

    # Комментарии к отклонённым объявлениям
    async def get_rejected_comments(self, ad_id: int) -> str | None:
        """
        Получить комментарий к отклонённому объявлению.
        :param ad_id: ID объявления
        :return: Комментарий к отклонению или None, если объявление не отклонено
        """
        async with self.session() as session:
            result = await session.execute(
                select(Moderation.comment).where(Moderation.ad_id == ad_id, Moderation.status == "rejected")
            )
            return result.scalar_one_or_none()


# CRUD Операции Таблицы Модераторов
class CrudeModerator:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Создание модератора
    async def add(self, telegram_id: int, username: str | None = None) -> Moderator:
        """
        Добавить нового модератора.
        :param telegram_id: ID модератора в Telegram
        :param username: Имя пользователя (необязательно)
        :return: Объект Moderator
        """
        async with self.session() as session:
            try:
                stmt = pg_insert(Moderator).values(telegram_id=telegram_id, username=username).on_conflict_do_nothing(index_elements=[Moderator.telegram_id]).returning(Moderator)
                res = await session.execute(stmt)
                await session.commit()
                moderator = res.scalar_one_or_none()
                if moderator:
                    return moderator

                # Если уже был — выберем существующего и кинем ошибку
                existing = await session.execute(select(Moderator).where(Moderator.telegram_id == telegram_id))
                if existing.scalar_one_or_none():
                    raise ValueError("Модератор с таким Telegram ID уже существует.")
                return existing.scalar_one_or_none()

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Получение всех активных модераторов
    async def get_all_active(self) -> list[Moderator]:
        """
        Получить всех активных модераторов.
        :return: Список объектов Moderator
        """
        async with self.session() as session:
            result = await session.execute(select(Moderator).where(Moderator.is_active.is_(True)))
            return result.scalars().all()

    # Деактивация модератора
    async def deactivate(self, moderator_id: int) -> Moderator:
        """
        Деактивировать модератора по ID.
        :param moderator_id: ID модератора
        :return: Объект Moderator
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли модератор с таким ID
                stmt = await session.execute(select(Moderator).where(Moderator.id == moderator_id))
                existing_moderator = stmt.scalar_one_or_none()
                if not existing_moderator:
                    raise ValueError("Модератор не найден.")

                # Деактивируем модератора
                await session.execute(update(Moderator).where(Moderator.id == moderator_id).values(is_active=False))
                await session.commit()
                return existing_moderator

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception as e:
                await session.rollback()
                raise e

    # Получение количества проверок
    async def get_moderation_count(self, moderator_id: int) -> int:
        """
        Получить количество проверок модератора по ID.
        :param moderator_id: ID модератора
        :return: Количество проверок
        """
        async with self.session() as session:
            result = await session.execute(
                select(func.count(Moderation.id)).where(Moderation.moderator_id == moderator_id)
            )
            return result.scalar_one_or_none() or 0
