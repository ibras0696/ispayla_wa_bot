from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Iterable, Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger("app.bot.services.media")

_CACHE_DIR = Path("media/cache")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def prepare_media_paths(items: Iterable[Any], limit: int | None = None) -> list[Path]:
    """
    Преобразовать список ORM-объектов/путей/URL в существующие файлы.
    Если путь относительный — приводим к абсолютному.
    Если путь HTTP(S) — скачиваем во временную папку media/cache.
    """
    paths: list[Path] = []
    for item in items:
        if limit is not None and len(paths) >= limit:
            break
        url = _extract_url(item)
        if not url:
            continue
        resolved = _resolve_path(url)
        if not resolved:
            continue
        paths.append(resolved)
    return paths


def _extract_url(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, Path):
        return str(item)
    if isinstance(item, str):
        return item
    return getattr(item, "image_url", "") or ""


def _resolve_path(raw: str) -> Path | None:
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if path.exists():
        return path
    if raw.startswith("http://") or raw.startswith("https://"):
        return _download_remote(raw)
    logger.debug("Файл фото не найден: %s", raw)
    return None


def _download_remote(url: str) -> Path | None:
    """Скачать внешний файл и сохранить в кеше."""
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось скачать фото %s: %s", url, exc)
        return None
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = _CACHE_DIR / filename
    target.write_bytes(response.content)
    return target
