from sqlalchemy import Column, Integer

from app.models.base import Base


class Favourites(Base):
    __tablename__ = "favourites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=False, nullable=False)
    company_id = Column(Integer, unique=False, nullable=False)
