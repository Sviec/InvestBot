from sqlalchemy import Column, Integer, String

from app.models.base import Base


class Industry(Base):
    __tablename__ = "industry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    sector_id = Column(Integer, nullable=False)
