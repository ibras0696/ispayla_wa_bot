from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, delete

from ..models import User, Ad, Favorite
from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert

# CRUD Операции Таблицы Пользователей
class CrudeUser:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Создание пользователя
    async def add(self, sender: str, username: str | None = None, balance: int = 0) -> User:
        """
        Добавить нового пользователя в базу данных.
        :param sender: Whatsapp sender ID
        :param username: Имя пользователя (необязательно)
        :param balance: Баланс пользователя (по умолчанию 0)
        :return: Объект User
        """
        async with self.session() as session:
            try:
                # Попытка вставки с ON CONFLICT DO NOTHING и RETURNING
                stmt = pg_insert(User).values(sender=sender, username=username, balance=balance)
                stmt = stmt.on_conflict_do_nothing(index_elements=[User.sender]).returning(User)
                res = await session.execute(stmt)
                await session.commit()
                user = res.scalar_one_or_none()
                if user:
                    return user

                # Если запись уже существовала, выбираем её
                existing = await session.execute(select(User).where(User.sender == sender))
                return existing.scalar_one_or_none()

            except Exception:
                await session.rollback()
                raise

    # Поиск пользователя по sender
    async def get_by_sender(self, sender: str) -> User | None:
        """
        Получить пользователя по sender.
        :param sender: Whatsapp sender ID
        :return: Объект User или None, если пользователь не найден
        """
        async with self.session() as session:
            result = await session.execute(select(User).where(User.sender == sender))
            return result.scalar_one_or_none()

    # Обновление баланса + | -
    async def update_balance(self, sender: str, amount: int, operation: bool) -> None:
        """
        Обновить баланс пользователя.
        :param sender: Whatsapp sender ID
        :param amount: Сумма для добавления или вычитания из баланса
        :param operation: True для увеличения баланса, False для уменьшения
        :return: None
        """
        async with self.session() as session:
            try:
                stmt = None
                # Если Увелечения баланса
                if operation:
                    stmt = update(User).where(User.sender == sender).values(balance=User.balance + amount)
                # Иначе Уменьшение баланса
                else:
                    stmt = update(User).where(User.sender == sender).values(balance=User.balance - amount)

                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    # Получение всех объявлений пользователя
    async def get_all_ads(self, sender: str) -> list[Ad]:
        """
        Получить все объявления пользователя.
        :param sender: Whatsapp sender ID
        :return: Список объектов Ad
        """
        async with self.session() as session:
            result = await session.execute(select(Ad).where(Ad.sender == sender))
            return result.scalars().all()

    # Получение избранного пользователя
    async def get_favorites(self, sender: str) -> list[Favorite]:
        """
        Получить избранные объявления пользователя.
        :param sender: Whatsapp sender ID
        :return: Список объектов Favorite
        """
        async with self.session() as session:
            result = await session.execute(select(Favorite).where(Favorite.sender == sender))
            return result.scalars().all()

    # Удаление пользователя (редко используется)
    async def delete(self, sender: str) -> bool | None:
        """
        Удалить пользователя по sender.
        :param sender: Whatsapp sender ID
        :return: True Если удаление иначе False, None если пользователь не найден
        """
        async with self.session() as session:
            try:
                # Проверяем, существует ли пользователь с таким sender
                stmt = await session.execute(select(User).where(User.sender == sender))
                result = stmt.scalar_one_or_none()
                if not result:
                    return None  # Пользователь не найден

                # Удаляем пользователя
                await session.execute(delete(User).where(User.sender == sender))
                await session.commit()
                return True  # Успешное удаление

            except Exception as e:
                await session.rollback()
                raise e
