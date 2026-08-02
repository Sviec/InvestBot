"""Компактное представление пути навигации в callback_data.

Telegram ограничивает `callback_data` 64 байтами. Читаемый путь вида
`company%AAPL#tckr%c_fa%fa_fin%fin_quarter` вместе с префиксом занимает под
60 байт и ломается при добавлении ещё одного уровня меню, причём молча.

Кодек заменяет имена узлов короткими псевдонимами. Псевдоним считается от
хеша имени, а не от порядкового номера: добавление нового пункта меню не
сдвигает псевдонимы остальных, поэтому кнопки в старых сообщениях продолжают
работать после деплоя.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache

from app.core.errors import NavigationError
from app.utils.navigation import (
    FALLBACK_LANGUAGE,
    SEGMENT_SEPARATOR,
    SUFFIX_SEPARATOR,
    all_menu_keys,
)

logger = logging.getLogger(__name__)

ALIAS_LENGTH = 4
MAX_ALIAS_LENGTH = 12
LITERAL_PREFIX = "~"
_BASE36_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

# Суффиксы подставленных значений: тикер, сектор, отрасль, номер страницы.
SUFFIX_ALIASES = {"tckr": "t", "sctr": "s", "inds": "i", "pg": "p"}
SUFFIX_NAMES = {alias: name for name, alias in SUFFIX_ALIASES.items()}


def _base36(value: int) -> str:
    if value == 0:
        return "0"
    digits: list[str] = []
    while value:
        value, remainder = divmod(value, 36)
        digits.append(_BASE36_DIGITS[remainder])
    return "".join(reversed(digits))


def _alias(key: str, length: int) -> str:
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=16).digest()
    return _base36(int.from_bytes(digest, "big"))[:length]


@lru_cache(maxsize=4)
def _tables(language: str) -> tuple[dict[str, str], dict[str, str]]:
    """Строит таблицы «имя → псевдоним» и обратную, разрешая коллизии."""
    keys = all_menu_keys(language)
    length = ALIAS_LENGTH
    pending = list(keys)
    forward: dict[str, str] = {}

    while pending and length <= MAX_ALIAS_LENGTH:
        candidates: dict[str, list[str]] = {}
        for key in pending:
            candidates.setdefault(_alias(key, length), []).append(key)

        collided: list[str] = []
        for alias, owners in candidates.items():
            if len(owners) == 1 and alias not in forward.values():
                forward[owners[0]] = alias
            else:
                collided.extend(owners)
        pending = sorted(collided)
        length += 1

    if pending:
        raise NavigationError(
            f"Не удалось построить уникальные псевдонимы для ключей меню: {pending}"
        )

    backward = {alias: key for key, alias in forward.items()}
    return forward, backward


def encode_path(path: str) -> str:
    """Сжимает читаемый путь для передачи в callback_data."""
    if not path:
        return path
    forward, _ = _tables(FALLBACK_LANGUAGE)
    encoded: list[str] = []
    for segment in path.split(SEGMENT_SEPARATOR):
        if not segment:
            continue
        if SUFFIX_SEPARATOR in segment:
            value, _, suffix = segment.rpartition(SUFFIX_SEPARATOR)
            encoded.append(f"{value}{SUFFIX_SEPARATOR}{SUFFIX_ALIASES.get(suffix, suffix)}")
            continue
        alias = forward.get(segment)
        if alias is None:
            # Узел не из дерева меню: передаём как есть, помечая маркером.
            logger.debug("Сегмент %r отсутствует в дереве меню, кодирую дословно", segment)
            encoded.append(f"{LITERAL_PREFIX}{segment}")
            continue
        encoded.append(alias)
    return SEGMENT_SEPARATOR.join(encoded)


def decode_path(path: str) -> str:
    """Восстанавливает читаемый путь из callback_data.

    :raises NavigationError: если псевдоним неизвестен — так бывает с кнопками
        из сообщений, отправленных до изменения структуры меню
    """
    if not path:
        return path
    _, backward = _tables(FALLBACK_LANGUAGE)
    decoded: list[str] = []
    for segment in path.split(SEGMENT_SEPARATOR):
        if not segment:
            continue
        if SUFFIX_SEPARATOR in segment:
            value, _, alias = segment.rpartition(SUFFIX_SEPARATOR)
            decoded.append(f"{value}{SUFFIX_SEPARATOR}{SUFFIX_NAMES.get(alias, alias)}")
            continue
        if segment.startswith(LITERAL_PREFIX):
            decoded.append(segment[len(LITERAL_PREFIX) :])
            continue
        key = backward.get(segment)
        if key is None:
            raise NavigationError(f"Неизвестный псевдоним пути: {segment!r}")
        decoded.append(key)
    return SEGMENT_SEPARATOR.join(decoded)
