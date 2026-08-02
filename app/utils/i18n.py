"""Каталог пользовательских сообщений бота.

Тексты лежат в `app/data/messages/{lang}.json` и читаются по ключу через `t()`.
Дерево меню (`app/data/menu/`) сюда не входит — это отдельный источник
навигационных подписей. Язык процесса задаётся `BOT_LANGUAGE`; при отсутствии
файла или ключа используется русский fallback.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

FALLBACK_LANGUAGE = "ru"


def _messages_dir() -> Path:
    # Ленивый импорт: errors → i18n → config → errors иначе цикл на загрузке.
    from app.data.config import PROJECT_ROOT

    return PROJECT_ROOT / "app" / "data" / "messages"


def __getattr__(name: str) -> Path:
    # Совместимость с `from app.utils.i18n import MESSAGES_DIR`.
    if name == "MESSAGES_DIR":
        return _messages_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _config_error(message: str) -> Exception:
    # Ленивый импорт: errors использует t(), циклов на уровне модуля быть не должно.
    from app.core.errors import ConfigurationError

    return ConfigurationError(message)


def _read_messages_file(language: str) -> dict[str, str] | None:
    path = _messages_dir() / f"{language}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise _config_error(
            f"Файл сообщений {path} содержит некорректный JSON: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise _config_error(f"Файл сообщений {path} должен быть объектом")
    messages: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise _config_error(f"В {path} найден некорректный ключ: {key!r}")
        if not isinstance(value, str):
            raise _config_error(
                f"Значение ключа {key!r} в {path} должно быть строкой"
            )
        messages[key] = value
    return messages


@lru_cache(maxsize=8)
def load_messages(language: str | None = None) -> Mapping[str, str]:
    """Загружает каталог сообщений для языка (с fallback на русский)."""
    from app.data.config import get_settings

    lang = language or get_settings().bot_language
    catalog = _read_messages_file(lang)
    if catalog is None and lang != FALLBACK_LANGUAGE:
        logger.warning(
            "Файл сообщений для языка %s не найден, использую %s",
            lang,
            FALLBACK_LANGUAGE,
        )
        catalog = _read_messages_file(FALLBACK_LANGUAGE)
    if catalog is None:
        raise _config_error(
            f"Не найден каталог сообщений "
            f"({_messages_dir() / f'{FALLBACK_LANGUAGE}.json'})"
        )
    if not catalog and lang != FALLBACK_LANGUAGE:
        fallback = _read_messages_file(FALLBACK_LANGUAGE) or {}
        return fallback
    if lang != FALLBACK_LANGUAGE:
        # Частичный перевод: недостающие ключи берём из русского.
        base = _read_messages_file(FALLBACK_LANGUAGE) or {}
        merged = dict(base)
        merged.update(catalog)
        return merged
    return catalog


def clear_messages_cache() -> None:
    """Сбрасывает кеш каталога (для тестов)."""
    load_messages.cache_clear()


def t(key: str, /, **kwargs: Any) -> str:
    """Возвращает сообщение по ключу с подстановкой плейсхолдеров.

    :raises KeyError: если ключ отсутствует и в выбранном языке, и в fallback
    :raises ConfigurationError: если каталог не загружается
    """
    catalog = load_messages()
    try:
        template = catalog[key]
    except KeyError as exc:
        raise KeyError(f"Сообщение {key!r} отсутствует в каталоге") from exc
    try:
        return template.format_map(_SafeMap(kwargs))
    except KeyError as exc:
        raise KeyError(
            f"Для сообщения {key!r} не передан плейсхолдер {exc.args[0]!r}"
        ) from exc


class _SafeMap(dict):
    """format_map без молчаливой подстановки отсутствующих ключей."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - raise path
        raise KeyError(key)
