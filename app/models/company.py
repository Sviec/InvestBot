"""Модель компании (справочник тикеров)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Уникальное ограничение уже создаёт индекс, по которому идёт поиск.
    ticker: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String, nullable=False)
    sector_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sector.id", ondelete="SET NULL"), nullable=True, index=True
    )
    industry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("industry.id", ondelete="SET NULL"), nullable=True, index=True
    )
    isin_telegram: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
