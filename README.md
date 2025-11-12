# Green API WhatsApp Bot

В проекте используется официальный пакет `whatsapp-chatbot-python`, который через долгий опрос (long polling) получает события из Green API. Никаких вебхуков и отдельного FastAPI-приложения не требуется.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # заполните ID_INSTANCE и API_TOKEN, а также параметры Postgres
```

Или просто выполните `make install`, чтобы автоматизировать шаги выше.

## Запуск бота (аналогично aiogram)

Файл `app/bot_runner.py` создаёт `GreenAPIBot`, регистрирует базовые хэндлеры (`/start`, запрос баланса, дефолтный автоответ) и сохраняет пользователя в БД через существующие CRUD.

Запуск:

```bash
make bot
# или напрямую
python -m app.bot_runner
```

Что происходит:
- библиотека сама настраивает нужные уведомления в кабинете Green API;
- бот получает входящие события через `receiveNotification`, так что вебхук и публичный домен не нужны;
- все новые отправители попадают в таблицу `users`, команда `баланс` вытаскивает данные из базы.

Дальше можно дописывать фильтры и обработчики (см. `examples` в репозитории Green API).

## Полезные команды Makefile

- `make lint` — прогнать Ruff.
- `make test` — запустить pytest.
- `make up` / `make down` — поднять или остановить Docker-стек.
- `make bot-shell` — открыть shell внутри контейнера приложения.
- `make db-shell` — открыть shell внутри контейнера Postgres.

## Docker/Compose

Для развёртывания без локального Python используйте Docker:

```bash
docker compose up --build
```

Файл `docker-compose.yml` поднимет Postgres 16 и сервис `bot`, который запускает `app.bot_runner`. Настройки тянутся из `.env`, поэтому убедитесь, что там указаны креды БД и ключи Green API. При необходимости добавьте сервис `migrate` с `alembic upgrade head`.

## Дальнейшие шаги
- расширить обработчики, используя модули `database.crude`;
- добавить работу с медиа, кнопками, сценами (`router.state`) из `whatsapp-chatbot-python`;
- при необходимости дописать миграционный контейнер, CI, мониторинг и т.д.
