from sqlalchemy import Column, Integer, Float, DateTime, Boolean, String

from app.models.base import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False)  # Telegram ID
    username = Column(String(100))  # Username