from sqlalchemy import Column, Integer, Float, DateTime, Boolean, String

from app.models.base import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))