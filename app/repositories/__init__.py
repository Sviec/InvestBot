from app.repositories.sector import SectorRepository
from app.repositories.industry import IndustryRepository


class Repositories:
    """Контейнер для всех репозиториев"""
    def __init__(self):
        # self.favourites = FavouritesRepository()
        # self.user = UserRepository()
        # self.company = CompanyRepository()
        self.sector = SectorRepository()
        self.industry = IndustryRepository()


repositories = Repositories()