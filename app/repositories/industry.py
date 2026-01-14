from typing import List, Optional, Dict, Any

from app.models.industry import Industry
from app.models.sector import Sector
from app.repositories.base import BaseRepository


class IndustryRepository(BaseRepository[Industry]):
    def __init__(self):
        super().__init__(Industry)

    def get_all(self) -> dict[Any, Any]:
        """Получить все отрасли"""
        with self._get_session() as db:
            return dict(db.query(Industry.id, Industry.name)
                        .order_by(Industry.name)
                        .all())

    def get_all_names(self) -> List[str]:
        """Получить все отрасли (только имена)"""
        with (self._get_session() as db):
            return db.scalars(db.query(Industry.name)
                              .order_by(Industry.name)
                              ).all()

    def get_by_name(self, name: str) -> Optional[Industry]:
        """Найти отрасль по имени"""
        with self._get_session() as db:
            return db.query(Industry) \
                .filter(Industry.name == name) \
                .first()

    def get_name_by_id(self, industry_id: int) -> str:
        """Найти отрасль по id"""
        with self._get_session() as db:
            return str(db.query(Industry.name)
                       .filter(Industry.id == industry_id)
                       .scalar())

    def get_key_by_id(self, industry_id: int) -> str:
        """Найти ключ отрасли по id"""
        with self._get_session() as db:
            return str(db.query(Industry.key)
                       .filter(Industry.id == industry_id)
                       .scalar())

    def get_all_by_sector_id(self, sector_id) -> dict[Any, Any]:
        """Получить все индустрии сектора по id сектора"""
        with self._get_session() as db:
            return dict(db.query(Industry.id, Industry.name)
                        .filter(Industry.sector_id == sector_id)
                        .all())

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
            return db.query(Sector.name) \
                    .join(Industry, Industry.sector_id == Sector.id) \
                    .filter(Industry.id == industry_id) \
                    .scalar()
