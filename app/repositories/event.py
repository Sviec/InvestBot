"""Репозиторий журнала действий пользователя."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import ColumnElement, delete, func, insert, select
from sqlalchemy.orm import Session

from app.models.event import UserEvent
from app.repositories.base import BaseRepository
from app.repositories.dto import CountedItem, UserActivityStats, UserEventInput

# Совпадают с длинами колонок: обрезка здесь, а не падение INSERT на длинном узле.
_KIND_MAX = 20
_NODE_MAX = 40
_TICKER_MAX = 15


class EventRepository(BaseRepository[UserEvent]):
    def __init__(self) -> None:
        super().__init__(UserEvent)

    def insert_many(self, events: Sequence[UserEventInput]) -> int:
        """Вставляет пачку событий одним executemany. Пустой список — no-op."""
        if not events:
            return 0

        rows = [
            {
                "user_id": event.user_id,
                "kind": event.kind[:_KIND_MAX],
                "node": event.node[:_NODE_MAX],
                "ticker": (
                    None
                    if event.ticker is None
                    else event.ticker.strip().upper()[:_TICKER_MAX] or None
                ),
            }
            for event in events
        ]

        def _operation(session: Session) -> int:
            # Список словарей → executemany: один round-trip вместо N insert.
            session.execute(insert(UserEvent), rows)
            return len(rows)

        return self._write(_operation, "insert_many")

    def user_stats(self, user_id: int, *, top_n: int = 10) -> UserActivityStats:
        """Топ тикеров и разделов, число активных дней, последняя активность."""

        def _operation(session: Session) -> UserActivityStats:
            top_tickers = _top_counts(
                session,
                user_id,
                UserEvent.ticker,
                top_n,
                require_not_null=True,
            )
            top_nodes = _top_counts(session, user_id, UserEvent.node, top_n)
            active_days = session.execute(
                select(func.count(func.distinct(func.date(UserEvent.created_at)))).where(
                    UserEvent.user_id == user_id
                )
            ).scalar_one()
            last_activity = session.execute(
                select(func.max(UserEvent.created_at)).where(
                    UserEvent.user_id == user_id
                )
            ).scalar_one_or_none()
            return UserActivityStats(
                top_tickers=tuple(top_tickers),
                top_nodes=tuple(top_nodes),
                active_days=int(active_days or 0),
                last_activity=last_activity,
            )

        return self._read(_operation, "user_stats")

    def purge_older_than(self, days: int) -> int:
        """Удаляет события старше `days` суток. Возвращает число удалённых строк."""
        if days < 1:
            raise ValueError("срок хранения должен быть не меньше 1 дня")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        def _operation(session: Session) -> int:
            result = session.execute(
                delete(UserEvent).where(UserEvent.created_at < cutoff)
            )
            return int(result.rowcount or 0)

        return self._write(_operation, "purge_older_than")


def _top_counts(
    session: Session,
    user_id: int,
    column: ColumnElement[str | None],
    top_n: int,
    *,
    require_not_null: bool = False,
) -> list[CountedItem]:
    query = (
        select(column, func.count().label("cnt"))
        .where(UserEvent.user_id == user_id)
        .group_by(column)
        .order_by(func.count().desc(), column.asc())
        .limit(top_n)
    )
    if require_not_null:
        query = query.where(column.is_not(None))
    rows = session.execute(query).all()
    return [CountedItem(key=str(row[0]), count=int(row[1])) for row in rows]
