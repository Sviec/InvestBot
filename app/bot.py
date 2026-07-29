"""Сборка бота, диспетчера и хранилища состояний."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from app.data.config import Settings
from app.handlers import build_router
from app.middlewares import (
    ContextMiddleware,
    ErrorsMiddleware,
    TelemetryMiddleware,
    ThrottlingMiddleware,
    UserMiddleware,
)

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )


async def create_storage(settings: Settings) -> BaseStorage:
    """Хранилище FSM в памяти процесса.

    В состоянии живёт только `origin` на время ожидания тикера — оно
    транзитное и при перезапуске теряется без вреда. Бот работает одним
    процессом на long polling, поэтому `MemoryStorage` достаточно. Функция
    оставлена как единственная точка замены хранилища.
    """
    _ = settings
    return MemoryStorage()


def create_dispatcher(settings: Settings, storage: BaseStorage) -> Dispatcher:
    dispatcher = Dispatcher(storage=storage)

    dispatcher.update.outer_middleware(ContextMiddleware())
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(
            ThrottlingMiddleware(
                rate=settings.throttle_rate, cache_size=settings.throttle_cache_size
            )
        )
        # Внутренние middleware диспетчера применяются и к вложенным роутерам.
        # Порядок (снаружи внутрь): Errors → User → Telemetry → хендлер.
        # Errors оборачивает остальное, иначе сбой БД при регистрации останется
        # без ответа. User кладёт `user_id` до Telemetry. Telemetry после
        # хендлера только ставит событие в очередь и не ждёт БД.
        observer.middleware(ErrorsMiddleware())
        observer.middleware(UserMiddleware())
        observer.middleware(TelemetryMiddleware())

    dispatcher.include_router(build_router())

    @dispatcher.errors()
    async def on_unhandled_error(event: ErrorEvent) -> bool:
        logger.critical(
            "Необработанная ошибка апдейта %s",
            getattr(event.update, "update_id", "?"),
            exc_info=event.exception,
        )
        return True

    return dispatcher
