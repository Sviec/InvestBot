from sqlalchemy import Column, Integer, Float, DateTime, Boolean, String, ARRAY, VARCHAR

from app.models.base import Base


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=False, nullable=False)  # Company name
    ticker = Column(String, unique=False, nullable=False)
    country = Column(String, nullable=False)
    sector = Column(String)
    industry = Column(String)
    isin_telegram = Column(Boolean, nullable=False)