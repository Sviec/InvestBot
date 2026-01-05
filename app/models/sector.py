from sqlalchemy import Column, Integer, String

from app.models.base import Base


class Sector(Base):
    __tablename__ = "sector"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
