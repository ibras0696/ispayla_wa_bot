from __future__ import annotations

"""
Одноразовый скрипт для добавления новых колонок в таблицу ads:
- model_name (модель)
- region (регион)
- condition (состояние)

Запуск:
    python scripts/add_ads_columns.py

Скрипт использует те же переменные окружения, что и приложение (POSTGRES_* или DATABASE_URL).
"""

from sqlalchemy import create_engine, text

from app.database.db import _build_database_url


DDL_STATEMENTS = [
    "ALTER TABLE ads ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);",
    "ALTER TABLE ads ADD COLUMN IF NOT EXISTS region VARCHAR(100);",
    "ALTER TABLE ads ADD COLUMN IF NOT EXISTS condition VARCHAR(50);",
]


def _sync_url(async_url: str) -> str:
    """Преобразовать asyncpg URL в sync для create_engine."""
    return async_url.replace("+asyncpg", "")


def main() -> None:
    url = _sync_url(_build_database_url())
    engine = create_engine(url)
    with engine.begin() as conn:
        for ddl in DDL_STATEMENTS:
            conn.execute(text(ddl))
    print("Миграция завершена: колонки model_name, region, condition добавлены (если их не было).")


if __name__ == "__main__":
    main()
