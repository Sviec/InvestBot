from typing import List, Optional, Any

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    def __init__(self):
        super().__init__(Company)

    def get_all(self) -> dict:
        """Получить все компании"""
        with self._get_session() as db:
            return dict(db.query(Company)
                        .order_by(Company.name)
                        .all())

    def get_all_names(self) -> List[str]:
        """Получить все компании (только имена)"""
        with (self._get_session() as db):
            return db.scalars(db.query(Company.name)
                              .order_by(Company.name)
                              ).all()

    def get_by_name(self, name: str) -> Optional[Company]:
        """Найти компанию по имени"""
        with self._get_session() as db:
            return db.query(Company) \
                .filter(Company.name == name) \
                .first()

    def get_name_by_id(self, company_id: int) -> str:
        """Найти компанию по id"""
        with self._get_session() as db:
            return str(db.query(Company.name)
                       .filter(Company.id == company_id)
                       .scalar())

    def get_by_id(self, company_id: int) -> str:
        """Найти ключ компании по id"""
        with self._get_session() as db:
            return str(db.query(Company)
                       .filter(Company.id == company_id)
                       .scalar())
