from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.future import select

from ..models import User, Payment
from ..db import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert as pg_insert


# CRUD Операции Таблицы Платежей
class CrudePayment:

    # Инициализация класса сессии для работы с БД
    def __init__(self):
        self.session: async_sessionmaker = AsyncSessionLocal

    # Создание платежа
    async def add(self, sender: str, amount: int, description: str | None = None) -> Payment:
        """
        Добавить новый платеж.
        :param sender: Whatsapp sender ID пользователя
        :param amount: Сумма платежа
        :param description: Описание платежа (необязательно)
        :return: Объект Payment
        """
        async with self.session() as session:
            try:
                user_stmt = await session.execute(select(User).where(User.sender == sender))
                if not user_stmt.scalar_one_or_none():
                    raise ValueError("Пользователь не найден.")

                stmt = pg_insert(Payment).values(sender=sender, amount=amount, description=description).returning(Payment)
                res = await session.execute(stmt)
                await session.commit()
                return res.scalar_one()

            except ValueError as ve:
                await session.rollback()
                raise ve

            except Exception:
                await session.rollback()
                raise

    # Получение всех платежей пользователя
    async def get_by_sender(self, sender: str) -> list[Payment]:
        """
        Получить все платежи пользователя по sender.
        :param sender: Whatsapp sender ID
        :return: Список объектов Payment
        """
        async with self.session() as session:
            result = await session.execute(select(Payment).where(Payment.sender == sender))
            return result.scalars().all()

    # Аналитика платежей кто сколько потратил
    async def get_spending_summary(self) -> list[tuple[str, int]]:
        """
        Получить сводку по платежам: кто сколько потратил.
        :return: Список кортежей (sender, total_spent)
        """
        async with self.session() as session:
            result = await session.execute(
                select(Payment.sender, Payment.amount).group_by(Payment.sender)
            )
            return [(row.sender, row.amount) for row in result.fetchall()]

    # Аналитика Топ клиентов
    async def get_top_clients(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Получить топ клиентов по сумме платежей.
        :param limit: Количество топ клиентов (по умолчанию 10)
        :return: Список кортежей (sender, total_spent)
        """
        async with self.session() as session:
            result = await session.execute(
                select(Payment.sender, Payment.amount)  # Выбираем отправителя и сумму
                .group_by(Payment.sender)  # Группировка по отправителю
                .order_by(Payment.amount.desc())  # Сортировка по убыванию суммы
                .limit(limit)  # Ограничение по количеству клиентов
            )
            return [(row.sender, row.amount) for row in result.fetchall()]
