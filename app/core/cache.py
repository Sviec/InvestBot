"""Потокобезопасный TTL-кеш с поддержкой отдачи устаревших данных.

Кеш используется из рабочих потоков (`run_blocking`), поэтому синхронизация
обязательна. Помимо обычного `get`, есть `get_stale`: если внешний источник
недоступен, лучше показать данные пятиминутной давности, чем ошибку.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class _Entry(Generic[V]):
    value: V
    stored_at: float
    ttl: float


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    stale_hits: int
    evictions: int
    size: int


class TTLCache(Generic[K, V]):
    """LRU-кеш с временем жизни записи и «мягким» сроком годности.

    :param maxsize: максимум записей, дальше вытесняется давно не используемая
    :param ttl: время, в течение которого запись считается свежей, в секундах
    :param stale_ttl: сколько ещё хранить протухшую запись для аварийной отдачи
    """

    def __init__(self, maxsize: int, ttl: float, stale_ttl: float = 0.0, name: str = "cache") -> None:
        if maxsize <= 0:
            raise ValueError("maxsize должен быть положительным")
        if ttl <= 0:
            raise ValueError("ttl должен быть положительным")
        self._maxsize = maxsize
        self._ttl = ttl
        self._stale_ttl = max(stale_ttl, ttl)
        self._name = name
        self._data: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0
        self._evictions = 0

    def get(self, key: K) -> V | None:
        """Возвращает значение, если оно ещё свежее."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.monotonic() - entry.stored_at > entry.ttl:
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return entry.value

    def get_stale(self, key: K) -> V | None:
        """Возвращает значение, даже если TTL истёк, но не старше `stale_ttl`."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if time.monotonic() - entry.stored_at > self._stale_ttl:
                del self._data[key]
                return None
            self._stale_hits += 1
            return entry.value

    def set(self, key: K, value: V, *, ttl: float | None = None) -> None:
        """Кладёт значение в кеш.

        :param ttl: срок жизни именно этой записи. Нужен, чтобы хранить
            неудачные ответы меньше обычного: «данных нет» может означать и
            сбой у провайдера, и такой ответ не должен залипать надолго.
        """
        with self._lock:
            self._data[key] = _Entry(
                value=value,
                stored_at=time.monotonic(),
                ttl=self._ttl if ttl is None else ttl,
            )
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)
                self._evictions += 1

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                stale_hits=self._stale_hits,
                evictions=self._evictions,
                size=len(self._data),
            )

    def log_stats(self) -> None:
        stats = self.stats()
        total = stats.hits + stats.misses
        ratio = (stats.hits / total * 100) if total else 0.0
        logger.info(
            "Кеш %s: %d записей, попаданий %d (%.1f%%), промахов %d, "
            "отдач устаревших %d, вытеснений %d",
            self._name,
            stats.size,
            stats.hits,
            ratio,
            stats.misses,
            stats.stale_hits,
            stats.evictions,
        )
