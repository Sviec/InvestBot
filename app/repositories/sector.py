from typing import List, Optional, Dict, Any

from app.models.sector import Sector
from app.repositories.base import BaseRepository


class SectorRepository(BaseRepository[Sector]):
    def __init__(self):
        super().__init__(Sector)

    def get_all(self) -> dict[Any, Any]:
        """Получить все секторы"""
        with self._get_session() as db:
            return dict(db.query(Sector.id, Sector.name)
                        .order_by(Sector.name)
                        .all())

    def get_all_names(self) -> List[str]:
        """Получить все секторы (только имена)"""
        with self._get_session() as db:
            return db.scalars(db.query(Sector.name).order_by(Sector.name)).all()

    def get_by_name(self, name: str) -> Optional[Sector]:
        """Найти сектор по имени"""
        with self._get_session() as db:
            return db.query(Sector) \
                .filter(Sector.name == name) \
                .first()

    def get_by_id(self, sector_id: int) -> Optional[Sector]:
        """Найти сектор по id"""
        with self._get_session() as db:
            return db.query(Sector) \
                .filter(Sector.id == sector_id) \
                .first().scalar()

    def get_name_by_id(self, sector_id: int) -> str:
        """Найти сектор по id"""
        with self._get_session() as db:
            return str(db.query(Sector.name)
                       .filter(Sector.id == sector_id)
                       .scalar())

