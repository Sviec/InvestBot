"""Вынос блокирующего кода из event loop.

Обращения к БД (psycopg2), к yfinance и рендеринг matplotlib синхронные и
занимают сотни миллисекунд или секунды. Выполнение их прямо в корутине
останавливает обработку всех остальных апдейтов, поэтому любой такой вызов
идёт через `run_blocking` в пул потоков с ограниченным размером и таймаутом.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

from app.core.errors import OperationTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()
_DEFAULT_WORKERS = 8


def init_executor(max_workers: int) -> ThreadPoolExecutor:
    """Создаёт пул потоков. Вызывается один раз при старте приложения."""
    global _executor
    with _executor_lock:
        if _executor is not None:
            return _executor
        _executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="investbot-worker"
        )
        logger.info("Пул рабочих потоков создан: %d потоков", max_workers)
        return _executor


def get_executor() -> ThreadPoolExecutor:
    if _executor is None:
        return init_executor(_DEFAULT_WORKERS)
    return _executor


def shutdown_executor(wait: bool = True) -> None:
    global _executor
    with _executor_lock:
        if _executor is None:
            return
        logger.info("Останавливаю пул рабочих потоков")
        _executor.shutdown(wait=wait, cancel_futures=True)
        _executor = None


async def run_blocking(
    func: Callable[..., T],
    *args: object,
    timeout: float | None = None,
    limiter: asyncio.Semaphore | None = None,
    description: str | None = None,
    **kwargs: object,
) -> T:
    """Выполняет синхронную функцию в пуле потоков.

    :param timeout: ограничение на ожидание результата; поток при этом не
        прерывается (Python не умеет убивать потоки), но корутина освобождается
    :param limiter: семафор для ресурсоёмких операций, чтобы десять
        одновременных рендеров не съели всю память
    """
    label = description or getattr(func, "__qualname__", repr(func))

    if limiter is not None:
        async with limiter:
            return await _submit(func, args, kwargs, timeout, label)
    return await _submit(func, args, kwargs, timeout, label)


async def _submit(
    func: Callable[..., T],
    args: tuple[object, ...],
    kwargs: dict[str, object],
    timeout: float | None,
    label: str,
) -> T:
    loop = asyncio.get_running_loop()
    context = contextvars.copy_context()
    call = functools.partial(context.run, functools.partial(func, *args, **kwargs))
    future = loop.run_in_executor(get_executor(), call)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError as exc:
        logger.error("Операция «%s» превысила таймаут %.1f с", label, timeout or 0.0)
        raise OperationTimeoutError(f"Таймаут операции {label}") from exc
