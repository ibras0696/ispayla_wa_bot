# Использование CRUD и CrudManager

В этом документе показано, как использовать отдельные CRUD-классы и как объединять несколько операций в одну транзакцию с помощью CrudManager.

## Быстрый старт

- Прямое использование CRUD (как раньше):

```python
from database.crude import CrudeUser

crud_user = CrudeUser()
user = await crud_user.add(sender="7900...", username="alex")
```

- Через менеджер (единая точка входа):

```python
from database.crude import crud_manager

# Простое использование (под капотом создастся своя сессия на время вызова)
user = await crud_manager.user.add(sender="7900...", username="alex")
```

## Одна транзакция для нескольких операций

Если нужно выполнить несколько действий в одной транзакции (одна и та же AsyncSession), используйте контекст `crud_manager.session()` и привязку CRUD к этой сессии.

```python
from database.crude import crud_manager

async with crud_manager.session() as session:
    # Привяжем все CRUD к этой сессии
    bound = crud_manager.bind_all(session)

    # Несколько операций в одной транзакции
    await bound.user.update_balance(sender="7900...", amount=100, operation=True)
    await bound.favorite.add(sender="7900...", ad_id=123)

    # Явный commit (по желанию — можно commit делать и внутри CRUD)
    await session.commit()
```

Альтернатива — привязать выборочные CRUD:

```python
async with crud_manager.session() as session:
    user_crud = crud_manager.bind(crud_manager.user, session)
    fav_crud = crud_manager.bind(crud_manager.favorite, session)

    await user_crud.update_balance(sender, 50, True)
    await fav_crud.add(sender, ad_id)
    await session.commit()
```

## Как это устроено

- `CrudManager` хранит единый `session_factory` (по умолчанию `AsyncSessionLocal`).
- По умолчанию каждый метод CRUD открывает и закрывает свою сессию (как и раньше) — это безопасно для большинства случаев.
- Для объединения операций в одну транзакцию используем `async with crud_manager.session(): ...` и `bind(...)`/`bind_all(...)`.
- `bind(...)` подменяет у экземпляра CRUD атрибут `session` на контекстный менеджер, который отдаёт уже открытую сессию.

## Примеры отдельных CRUD

### Пользователи
```python
from database.crude import crud_manager

# Создать пользователя (upsert — уникален по sender)
user = await crud_manager.user.add(sender="7900...", username="alex")

# Получить пользователя
user = await crud_manager.user.get_by_sender(sender="7900...")

# Обновить баланс
await crud_manager.user.update_balance(sender="7900...", amount=200, operation=True)
```

### Объявления (Ad)
```python
from database.crude import crud_manager

ad = await crud_manager.ad.add(
    sender="7900...",
    title="BMW",
    description="E90",
    price=10000,
    year_car=2010,
    car_brand_id=1,
    mileage_km_car=150000,
    vin_number="WBAXXXXXXX",
)

# Фильтрация
ads = await crud_manager.ad.filter_ads(min_price=5000, year_car=2010)
```

### Избранное (Favorite)
```python
from database.crude import crud_manager

fav = await crud_manager.favorite.add(sender="7900...", ad_id=123)
# idempotent: повторный вызов вернёт существующую запись
```

### Изображения (AdImage)
```python
from database.crude import crud_manager

img = await crud_manager.car_image.add(ad_id=123, image_url="https://...")
images = await crud_manager.car_image.get_all_by_ad_id(123)
```

### Марки (CarBrand)
```python
from database.crude import crud_manager

brand = await crud_manager.car_brand.add(name="BMW")
brand = await crud_manager.car_brand.update(brand_id=1, name="Mercedes")
```

### Модерация
```python
from database.crude import crud_manager

await crud_manager.moderation.update_status(ad_id=1, status="approved")
await crud_manager.moderation.assign_moderator(ad_id=1, moderator_id=10)
```

### Платежи (Payment)
```python
from database.crude import crud_manager

payment = await crud_manager.payment.add(sender="7900...", amount=500)
```

### Просмотры (ViewLog)
```python
from database.crude import crud_manager

log = await crud_manager.view.add(ad_id=1, sender="7900...")
count = await crud_manager.view.get_view_count(ad_id=1)
popular = await crud_manager.view.get_popular_ads(limit=10)
```

## Замечания и лучшие практики
- Не используйте «одну глобальную живую сессию». Открывайте сессию на время операции или транзакции.
- Для сложных сценариев (несколько операций в одной транзакции) используйте `crud_manager.session()` и `bind_all(...)`.
- Исключения — не забывайте про `rollback`/`commit`. В наших CRUD методах уже есть обработка, но при общей транзакции ответственность на вызывающей стороне.
- Тестирование: можно мокать `crud_manager.session()` и/или подставлять тестовый `session_factory` при создании `CrudManager`.
