user_favorites = {}


def add_favorite(user_id: int, ticker: str):
    if user_id not in user_favorites:
        user_favorites[user_id] = set()
    user_favorites[user_id].add(ticker)


def remove_favorite(user_id: int, ticker: str):
    if user_id in user_favorites:
        user_favorites[user_id].discard(ticker)


def is_favorite(user_id: int, ticker: str) -> bool:
    return ticker in user_favorites.get(user_id, set())


def list_favorites(user_id: int):
    return list(user_favorites.get(user_id, set()))
