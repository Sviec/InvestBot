"""Подготовка текста к отправке в Telegram.

Бот работает с `parse_mode=HTML`, а описания компаний и заголовки новостей
приходят из внешнего источника и содержат `&`, `<` и `>`. Без экранирования
Telegram отклоняет сообщение целиком, поэтому любой внешний текст проходит
через `escape`.
"""

from __future__ import annotations

import html
from typing import Iterable

TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024


def escape(value: object) -> str:
    """Экранирует значение для HTML-разметки Telegram."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def chunk(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    """Режет длинный текст на части, стараясь не рвать строки и слова."""
    if limit <= 0:
        raise ValueError("limit должен быть положительным")
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remainder = text
    while len(remainder) > limit:
        window = remainder[:limit]
        split_at = window.rfind("\n")
        if split_at < limit // 2:
            split_at = window.rfind(" ")
        if split_at < limit // 2:
            split_at = limit
        parts.append(remainder[:split_at].rstrip())
        remainder = remainder[split_at:].lstrip()
    if remainder:
        parts.append(remainder)
    return parts


def truncate(text: str, limit: int = TELEGRAM_TEXT_LIMIT, suffix: str = "…") -> str:
    """Обрезает текст до лимита, добавляя многоточие."""
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)].rstrip() + suffix


def format_number(value: object, digits: int = 2) -> str | None:
    """Форматирует число с разделителями разрядов; None — если это не число."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN и бесконечности
        return None
    return f"{number:,.{digits}f}".replace(",", " ")


def format_percent(value: object, digits: int = 2) -> str | None:
    """Форматирует долю (0.153) как проценты (15.30%)."""
    number = _safe_float(value)
    if number is None:
        return None
    formatted = format_number(number * 100, digits)
    return None if formatted is None else f"{formatted}%"


def _safe_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def join_lines(lines: Iterable[str | None]) -> str:
    """Собирает непустые строки в текст."""
    return "\n".join(line for line in lines if line)
