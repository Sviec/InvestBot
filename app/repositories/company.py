"""Репозиторий справочника компаний."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.base import BaseRepository
from app.repositories.dto import CompanyDTO, NamedItem

logger = logging.getLogger(__name__)


def _to_dto(row: Company) -> CompanyDTO:
    return CompanyDTO(
        id=row.id,
        name=row.name,
        ticker=row.ticker,
        country=row.country,
        sector_id=row.sector_id,
        industry_id=row.industry_id,
    )


class CompanyRepository(BaseRepository[Company]):
    def __init__(self) -> None:
        super().__init__(Company)

    def get_by_ticker(self, ticker: str) -> CompanyDTO | None:
        """Находит компанию по тикеру без учёта регистра."""
        normalized = ticker.strip().upper()

        def _operation(session: Session) -> CompanyDTO | None:
            row = session.execute(
                select(Company).where(Company.ticker == normalized)
            ).scalar_one_or_none()
            return _to_dto(row) if row is not None else None

        return self._read(_operation, "get_by_ticker")

    def get_by_id(self, company_id: int) -> CompanyDTO | None:
        def _operation(session: Session) -> CompanyDTO | None:
            row = session.get(Company, company_id)
            return _to_dto(row) if row is not None else None

        return self._read(_operation, "get_by_id")

    def list_all(self, limit: int = 500) -> list[NamedItem]:
        def _operation(session: Session) -> list[NamedItem]:
            rows = session.execute(
                select(Company.id, Company.name).order_by(Company.name).limit(limit)
            ).all()
            return [NamedItem(id=row.id, name=row.name) for row in rows]

        return self._read(_operation, "list_all")
