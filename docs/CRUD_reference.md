# Полная документация по CRUD-ам

Этот документ описывает все доступные CRUD-классы, их методы, параметры, возвращаемые значения, ошибки и примеры использования. Примеры показаны в двух вариантах:
- прямое использование конкретного CRUD-класса;
- через `CrudManager` (рекомендуемый путь для объединения нескольких операций в одной транзакции).

См. также:
- `docs/CRUD_usage.md` — быстрые примеры и общий подход к транзакциям через `CrudManager`.

## Общие договорённости
- Все CRUD-методы асинхронные (async/await) и используют SQLAlchemy AsyncSession.
- Исключения бизнес-логики бросаются как `ValueError` (например, «уже существует», «не найдено»).
- Методы, создающие записи, по возможности используют `INSERT ... RETURNING` и/или PostgreSQL upsert (`ON CONFLICT DO NOTHING / UPDATE`) для снижения числа запросов и избежания гонок.
- Для объединения нескольких операций в одну транзакцию используйте `CrudManager.session()` + `bind()`/`bind_all()`.

Сокращения в сигнатурах
- `sender`: строковый идентификатор пользователя/отправителя (WhatsApp ID).
- `ad_id`, `brand_id`, `moderator_id`, `image_id`: числовые идентификаторы соответствующих сущностей.

---

## CrudeUser — пользователи
Импорт:
```python
from database.crude import crud_manager, CrudeUser
```

Методы:
- add(sender: str, username: str | None, balance: int = 0) -> User
  - Создаёт пользователя. Уникальность по `sender` (upsert через ON CONFLICT DO NOTHING). Если пользователь уже есть — вернёт существующего.
  - Ошибки: (нет ValueError для дубля — возвращает существующую запись).

- get_by_sender(sender: str) -> User | None
  - Возвращает пользователя по `sender`.

- update_balance(sender: str, amount: int, operation: bool) -> None
  - Изменяет баланс. `operation=True` — увеличить, `False` — уменьшить.

- get_all_ads(sender: str) -> list[Ad]
  - Возвращает все объявления пользователя.

- get_favorites(sender: str) -> list[Favorite]
  - Возвращает избранное пользователя.

- delete(sender: str) -> bool | None
  - Удаляет пользователя. `True` — удалён, `None` — не найден.

Примеры:
```python
# Прямо
crud = CrudeUser()
user = await crud.add(sender="7900...", username="alex")

# Через менеджер
user = await crud_manager.user.add(sender="7900...", username="alex")
```

---

## CrudeAdd — объявления (Ad)
Импорт:
```python
from database.crude import crud_manager, CrudeAdd
```

Методы:
- add(sender, title, description, price, year_car, car_brand_id, mileage_km_car, vin_number, day_count=7, is_active=True) -> Ad
  - Создаёт новое объявление. Уникальность по `vin_number`. Если VIN уже существует, бросает `ValueError`.

- update(ad_id, title=None, description=None, price=None, year_car=None, car_brand_id=None, mileage_km_car=None, vin_number=None, day_count=None, is_active=None) -> Ad
  - Обновляет объявление. Бросает `ValueError`, если `ad_id` не найден, или VIN конфликтует.

- delete(ad_id: int) -> bool | None
  - Удаляет объявление. `True` — удалено, `None` — не найдено.

- get_all_active() -> list[Ad]
- get_by_sender(sender: str) -> list[Ad]
- filter_ads(car_brand_id=None, min_price=None, max_price=None, year_car=None, min_mileage=None, max_mileage=None) -> list[Ad]
- get_moderation(ad_id: int) -> Moderation | None
- get_by_vin(vin_number: str) -> Ad | None
- change_status(ad_id: int, is_active: bool) -> Ad  (ValueError если не найдено)
- extend_ad(ad_id: int, additional_days: int) -> Ad (ValueError если не найдено)

Пример:
```python
ad = await crud_manager.ad.add(
    sender="7900...",
    title="BMW 3",
    description="E90",
    price=10000,
    year_car=2010,
    car_brand_id=1,
    mileage_km_car=150000,
    vin_number="WBAX...",
)
```

---

## CrudeFavorite — избранное
Импорт:
```python
from database.crude import crud_manager, CrudeFavorite
```

Методы:
- add(sender: str, ad_id: int) -> Favorite
  - Идемпотентная вставка: если запись уже есть, вернёт существующую. Бросает `ValueError`, если не найден `User` или `Ad`.

- delete(sender: str, ad_id: int) -> bool | None
  - Удаляет из избранного. `True` — удалено, `None` — не найдено.

- get_by_sender(sender: str) -> list[Favorite]

Пример:
```python
fav = await crud_manager.favorite.add(sender="7900...", ad_id=123)
```

---

## CrudeAdImage — изображения объявлений
Импорт:
```python
from database.crude import crud_manager, CrudeAdImage
```

Методы:
- add(ad_id: int, image_url: str) -> AdImage
  - Создаёт изображение. Бросает `ValueError`, если объявление не найдено.

