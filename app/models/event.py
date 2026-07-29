"""Модель журнала действий пользователя."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserEvent(Base):
    """Одно действие в интерфейсе бота.

    Без `updated_at`: событие иммутабельно после вставки. Длины `kind` / `node`
    / `ticker` совпадают с миграцией — обрезка на стороне записи, а не схема.
    """

    __tablename__ = "user_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    node: Mapped[str] = mapped_column(String(40), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(15), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
