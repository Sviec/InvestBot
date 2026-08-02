"""Дерево меню и разбор путей навигации.

Меню читается из JSON один раз при старте и разбирается в неизменяемые
`MenuNode`: некорректный файл обнаруживается сразу, а не на нажатии кнопки
пользователем. Файл больше не открывается на каждый апдейт.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping

from app.core.errors import ConfigurationError, UnknownPathError
from app.data.config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)

MENU_DIR = PROJECT_ROOT / "app" / "data" / "menu"
FALLBACK_LANGUAGE = "ru"
SEGMENT_SEPARATOR = "%"
SUFFIX_SEPARATOR = "#"


@dataclass(frozen=True, slots=True)
class MenuNode:
    """Узел дерева меню."""

    key: str
    text: str
    button_text: str
    input_text: str | None = None
    url: str | None = None
    buttons: Mapping[str, "MenuNode"] = field(default_factory=lambda: MappingProxyType({}))

    def child(self, key: str) -> "MenuNode | None":
        return self.buttons.get(key)

    def walk(self) -> Iterator["MenuNode"]:
        yield self
        for node in self.buttons.values():
            yield from node.walk()


def _parse_node(key: str, raw: Any) -> MenuNode:
    """Разбирает узел меню, допуская сокращённую запись «ключ: подпись»."""
    if isinstance(raw, str):
        return MenuNode(key=key, text=raw, button_text=raw)
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Узел меню {key!r} должен быть объектом или строкой")

    children_raw = raw.get("buttons") or {}
    if not isinstance(children_raw, dict):
        raise ConfigurationError(f"Поле buttons узла {key!r} должно быть объектом")

    children = {
        child_key: _parse_node(child_key, child_raw)
        for child_key, child_raw in children_raw.items()
    }
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ConfigurationError(f"У узла меню {key!r} отсутствует непустое поле text")

    return MenuNode(
        key=key,
        text=text,
        button_text=raw.get("button_text") or text,
        input_text=raw.get("input_text"),
        url=raw.get("url"),
        buttons=MappingProxyType(children),
    )


def _read_menu_file(language: str) -> dict[str, MenuNode] | None:
    path = MENU_DIR / f"{language}.json"
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Файл меню %s недоступен: %s", path, exc)
        return None
    if not content:
        logger.warning("Файл меню %s пуст", path)
        return None
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("Файл меню %s содержит некорректный JSON: %s", path, exc)
        return None
    if not isinstance(raw, dict) or not raw:
        logger.error("Файл меню %s должен содержать непустой объект", path)
        return None
    return {key: _parse_node(key, value) for key, value in raw.items()}


@lru_cache(maxsize=4)
def load_menu(language: str) -> Mapping[str, MenuNode]:
    """Загружает дерево меню с откатом на язык по умолчанию."""
    menu = _read_menu_file(language)
    if menu is None and language != FALLBACK_LANGUAGE:
        logger.warning(
            "Меню для языка %r недоступно, использую %r", language, FALLBACK_LANGUAGE
        )
        menu = _read_menu_file(FALLBACK_LANGUAGE)
    if menu is None:
        raise ConfigurationError(
            f"Не удалось загрузить дерево меню из {MENU_DIR}. "
            "Проверьте наличие и корректность файла ru.json."
        )
    logger.info("Меню загружено (%s), корневых разделов: %d", language, len(menu))
    return MappingProxyType(menu)


def get_menu() -> Mapping[str, MenuNode]:
    return load_menu(get_settings().bot_language)


def is_dynamic_segment(segment: str) -> bool:
    """Сегмент вида `AAPL#tckr` — подставленное значение, а не узел меню."""
    return SUFFIX_SEPARATOR in segment


def resolve(path: str) -> MenuNode:
    """Находит узел меню по пути, пропуская подставленные значения.

    :raises UnknownPathError: если сегмент отсутствует в дереве
    """
    segments = [part for part in path.split(SEGMENT_SEPARATOR) if part]
    if not segments:
        raise UnknownPathError(path)

    menu = get_menu()
    root_key = segments[0]
    node = menu.get(root_key)
    if node is None:
        raise UnknownPathError(path)

    for segment in segments[1:]:
        if is_dynamic_segment(segment):
            continue
        child = node.child(segment)
        if child is None:
            raise UnknownPathError(path)
        node = child
    return node


def all_menu_keys(language: str = FALLBACK_LANGUAGE) -> tuple[str, ...]:
    """Все ключи узлов дерева — исходные данные для кодека путей."""
    keys: set[str] = set()
    for root_key, node in load_menu(language).items():
        keys.add(root_key)
        for child in node.walk():
            keys.add(child.key)
    return tuple(sorted(keys))
