"""Репозитории и их общий контейнер."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.repositories.company import CompanyRepository
from app.repositories.event import EventRepository
from app.repositories.favourites import FavouritesRepository
from app.repositories.industry import IndustryRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.sector import SectorRepository
from app.repositories.user import UserRepository


@dataclass(frozen=True)
class Repositories:
    """Точка доступа ко всем репозиториям.

    Репозитории не держат состояния и сессий, поэтому единственный экземпляр
    безопасно использовать из нескольких рабочих потоков.
    """

    company: CompanyRepository = field(default_factory=CompanyRepository)
    event: EventRepository = field(default_factory=EventRepository)
    favourites: FavouritesRepository = field(default_factory=FavouritesRepository)
    industry: IndustryRepository = field(default_factory=IndustryRepository)
    portfolio: PortfolioRepository = field(default_factory=PortfolioRepository)
    sector: SectorRepository = field(default_factory=SectorRepository)
    user: UserRepository = field(default_factory=UserRepository)


repositories = Repositories()

__all__ = ["Repositories", "repositories"]
