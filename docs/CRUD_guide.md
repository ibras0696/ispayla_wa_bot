# Руководство по работе с `database` и CRUD-ами

Документация описывает структуру моделей, доступные CRUD-классы (в `database/crude`), рекомендации по использованию,
а также примеры оптимизированных запросов: eager-loading (selectinload/joinedload), использование `RETURNING`/`returning()`
и приёмы для уменьшения количества запросов и повышения производительности.

## Структура и короткая справка по моделям

- `User` (users): ключ `sender` (Whatsapp ID). Связи: `ads`, `views`, `favorites`.
- `Ad` (ads): объявления; связи: `owner`, `brand`, `images`, `moderation`, `views`, `favorites`.
- `CarBrand` (car_brands)
- `AdImage` (ad_images)
- `Favorite` (favorites)
- `Payment` (payments)
- `Moderator` / `Moderation` (moderators, moderations)
- `ViewLog` (view_logs)

Индексы: многие поля уже индексированы (`ads.id`, `ads.vin_number`, `ads.car_brand_id`, `users.sender`). При необходимости добавьте составные индексы
для часто используемых сочетаний фильтров (например `(car_brand_id, price)` для быстрых выборок по бренду и цене).

## Список CRUD-классов

- `CrudeUser` — создаёт / получает / обновляет баланс / удаляет.
- `CrudeAdd` — работа с объявлениями: add, update, delete, фильтрация, продление, смена статуса.
- `CrudeFavorite` — добавление/удаление избранного, получение избранных.
- `CrudeViewLog` — запись просмотров, аналитика и топы.
- (и другие: `payment.py`, `car_brand.py`, `car_image.py`, `moder.py`, `view.py`)

Каждый CRUD использует `AsyncSessionLocal` из `database/db.py` и `async with session()` паттерн.

## Общие рекомендации по оптимизации

1. Eager loading (selectinload / joinedload)
   - Если вы грузите объявления и затем обращаетесь к связанным сущностям (images, brand, owner), используйте `select().options(selectinload(Ad.images), selectinload(Ad.brand))`.
   - Это устраняет N+1 проблему и значительно уменьшает количество запросов.

2. Используйте `.returning()` для получения вставленной/обновлённой строки без отдельного `refresh()`.
   - Пример: `await session.execute(insert(Ad).values(...).returning(Ad))`.

3. Upsert / ON CONFLICT
   - Для операций "создать если нет" используйте PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` или `ON CONFLICT (...) DO UPDATE` через `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing()`.
   - Это безопаснее и быстрее, чем сначала делать SELECT, потом INSERT (race conditions).

4. Bulk операции
   - Для массовой вставки/обновления используйте `session.execute(insert(...))` с списком значений или `session.execute(update(...))` с выражением.

5. Aggregations & counts
   - Для вычисления количества используйте `select(func.count(...))` или `select(func.count()).select_from(...)` и избегайте `.all()` когда нужен только `count`.

6. Пагинация
   - Всегда поддерживайте LIMIT/OFFSET или cursor-based пагинацию для endpoints, возвращающих списки.

7. Транзакции
   - Используйте минимально необходимую область транзакции; не держите транзакцию дольше, чем требуется.


## Примеры оптимизированных CRUD-операций

Ниже — готовые примеры замен для ваших текущих методов. Они используют SQLAlchemy Core/ORM где нужно и async session.

### 1) Получение активных объявлений с картинками + брендом (eager loading + пагинация)

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def get_active_ads(limit: int = 20, offset: int = 0):
    async with AsyncSessionLocal() as session:
        q = (
            select(Ad)
            .where(Ad.is_active.is_(True))
            .options(selectinload(Ad.images), selectinload(Ad.brand))
            .order_by(Ad.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(q)
        return result.scalars().all()

# Это вернёт объекты Ad с заранее подгруженными images и brand без N+1 запросов.
```

### 2) Эффективный insert с returning() (вместо session.add + commit + refresh)

```python
from sqlalchemy import insert

async def add_ad_returning(**kwargs) -> Ad:
    async with AsyncSessionLocal() as session:
        stmt = insert(Ad).values(**kwargs).returning(Ad)
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one()

# Преимущество: один SQL-запрос INSERT ... RETURNING * возвращает вставленную строку.
```

