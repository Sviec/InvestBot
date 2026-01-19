from app.repositories.company import CompanyRepository
from app.repositories.favourites import FavouritesRepository
from app.repositories.sector import SectorRepository
from app.repositories.industry import IndustryRepository
from app.repositories.user import UserRepository


class Repositories:
    """Контейнер для всех репозиториев"""
    def __init__(self):
        self.favourites = FavouritesRepository()
        self.user = UserRepository()
        self.company = CompanyRepository()
        self.sector = SectorRepository()
        self.industry = IndustryRepository()


repositories = Repositories()