- get_all_by_ad_id(ad_id: int) -> list[AdImage]
- delete(image_id: int) -> bool | None

Пример:
```python
img = await crud_manager.car_image.add(ad_id=123, image_url="https://...")
```

---

## CrudeCarBrand — марки автомобилей
Импорт:
```python
from database.crude import crud_manager, CrudeCarBrand
```

Методы:
- get_all() -> list[CarBrand]
- add(name: str) -> CarBrand
  - Бросает `ValueError`, если марка уже существует (уникальность по имени).

- delete(brand_id: int) -> bool | None
- update(brand_id: int, name: str) -> CarBrand
  - Бросает `ValueError`, если `brand_id` не найден или новое имя дублирует другую марку.

Пример:
```python
brand = await crud_manager.car_brand.add(name="BMW")
brand = await crud_manager.car_brand.update(brand_id=brand.id, name="Mercedes")
```

---

## CrudeModeration — модерация объявлений
Импорт:
```python
from database.crude import crud_manager, CrudeModeration
```

Методы:
- get_pending_ads() -> list[Ad]
- update_status(ad_id: int, status: str, comment: str | None = None) -> Moderation
  - Обновляет статус. Бросает `ValueError`, если модерация не найдена.

- assign_moderator(ad_id: int, moderator_id: int) -> Moderation
  - Привязывает модератора. Бросает `ValueError`, если модерация или модератор не найдены.

- get_moderation_history(moderator_id: int) -> list[Moderation]
- get_rejected_comments(ad_id: int) -> str | None

Пример:
```python
await crud_manager.moderation.update_status(ad_id=1, status="approved")
await crud_manager.moderation.assign_moderator(ad_id=1, moderator_id=10)
```

---

## CrudeModerator — модераторы
Импорт:
```python
from database.crude import crud_manager, CrudeModerator
```

Методы:
- add(telegram_id: int, username: str | None = None) -> Moderator
  - Создаёт модератора. Если уже существует с таким `telegram_id`, бросает `ValueError`.

- get_all_active() -> list[Moderator]
- deactivate(moderator_id: int) -> Moderator
  - Деактивирует модератора. Бросает `ValueError`, если не найдено.

- get_moderation_count(moderator_id: int) -> int
  - Кол-во проверок модератора.

Пример:
```python
moder = await crud_manager.moderator.add(telegram_id=123456, username="mod")
await crud_manager.moderator.deactivate(moderator_id=moder.id)
```

---

## CrudePayment — платежи
Импорт:
```python
from database.crude import crud_manager, CrudePayment
```

Методы:
- add(sender: str, amount: int, description: str | None = None) -> Payment
  - Создаёт платеж. Бросает `ValueError`, если `User` не найден.

- get_by_sender(sender: str) -> list[Payment]
- get_spending_summary() -> list[tuple[str, int]]
  - Агрегированная сводка трат по пользователям. (Примечание: реализацию можно доработать до `SUM` при необходимости.)

- get_top_clients(limit: int = 10) -> list[tuple[str, int]]
  - Топ пользователей по тратам (см. примечание о возможной доработке агрегации).

Пример:
```python
payment = await crud_manager.payment.add(sender="7900...", amount=500)
```

---

## CrudeViewLog — просмотры объявлений
Импорт:
```python
from database.crude import crud_manager, CrudeViewLog
```

Методы:
- add(ad_id: int, sender: str) -> ViewLog
  - Создаёт запись о просмотре. Бросает `ValueError`, если объявление не найдено.

- get_view_count(ad_id: int) -> int
- get_by_sender(sender: str) -> list[ViewLog]
- get_view_analytics() -> list[tuple[str, int]]
  - Аналитика: пары (sender, ad_id, view_count).

- get_popular_ads(limit: int = 10) -> list[tuple[int, int]]
  - Топ популярных объявлений (ad_id, count).

- filter_by_date(start_date: datetime, end_date: datetime) -> list[ViewLog]

Пример:
```python
log = await crud_manager.view.add(ad_id=1, sender="7900...")
count = await crud_manager.view.get_view_count(ad_id=1)
popular = await crud_manager.view.get_popular_ads(limit=10)
```

---

## Транзакции и связывание CRUD через CrudManager
```python
from database.crude import crud_manager

async with crud_manager.session() as session:
    bound = crud_manager.bind_all(session)
    await bound.user.update_balance("7900...", 100, True)
    await bound.favorite.add("7900...", 123)
    await session.commit()
```

## Тестирование
- Для модульных тестов можно создавать отдельный `CrudManager` с тестовым `session_factory`.
- Для интеграционных тестов используйте временную БД (Docker) и транзакции на тест-кейс.

## Примечания по производительности
- Методы вставок/обновлений используют `RETURNING` (где возможно) и upsert для снижения числа запросов.
- Избегайте «вечных» сессий — используйте сессию на время операции/транзакции.
