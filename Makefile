# Basic automation helpers for the WhatsApp bot project.

VENV_DIR ?= .venv
PYTHON ?= python3
PIP := $(VENV_DIR)/bin/pip
PYTHON_BIN := $(VENV_DIR)/bin/python
VENV_SENTINEL := $(VENV_DIR)/.installed

.PHONY: help install bot lint test up upb down downv bot-shell db-shell logs restart

help:
	@echo "Доступные команды:"
	@echo "  make install  - создать виртуальное окружение и поставить зависимости (pip install -e .)"
	@echo "  make bot      - запустить Green API бота (polling)"

$(VENV_SENTINEL): pyproject.toml
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "[venv] Создаю виртуальное окружение в $(VENV_DIR)"; \
		$(PYTHON) -m venv $(VENV_DIR); \
	else \
		echo "[venv] Использую существующее окружение $(VENV_DIR)"; \
	fi
	@echo "[venv] Обновляю pip и устанавливаю пакет проекта"
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@touch $(VENV_SENTINEL)

install: $(VENV_SENTINEL)
	@echo "[install] Готово."

bot: $(VENV_SENTINEL)
	@echo "[bot] Запуск app.bot_runner"
	$(PYTHON_BIN) -m app.bot_runner

lint: $(VENV_SENTINEL)
	@echo "[lint] Проверка Ruff"
	$(VENV_DIR)/bin/ruff check app

test: $(VENV_SENTINEL)
	@echo "[test] Запуск pytest"
	$(VENV_DIR)/bin/pytest

up:
	@echo "[compose] docker compose up"
	docker compose up -d

upb:
	@echo "[compose] docker compose up"
	docker compose up -d --build

down:
	@echo "[compose] docker compose down"
	docker compose down

downv:
	@echo "[compose] docker compose down -v"
	docker compose down -v

rebuild:
	@echo "[compose] docker compose up --build"
	docker compose up -d --build

bot-shell:
	@echo "[compose] Подключаюсь к контейнеру bot"
	@docker compose exec bot /bin/bash || docker compose exec bot /bin/sh

db-shell:
	@echo "[compose] Подключаюсь к контейнеру postgres"
	docker compose exec postgres /bin/sh

logs:
	@echo "[compose] docker compose logs -f bot"
	docker compose logs -f bot
restart: downv upb logs
