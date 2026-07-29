"""Асинхронная очередь телеметрии: хендлер не ждёт запись в БД.

События копятся в `asyncio.Queue` фиксированного размера и уходят в БД
пачками (по размеру или по таймауту). При переполнении очередь отбрасывает
событие с предупреждением — статистика важнее UX не бывает.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.core.executor import run_blocking
from app.data.config import Settings, get_settings
from app.repositories import repositories
from app.repositories.dto import UserEventInput

logger = logging.getLogger(__name__)

# Просмотр экрана по callback-кнопке. Другие kind появятся при расширении
# телеметрии (например, ввод тикера текстом).
EVENT_KIND_VIEW = "view"

FlushCallback = Callable[[Sequence["PendingEvent"]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PendingEvent:
    """Событие в очереди до пакетной записи."""

    user_id: int
    kind: str
    node: str
    ticker: str | None = None


class EventBus:
    """Накопитель событий с фоновой записью пачками."""

    def __init__(
        self,
        *,
        queue_size: int,
        batch_size: int,
        flush_interval: float,
        flush: FlushCallback | None = None,
    ) -> None:
        self._queue: asyncio.Queue[PendingEvent | None] = asyncio.Queue(
            maxsize=queue_size
        )
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        # Подмена в тестах: без обращения к БД.
        self._flush_callback = flush
        self._task: asyncio.Task[None] | None = None

    def emit(self, event: PendingEvent) -> None:
        """Кладёт событие в очередь без ожидания. При переполнении — отбрасывает."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Очередь телеметрии переполнена (%s), событие отброшено",
                self._queue.maxsize,
            )

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._worker(), name="event-bus-flusher")
        logger.info(
            "Телеметрия запущена: очередь=%s, пачка=%s, интервал=%.1f с",
            self._queue.maxsize,
            self._batch_size,
            self._flush_interval,
        )

    async def stop(self) -> None:
        """Останавливает воркер и досылает накопленное."""
        if self._task is None:
            return
        # None — маркер остановки: воркер дочитывает очередь и выходит.
        # При переполненной очереди вытесняем одно событие — оно и так
        # считалось допустимой потерей при backpressure.
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            logger.info("Телеметрия остановлена")

    async def _worker(self) -> None:
        batch: list[PendingEvent] = []
        try:
            while True:
                try:
                    # Пока пачка пуста — ждём событие без таймаута; иначе
                    # сбрасываем неполную пачку по истечении интервала.
                    timeout = self._flush_interval if batch else None
                    item = await asyncio.wait_for(
                        self._queue.get(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    await self._flush(batch)
                    batch = []
                    continue

                if item is None:
                    # Дочитываем всё, что успели положить до маркера остановки.
                    while True:
                        try:
                            leftover = self._queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        if leftover is not None:
                            batch.append(leftover)
                    await self._flush(batch)
                    return

                batch.append(item)
                if len(batch) >= self._batch_size:
                    await self._flush(batch)
                    batch = []
        except asyncio.CancelledError:
            # На отмене тоже пытаемся сохранить уже накопленное.
            while True:
                try:
                    leftover = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if leftover is not None:
                    batch.append(leftover)
            if batch:
                await self._flush(batch)
            raise

    async def _flush(self, batch: list[PendingEvent]) -> None:
        if not batch:
            return
        if self._flush_callback is not None:
            await self._flush_callback(batch)
            return
        settings = get_settings()
        payload = [
            UserEventInput(
                user_id=event.user_id,
                kind=event.kind,
                node=event.node,
                ticker=event.ticker,
            )
            for event in batch
        ]
        try:
            await run_blocking(
                repositories.event.insert_many,
                payload,
                timeout=settings.db_timeout,
                description="запись телеметрии",
            )
        except Exception:  # noqa: BLE001 — сбой телеметрии не должен ронять воркер
            logger.warning(
                "Не удалось записать пачку из %s событий",
                len(payload),
                exc_info=True,
            )


_bus: EventBus | None = None


def get_event_bus() -> EventBus | None:
    """Текущая шина или `None`, если телеметрия ещё не запущена / уже остановлена."""
    return _bus


async def start_event_bus(settings: Settings) -> EventBus:
    """Чистит просроченные записи и запускает фоновую запись пачек."""
    global _bus
    if _bus is not None:
        return _bus

    try:
        deleted = await run_blocking(
            repositories.event.purge_older_than,
            settings.events_retention_days,
            timeout=settings.db_timeout,
            description="очистка старой телеметрии",
        )
        if deleted:
            logger.info(
                "Удалено устаревших событий телеметрии: %s (старше %s сут.)",
                deleted,
                settings.events_retention_days,
            )
    except Exception:  # noqa: BLE001 — чистка не блокирует старт бота
        logger.warning("Не удалось очистить старую телеметрию", exc_info=True)

    bus = EventBus(
        queue_size=settings.events_queue_size,
        batch_size=settings.events_batch_size,
        flush_interval=settings.events_flush_interval,
    )
    await bus.start()
    _bus = bus
    return bus


async def stop_event_bus() -> None:
    """Досылает пачку и останавливает воркер."""
    global _bus
    bus = _bus
    _bus = None
    if bus is not None:
        await bus.stop()
