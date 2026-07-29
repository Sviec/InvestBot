"""Точка входа.

Запуск устроен по принципу «падать рано»: конфигурация, дерево меню, база
данных и токен проверяются до начала опроса Telegram, чтобы неверная
настройка обнаруживалась в момент старта, а не при первом нажатии кнопки.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError

from app.bot import create_bot, create_dispatcher, create_storage
from app.core.errors import ConfigurationError
from app.core.events import start_event_bus, stop_event_bus
from app.core.executor import init_executor, run_blocking, shutdown_executor
from app.core.logging import setup_logging
from app.data.config import Settings, get_settings
from app.db.session import dispose_engine, healthcheck
from app.entities.base import get_cache
from app.entities.session import close_market_session
from app.utils.navigation import get_menu
from app.utils.path_codec import encode_path

logger = logging.getLogger(__name__)

EXIT_CONFIGURATION_ERROR = 78  # EX_CONFIG
EXIT_DEPENDENCY_ERROR = 69  # EX_UNAVAILABLE


async def preflight(settings: Settings) -> None:
    """Проверяет зависимости до старта опроса."""
    menu = get_menu()
    # Прогреваем таблицу псевдонимов: несогласованное меню обнаружится здесь,
    # а не при построении первой клавиатуры.
    encode_path("main_menu")
    logger.info("Дерево меню готово, корневых разделов: %d", len(menu))

    if not await run_blocking(
        healthcheck, timeout=settings.db_timeout, description="проверка БД"
    ):
        raise ConnectionError(
            f"Нет соединения с базой данных ({settings.safe_database_url})"
        )
    logger.info("Соединение с БД проверено")


async def shutdown(bot: Bot, dispatcher: Dispatcher) -> None:
    """Освобождает ресурсы: соединения, пул потоков, HTTP-сессию Telegram."""
    logger.info("Останавливаюсь")
    get_cache().log_stats()
    try:
        await dispatcher.storage.close()
    except Exception:  # noqa: BLE001 — на остановке важно дойти до конца
        logger.warning("Не удалось корректно закрыть хранилище FSM", exc_info=True)
    try:
        await bot.session.close()
    except Exception:  # noqa: BLE001
        logger.warning("Не удалось закрыть HTTP-сессию Telegram", exc_info=True)
    close_market_session()
    # Досылаем накопленную телеметрию до закрытия пула и движка БД.
    await stop_event_bus()
    dispose_engine()
    shutdown_executor(wait=False)
    logger.info("Остановлен")


async def run() -> int:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    setup_logging(
        level=settings.log_level,
        log_dir=settings.log_dir,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )
    settings.ensure_directories()
    init_executor(settings.worker_threads)

    try:
        await preflight(settings)
    except ConfigurationError as exc:
        logger.critical("Ошибка конфигурации: %s", exc)
        shutdown_executor(wait=False)
        return EXIT_CONFIGURATION_ERROR
    except Exception as exc:  # noqa: BLE001 — на старте показываем причину и выходим
        logger.critical("Проверка зависимостей не пройдена: %s", exc)
        dispose_engine()
        shutdown_executor(wait=False)
        return EXIT_DEPENDENCY_ERROR

    # После проверки БД: чистка просроченных событий и фоновая запись пачек.
    await start_event_bus(settings)

    bot = create_bot(settings)
    storage = await create_storage(settings)
    dispatcher = create_dispatcher(settings, storage)

    try:
        me = await bot.get_me()
        logger.info("Запускаюсь как @%s (id=%s)", me.username, me.id)
    except TelegramUnauthorizedError:
        logger.critical("BOT_TOKEN отклонён Telegram. Проверьте значение в .env")
        await shutdown(bot, dispatcher)
        return EXIT_CONFIGURATION_ERROR

    try:
        # Оставшийся вебхук приводит к конфликту с long polling.
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types()
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    finally:
        await shutdown(bot, dispatcher)
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
