from typing import List, Any

from app.models.company import Company
from app.models.favourites import Favourites
from app.models.user import User
from app.repositories.base import BaseRepository


class FavouritesRepository(BaseRepository[Favourites]):
    def __init__(self):
        super().__init__(Favourites)

    def get_all_tickers(self, user_id) -> dict[str, str]:
        """Получить все тикеры"""
        with self._get_session() as db:
            return dict(db.query(Company.ticker, Company.ticker)
                        .join(Favourites, Favourites.company_id == Company.id) \
                        .join(User, User.id == Favourites.user_id)
                        .filter(User.telegram_user_id == user_id)
                        .all())

    def add_favourite(self, user_id: int, ticker: str) -> bool:
        """Добавить компанию в избранное по тикеру"""
        with self._get_session() as db:
            company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
            if not company:
                return False

            favourite = Favourites(
                user_id=user_id,
                company_id=company.id
            )
            db.add(favourite)
            db.commit()
            return True

    def remove_favourite(self, user_id: int, company_id: int) -> bool:
        """Удалить компанию из избранного"""
        with self._get_session() as db:
            deleted = db.query(Favourites) \
                .filter(
                Favourites.user_id == user_id,
                Favourites.company_id == company_id
            ) \
                .delete()
            db.commit()
            return deleted > 0

    def get_user_favourites(self, user_id: int) -> List[int]:
        """Получить список ID избранных компаний пользователя"""
        with self._get_session() as db:
            results = db.query(Favourites.company_id) \
                .filter(Favourites.user_id == user_id) \
                .all()
            return [company_id for (company_id,) in results]

    def is_favourite(self, user_id: int, company_id: int) -> bool:
        """Проверить, находится ли компания в избранном у пользователя"""
        with self._get_session() as db:
            count = db.query(Favourites) \
                .filter(
                Favourites.user_id == user_id,
                Favourites.company_id == company_id
            ) \
                .count()
            return count > 0