### 3) Upsert пользователя (создать если нет) — PostgreSQL

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_user(sender: str, username: str | None = None):
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(User).values(sender=sender, username=username)
        stmt = stmt.on_conflict_do_update(
            index_elements=[User.sender],
            set_={"username": stmt.excluded.username}
        ).returning(User)
        res = await session.execute(stmt)
        await session.commit()
        return res.scalar_one()
```

### 4) Подсчёт просмотров для списка ads (один запрос)

```python
from sqlalchemy import select, func

async def get_views_counts(ad_ids: list[int]):
    async with AsyncSessionLocal() as session:
        q = select(ViewLog.ad_id, func.count(ViewLog.id).label('views'))
        q = q.where(ViewLog.ad_id.in_(ad_ids)).group_by(ViewLog.ad_id)
        res = await session.execute(q)
        return {row.ad_id: row.views for row in res.fetchall()}
```

### 5) Обновление баланса атомарно

```python
from sqlalchemy import update

async def change_balance(sender: str, delta: int):
    async with AsyncSessionLocal() as session:
        stmt = (
            update(User)
            .where(User.sender == sender)
            .values(balance=User.balance + delta)
            .returning(User.balance)
        )
        res = await session.execute(stmt)
        await session.commit()
        return res.scalar_one_or_none()
```


## Примеры использования CRUD-ов в коде (FastAPI / handlers)

### Пример вызова из асинхронного endpoint (FastAPI)

```python
from fastapi import APIRouter, Depends
from database.crude.add import CrudeAdd

router = APIRouter()

@router.post('/ads')
async def create_ad(payload: dict):
    crud = CrudeAdd()
    ad = await crud.add(**payload)
    return ad
```

### Пример использования в вашем боте (асинхронный хендлер)

```python
from database.crude.user import CrudeUser

async def handler(message):
    user_crud = CrudeUser()
    user = await user_crud.add(sender=message.sender, username=message.sender)
    # ... дальнейшая логика
```


## Что можно улучшить в существующих CRUD-модулях (конкретные рекомендации)

1. Убрать лишние `select()` перед вставкой, где возможен upsert (race-safe).
2. Использовать `.returning()` где сейчас идут `session.add()` + `commit()` + `refresh()` — это сократит количество roundtrips.
3. Для методов, возвращающих списки с отношениями, применить `selectinload`.
4. В аналитических методах (get_popular_ads, get_view_analytics) вернуть результат в виде dict или Pydantic-моделей, и по возможности кэшировать часто запрашиваемые топы.
5. Добавить лимиты и пагинацию для методов, возвращающих `all()`.
6. Рассмотреть использование prepared statements / statement caching в asyncpg (внутри SQLAlchemy это доступно через execution_options) если вы делаете много однотипных запросов.


## Полезные утилиты

- `returning()` — уменьшает число запросов для insert/update.
- `selectinload()`/`joinedload()` — eager load relations.
- `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_*` — upsert patterns.
- `func.count()` и group_by — для агрегатов в один запрос.


## Заключение

Я подготовил набор практик и примеров, которые минимально инвазивно улучшают производительность:

- добавление `selectinload` в методы получения объявлений;
- использование `returning()` при вставках и обновлениях;
- использование upsert вместо "select-then-insert";
- использование bulk/aggregate запросов для аналитики.

Если хотите, могу:

1. Применить автоматические правки в коде CRUD-ов (внести патчи) — я могу реализовать замену существующих методов на оптимизированные (по одному CRUDe за раз).
2. Добавить unit/integration тесты для критичных операций (upsert, добавление рекламы, analytics).
3. Добавить миграцию/индексы (alembic) для рекомендуемых индексов.

Напишите, какие методы CRUD-а (например `CrudeAdd.add`, `CrudeUser.add`, `CrudeViewLog.get_popular_ads`) вы хотите, чтобы я сразу оптимизировал и запатчил в коде — сделаю это в следующем шаге и прогоню быстрые синтаксические проверки.
