from typing import List, Optional

from app.models.industry import Industry
from app.models.sector import Sector
from app.repositories.base import BaseRepository


class IndustryRepository(BaseRepository[Industry]):
    def __init__(self):
        super().__init__(Industry)

    def get_all(self) -> List[Industry]:
        """Получить все отрасли"""
        with self._get_session() as db:
            return db.query(Industry) \
                .order_by(Industry.name) \
                .all()

    def get_all_names(self) -> List[str]:
        """Получить все отрасли (только имена)"""
        with self._get_session() as db:
            return db.query(Industry.name) \
                .order_by(Industry.name) \
                .scalars() \
                .all()

    def get_by_name(self, name: str) -> Optional[Industry]:
        """Найти отрасль по имени"""
        with self._get_session() as db:
            return db.query(Industry) \
                .filter(Industry.name == name) \
                .first()

    def get_by_id(self, industry_id: int) -> Optional[Industry]:
        """Найти отрасль по id"""
        with self._get_session() as db:
            return db.query(Industry) \
                .filter(Industry.id == industry_id) \
                .first()

    def get_sector_id(self, industry_id: int) -> Optional[int]:
        """Получить id сектора по id индустрии"""
        with self._get_session() as db:
            result = db.query(Industry.sector_id) \
                .filter(Industry.id == industry_id) \
                .scalar()
            return result

    def get_sector_name(self, industry_id: int) -> Optional[str]:
        """Получить имя сектора по id индустрии"""
        with self._get_session() as db:
            result = db.query(Sector.name) \
                .join(Industry, Industry.sector_id == Sector.id) \
                .filter(Industry.id == industry_id) \
                .scalar()
            return result
    