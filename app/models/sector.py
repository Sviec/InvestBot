"""Модель сектора экономики."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Sector(TimestampMixin, Base):
    __tablename__ = "sector"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # Ключ, под которым сектор известен провайдеру рыночных данных.
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
