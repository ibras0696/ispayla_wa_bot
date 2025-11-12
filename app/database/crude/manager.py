from __future__ import annotations
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import AsyncIterator

from ..db import AsyncSessionLocal

# Импорт CRUD-классов локально, чтобы не создавать циклических импортов
from .user import CrudeUser
from .add import CrudeAdd
from .favorite import CrudeFavorite
from .car_image import CrudeAdImage
from .car_brand import CrudeCarBrand
from .view import CrudeViewLog
from .moder import CrudeModeration, CrudeModerator
from .payment import CrudePayment


def _bind_session_to_crud(crud_instance, bound_session):
    """Возвращает тот же объект crud_instance, но с session, привязанной к конкретной AsyncSession.

    Мы не создаём новую длительную сессию — просто заменяем атрибут `session` на asynccontextmanager,
    который при `async with crud.session()` вернёт уже существующую сессию (не закроет её).
    Это позволяет выполнять методы CRUD в рамках внешней сессии без изменения их реализации.
    """

    @asynccontextmanager
    async def _cm():
        yield bound_session

    # Патчим атрибут .session экземпляра (обычно это sessionmaker)
    setattr(crud_instance, "session", _cm)
    return crud_instance


class CrudManager:
    """Менеджер CRUD-ов.

    Примеры использования:

    # простой доступ к CRUD-инстансам (они используют глобальный AsyncSessionLocal)
    mgr = CrudManager()
    await mgr.user.add(...)

    # объединённая транзакция с одной сессией
    async with mgr.session() as session:
        bound_user = mgr.bind(mgr.user, session)
        bound_fav = mgr.bind(mgr.favorite, session)
        await bound_user.update_balance(sender, 100)
        await bound_fav.add(sender, ad_id)
        await session.commit()

    """

    def __init__(self, session_factory: object | None = None):
        # session_factory должен быть async_sessionmaker (обычно AsyncSessionLocal)
        self.session_factory = session_factory or AsyncSessionLocal

        # делаем экземпляры CRUD с дефолтной фабрикой
        self.user = CrudeUser()
        self.ad = CrudeAdd()
        self.favorite = CrudeFavorite()
        self.car_image = CrudeAdImage()
        self.car_brand = CrudeCarBrand()
        self.view = CrudeViewLog()
        self.moderation = CrudeModeration()
        self.moderator = CrudeModerator()
        self.payment = CrudePayment()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        """Контекстно-менеджер для сессии: async with manager.session() as session: ..."""
        async with self.session_factory() as session:
            yield session

    def bind(self, crud_instance, bound_session):
        """Привязать конкретный объект CRUD к существующей session и вернуть его.

        Небольшой хак: мы заменяем атрибут `session` на asynccontextmanager, который будет yield-ить
        переданную сессию. CRUD-методы, которые делают `async with self.session() as session` будут
        использовать эту сессию.
        """
        return _bind_session_to_crud(crud_instance, bound_session)

    def bind_all(self, bound_session) -> SimpleNamespace:
        """Вернуть набор всех CRUD-ов, привязанных к одной сессии."""
        return SimpleNamespace(
            user=self.bind(self.user, bound_session),
            ad=self.bind(self.ad, bound_session),
            favorite=self.bind(self.favorite, bound_session),
            car_image=self.bind(self.car_image, bound_session),
            car_brand=self.bind(self.car_brand, bound_session),
            view=self.bind(self.view, bound_session),
            moderation=self.bind(self.moderation, bound_session),
            moderator=self.bind(self.moderator, bound_session),
            payment=self.bind(self.payment, bound_session),
        )
