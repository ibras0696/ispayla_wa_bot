FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app app
COPY alembic alembic
COPY docs docs
COPY Makefile Makefile
COPY .env .env
COPY .env.example .env.example

RUN pip install --upgrade pip && pip install --no-cache-dir -e .

CMD ["python", "-m", "app.bot_runner"]
