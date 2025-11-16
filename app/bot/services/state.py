from __future__ import annotations

import asyncio
import threading
from typing import Awaitable

from ...database.crude import crud_manager
from ...database.db import init_db


class DBRunner:
    """
    Helper для выполнения корутин в выделенном event loop.

    SQLAlchemy async engine не любит, когда event loop постоянно создаётся/закрывается,
    поэтому держим отдельный поток и гоняем все операции через него.
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
    """Создать таблицы при старте приложения (алембик пока не подключен)."""
    db_runner.run(init_db())


async def _ensure_user(sender: str, username: str | None) -> None:
    await crud_manager.user.add(sender=sender, username=username)


async def _get_balance(sender: str) -> int:
    user = await crud_manager.user.get_by_sender(sender)
    return user.balance if user else 0


async def _get_user(sender: str):
    return await crud_manager.user.get_by_sender(sender)


def ensure_user(sender: str, username: str | None) -> None:
    """Синхронный фасад для добавления пользователя."""
    db_runner.run(_ensure_user(sender, username))


def get_balance(sender: str) -> int:
    """Синхронно вернуть баланс пользователя."""
    return db_runner.run(_get_balance(sender))


def get_user(sender: str):
    """Вернуть ORM-модель пользователя (или None)."""
    return db_runner.run(_get_user(sender))
