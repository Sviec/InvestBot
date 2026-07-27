"""Настройка логирования.

Идентификатор пользователя и апдейта прокидываются через `ContextVar`, поэтому
любая строка лога — включая написанную в глубине слоя данных — содержит
контекст запроса без явной передачи параметров.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from contextvars import ContextVar
from pathlib import Path

user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
update_id_var: ContextVar[int | None] = ContextVar("update_id", default=None)

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] [u=%(user_id)s upd=%(update_id)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Библиотеки, которые на INFO создают больше шума, чем пользы.
NOISY_LOGGERS = {
    "aiogram.event": logging.WARNING,
    "asyncio": logging.WARNING,
    "matplotlib": logging.WARNING,
    "matplotlib.font_manager": logging.ERROR,
    "peewee": logging.WARNING,
    "PIL": logging.WARNING,
    "urllib3": logging.WARNING,
    "yfinance": logging.WARNING,
}


class ContextFilter(logging.Filter):
    """Добавляет в запись лога идентификаторы из контекста обработки апдейта."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = user_id_var.get() or "-"
        record.update_id = update_id_var.get() or "-"
        return True


def setup_logging(
    *,
    level: str = "INFO",
    log_dir: Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Конфигурирует корневой логгер. Повторный вызов безопасен."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    context_filter = ContextFilter()
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Консоль Windows по умолчанию в cp1251 и падает на кириллице и символах
    # вроде «◀». Ошибка кодирования в логгере не должна ронять обработку.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            pass

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(context_filter)
    root.addHandler(console)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "bot.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            root.addHandler(file_handler)
        except OSError as exc:
            # Отсутствие прав на запись не должно мешать боту стартовать:
            # продолжаем только с выводом в stdout.
            root.warning("Не удалось включить запись логов в %s: %s", log_dir, exc)

    for name, noisy_level in NOISY_LOGGERS.items():
        logging.getLogger(name).setLevel(noisy_level)

    logging.captureWarnings(True)
