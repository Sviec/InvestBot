"""Репозиторий секторов."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sector import Sector
from app.repositories.base import BaseRepository
from app.repositories.dto import NamedItem


class SectorRepository(BaseRepository[Sector]):
    def __init__(self) -> None:
        super().__init__(Sector)

    def list_all(self) -> list[NamedItem]:
        def _operation(session: Session) -> list[NamedItem]:
            rows = session.execute(
                select(Sector.id, Sector.name).order_by(Sector.name)
            ).all()
            return [NamedItem(id=row.id, name=row.name) for row in rows]

        return self._read(_operation, "list_all")

    def get_key(self, sector_id: int) -> str | None:
        """Ключ сектора у провайдера рыночных данных."""

        def _operation(session: Session) -> str | None:
            return session.execute(
                select(Sector.key).where(Sector.id == sector_id)
            ).scalar_one_or_none()

        return self._read(_operation, "get_key")

    def get_name(self, sector_id: int) -> str | None:
        def _operation(session: Session) -> str | None:
            return session.execute(
                select(Sector.name).where(Sector.id == sector_id)
            ).scalar_one_or_none()

        return self._read(_operation, "get_name")
