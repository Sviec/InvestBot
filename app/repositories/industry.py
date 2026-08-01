"""Репозиторий отраслей."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.industry import Industry
from app.repositories.base import BaseRepository
from app.repositories.dto import NamedItem


class IndustryRepository(BaseRepository[Industry]):
    def __init__(self) -> None:
        super().__init__(Industry)

    def list_by_sector(self, sector_id: int) -> list[NamedItem]:
        def _operation(session: Session) -> list[NamedItem]:
            rows = session.execute(
                select(Industry.id, Industry.name)
                .where(Industry.sector_id == sector_id)
                .order_by(Industry.name)
            ).all()
            return [NamedItem(id=row.id, name=row.name) for row in rows]

        return self._read(_operation, "list_by_sector")

    def get_key(self, industry_id: int) -> str | None:
        """Ключ отрасли у провайдера рыночных данных."""

        def _operation(session: Session) -> str | None:
            return session.execute(
                select(Industry.key).where(Industry.id == industry_id)
            ).scalar_one_or_none()

        return self._read(_operation, "get_key")

    def get_name(self, industry_id: int) -> str | None:
        def _operation(session: Session) -> str | None:
            return session.execute(
                select(Industry.name).where(Industry.id == industry_id)
            ).scalar_one_or_none()

        return self._read(_operation, "get_name")
