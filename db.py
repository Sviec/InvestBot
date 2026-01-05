from pydantic_settings import SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from app.data.config import config
from app.models.base import Base


DATABASE_URL = config.database_url
print(f"Подключаемся к БД: {config.db_host}:{config.db_port}/{config.db_name}")

# Создаем движок
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

# Фабрика сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


@contextmanager
def get_db():
    """Контекстный менеджер для работы с БД"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


# Функция для создания всех таблиц
def create_all_tables():
    """Создает все таблицы из моделей"""
    Base.metadata.create_all(bind=engine)
    print("Все таблицы созданы")