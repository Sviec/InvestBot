"""ORM-модели.

Импорт всех моделей здесь обязателен: Alembic и `Base.metadata.create_all`
видят только те таблицы, чьи классы уже загружены.
"""

from app.models.base import Base, TimestampMixin
from app.models.company import Company
from app.models.event import UserEvent
from app.models.favourites import Favourites
from app.models.industry import Industry
from app.models.portfolio import PortfolioTransaction
from app.models.sector import Sector
from app.models.user import User

__all__ = [
    "Base",
    "Company",
    "Favourites",
    "Industry",
    "PortfolioTransaction",
    "Sector",
    "TimestampMixin",
    "User",
    "UserEvent",
]
