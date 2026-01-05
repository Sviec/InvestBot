from contextlib import contextmanager
from typing import Type, TypeVar, Generic, Optional

from db import get_db

ModelType = TypeVar('ModelType')


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    @contextmanager
    def _get_session(self):
        """Контекстный менеджер для сессии БД"""
        with get_db() as session:
            yield session

    def get_by_id(self, item_id: int) -> Optional[ModelType]:
        with self._get_session() as db:
            return db.query(self.model).filter(self.model.id == item_id).first()
