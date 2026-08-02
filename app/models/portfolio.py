"""Модель журнала сделок портфеля."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PortfolioTransaction(TimestampMixin, Base):
    __tablename__ = "portfolio_transaction"
    __table_args__ = (
        # Сторона сделки — только покупка или продажа; иначе агрегация позиций
        # не знает, как интерпретировать строку.
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_portfolio_transaction_side"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # Тикер обязан быть в справочнике: через company доступны сектор и отрасль.
    company_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'USD'")
    )
    traded_at: Mapped[date] = mapped_column(Date, nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
