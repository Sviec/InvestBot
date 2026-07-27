"""Повтор синхронных операций с экспоненциальной задержкой.

Применяется к сетевым вызовам (yfinance) и к обращениям к БД. Задержка растёт
экспоненциально и содержит джиттер, чтобы одновременно отвалившиеся запросы
не пошли на повтор синхронно.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, ParamSpec, Sequence, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    budget: float | None = None,
    retry_on: Sequence[type[BaseException]] = (Exception,),
    give_up_on: Sequence[type[BaseException]] = (),
    description: str = "операция",
) -> T:
    """Вызывает `func`, повторяя при перечисленных исключениях.

    :param give_up_on: исключения, при которых повтор бессмысленен
        (например, «тикер не найден») — пробрасываются сразу
    :param budget: предельное время на все попытки. Ограничение нужно потому,
        что вызывающая сторона ждёт результат с таймаутом: без него зависший
        провайдер держал бы рабочий поток ещё долго после того, как ответ
        пользователю уже отправлен, и пул потоков быстро исчерпывался бы.
    """
    if attempts < 1:
        raise ValueError("attempts должен быть >= 1")

    deadline = None if budget is None else time.monotonic() + budget
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except give_up_on:
            raise
        except retry_on as exc:  # type: ignore[misc]
            last_error = exc
            if attempt == attempts:
                break
            delay = min(base_delay * 2 ** (attempt - 1), max_delay)
            delay *= 0.5 + random.random()  # джиттер 50–150%
            if deadline is not None and time.monotonic() + delay >= deadline:
                logger.warning(
                    "Время на «%s» исчерпано после попытки %d/%d (%s: %s)",
                    description,
                    attempt,
                    attempts,
                    type(exc).__name__,
                    exc,
                )
                raise exc
            logger.warning(
                "Попытка %d/%d для «%s» не удалась (%s: %s), повтор через %.2f с",
                attempt,
                attempts,
                description,
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)

    assert last_error is not None
    logger.error("Все %d попыток для «%s» исчерпаны", attempts, description)
    raise last_error


def with_retry(
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    budget: float | None = None,
    retry_on: Sequence[type[BaseException]] = (Exception,),
    give_up_on: Sequence[type[BaseException]] = (),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Декоратор-обёртка над :func:`retry_call`."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return retry_call(
                lambda: func(*args, **kwargs),
                attempts=attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                budget=budget,
                retry_on=retry_on,
                give_up_on=give_up_on,
                description=func.__qualname__,
            )

        return wrapper

    return decorator
