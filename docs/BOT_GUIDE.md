# Гайд по работе с ботом на `whatsapp-chatbot-python` (с примерами)

Практическая шпаргалка: как устроен бот, как добавлять кнопки, стейты, CRUD, по мотивам нашего кода.

## Быстрый старт
- Точка входа: `app/bot_runner.py` → `app/bot/runner.py:create_bot()`.
- Бот на long polling, вебхуки не нужны.
- Главное в `Notification`:
  ```python
  def handle_start(notification: Notification, settings: Settings, allowed: set[str] | None):
      if not guard_sender(notification, allowed):
          return
      notification.answer("Привет!")
  ```
- Ответы: `notification.answer("текст")`, `notification.answer_with_file(path, caption="...")`.
- Белый список: `ALLOWED_SENDERS` в `.env` (можно писать без домена `@c.us`).

## Роутинг (пример)
`app/bot/runner.py`:
```python
bot.router.message(command="start")(wrap(handle_start))
bot.router.message(text_message="баланс")(wrap(handle_balance))
bot.router.message(text_message=["0", "00", "000"])(wrap(handle_main_menu))
bot.router.message(type_message=["buttonsResponseMessage", "interactiveButtonsResponse"])(wrap(handle_menu_selection))
bot.router.message(text_message=menu_text_triggers)(wrap(handle_menu_text))
bot.router.message()(wrap(handle_fallback))  # всё остальное
```
Идея: для каждого сценария — свой хендлер, fallback решает «куда отдать» (продажа/покупка/автоответ).

## Кнопки и тексты (пример)
- Константы в `app/bot/ui/buttons.py` / `texts.py`.
- Отправка интерактивных кнопок:
  ```python
  def send_main_menu(notification: Notification):
      payload = {
          "chatId": notification.chat,
          **MAIN_MENU_TEXT,
          "buttons": MAIN_MENU_BUTTONS,
      }
      notification.api.request(
          "POST",
          "{{host}}/waInstance{{idInstance}}/sendInteractiveButtonsReply/{{apiTokenInstance}}",
          payload,
      )
  ```
- Текстовые алиасы дублируют кнопки (`TEXT_TO_BUTTON`, `BUY_TEXT_TO_BUTTON`), чтобы тестировать без UI.

## Состояния и формы (пример мастера продажи)
- Хранение в памяти процесса: `services/forms.py`.
- Шаги формы:
  ```python
  SELL_FORM_STEPS = [
      {"key": "title", "prompt": "1️⃣ Заголовок", "validator": lambda v: _validate_text(v, "Заголовок")},
      {"key": "brand", "prompt": "Марка", "validator": ...},
      # ...
      {"key": "photos", "prompt": "Фото (до 3), напиши 'готово' когда хватит", "type": "photos"},
  ]
  ```
- Обработка:
  ```python
  if sell_form_manager.has_state(sender):
      media_reply = sell_form_manager.handle_media(sender, message_data)
      if media_reply:
          notification.answer(media_reply)
          return
      reply = sell_form_manager.handle(sender, incoming_text)
      notification.answer(reply)
      return
  ```
- Сохранение в БД: `create_ad_from_form` в `state.py` (через CRUD).
- Ограничения: `MAX_PHOTOS = 3`, обязательна минимум 1 фото (проверка в форме).

## Каталог и фильтры (пример)
- Состояние фильтров/кэша: `_FILTER_STATE`, `_LAST_CATALOG`, `_LAST_DETAILS` в `handlers/buy.py`.
- Обновление фильтра цены:
  ```python
  def _update_price_filter(sender: str, text: str) -> str:
      low, high = _parse_range(text)  # "цена 100000-500000"
      state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
      state["min_price"], state["max_price"] = low, high
      state["page"] = 0
      _persist_filter_state()
      return _render_filtered(sender)
  ```
- Рендер списка:
  ```python
  def _render_filtered(sender: str) -> str:
      state = _FILTER_STATE.setdefault(sender, {"page": 0, "page_size": PAGE_SIZE})
      total = count_filtered_public_ads(state)
      ads = filter_public_ads(state, page=state["page"], page_size=state["page_size"])
      _LAST_CATALOG[sender] = [ad["id"] for ad in ads]
      # ...
  ```
- Выбор по номеру/ID: `_extract_public_id` — теперь приоритет ID, если число совпадает с ID в списке, иначе трактуется как позиция.

## Работа с БД (паттерн)
- Асинхронные CRUD в `app/database/crude/*`.
- Синхронные фасады в `services/state.py` (через `DBRunner.run`):
  ```python
  def get_ads_preview(sender: str, limit: int = 5):
      return db_runner.run(_get_ads_preview(sender, limit))
  ```
- Хендлеры не трогают CRUD напрямую, только функции `state.py`.
- Файлы фото сохраняются в `media/uploads`, путь пишется в `ad_images`.

## Примеры типовых задач (пошагово)
1) **Добавить кнопку и хендлер**  
   - `ui/buttons.py`: добавить кнопку и алиас в `TEXT_TO_BUTTON`.  
   - `runner.py`: повесить `bot.router.message(text_message=[...])`.  
   - В хендлере — вызвать сервис/CRUD через `state.py`.

2) **Новая форма/мастер**  
   - Создать менеджер по аналогии с `SellFormManager` (шаги, валидаторы, `handle/handle_media`).  
   - В fallback проверять `has_state` и прокидывать сообщения в форму.  
   - В `state.py` сделать функцию сохранения в БД.

3) **Новый атрибут объявления**  
   - `models.py` поле + `crude/add.py` (insert/update) + `state.py` (прокинуть в витрину/форму).  
   - Добавить в форму (если нужно собирать от пользователя) и в карточки покупки/продажи.

4) **Фильтр по новому полю**  
   - Расширить `_FILTER_STATE` в `buy.py`, добавить апдейтер `_update_*`, учесть в `filter_public_ads` / `count_filtered_public_ads` (через `state.py` → CRUD).

## Тестирование/отладка
- Логи: `docker compose logs -f bot`.  
- Ограничить рассылку: `ALLOWED_SENDERS` в `.env`.  
- Юнит-тесты: пример `tests/test_buy_utils.py` (чистка стейта, подмена `_STATE_FILE`).  
- Если каталог не открывается по номеру — проверь `_LAST_CATALOG` и что перед этим был отправлен список.

## Ограничения/оговорки
- State хранится в памяти процесса (для продакшена лучше Redis).  
- Alembic миграций нет — одноразовые DDL можно выполнять через `scripts/add_ads_columns.py` или `docker compose exec postgres psql ...`.  
- Максимум фото в форме — 3, минимум 1.

Структура: UI и тексты — в `ui/`, хендлеры тонкие, данные — через `state.py`/CRUD. Используйте приведённые куски кода как шаблон для новых сценариев. 
