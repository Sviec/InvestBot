from typing import Optional

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_user_id_telegram_id(self, telegram_id: int) -> int:
        """Найти пользователя по telegram_id"""
        with self._get_session() as db:
            return int(db.query(User.id)
                       .filter(User.telegram_user_id == telegram_id)
                       .scalar())

    def create_user(self, telegram_id: int, username: Optional[str] = None) -> None:
        """Создать или обновить пользователя"""
        with self._get_session() as db:
            user = db.query(User) \
                .filter(User.telegram_user_id == telegram_id) \
                .first()

            if user:
                if username and user.username != username:
                    user.username = username
                    db.commit()
                    db.refresh(user)
                return user

            new_user = User(
                telegram_user_id=telegram_id,
                username=username
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

    def exists(self, telegram_id: int) -> bool:
        """Проверить, существует ли пользователь"""
        with self._get_session() as db:
            count = db.query(User) \
                .filter(User.telegram_user_id == telegram_id) \
                .count()
            return count > 0