"""Модель отрасли внутри сектора."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Industry(TimestampMixin, Base):
    __tablename__ = "industry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sector_id: Mapped[int] = mapped_column(
        ForeignKey("sector.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Ключ, под которым отрасль известна провайдеру рыночных данных.
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
