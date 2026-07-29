"""Сборка инлайн-клавиатур.

Раньше здесь было три почти одинаковых функции, различавшихся только тем,
что подставляется в путь, и каждая содержала ветку `isinstance(..., CompanyCallback)`.
Теперь дочерний callback умеет строить себя сам (`BaseCallback.child`), поэтому
остался один генератор кнопок.
"""

from __future__ import annotations

import logging
import math
from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import (
    AnalysisCallback,
    BaseCallback,
    ForecastCallback,
    MainMenuCallback,
    NoopCallback,
    ProfileCallback,
    ReferenceCallback,
)
from app.utils.navigation import MenuNode

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 12
PREVIOUS_PAGE_TEXT = "◀"
NEXT_PAGE_TEXT = "▶"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Корневое меню. Единственная клавиатура, собираемая вручную."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Прогноз", callback_data=ForecastCallback(path="forecast"))
    builder.button(text="Анализ", callback_data=AnalysisCallback(path="analysis"))
    builder.button(text="Профиль", callback_data=ProfileCallback(path="profile"))
    builder.button(text="Справка", callback_data=ReferenceCallback(path="reference"))
    builder.adjust(1)
    return builder.as_markup()


def menu_keyboard(
    callback_data: BaseCallback,
    node: MenuNode,
    *,
    columns: int = 1,
    with_back: bool = True,
) -> InlineKeyboardMarkup:
    """Клавиатура из дочерних пунктов узла меню."""
    builder = InlineKeyboardBuilder()
    for key, child in node.buttons.items():
        if child.url:
            builder.add(InlineKeyboardButton(text=child.button_text, url=child.url))
            continue
        builder.add(
            InlineKeyboardButton(
                text=child.button_text,
                callback_data=callback_data.child(key).pack(),
            )
        )
    builder.adjust(columns)
    if with_back:
        builder.row(callback_data.back_button())
    return builder.as_markup()


def items_keyboard(
    callback_data: BaseCallback,
    items: Sequence[tuple[str, str]],
    suffix: str,
    *,
    target: BaseCallback | None = None,
    page: int = 0,
    columns: int = 2,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> InlineKeyboardMarkup:
    """Клавиатура из динамического списка с постраничной навигацией.

    :param items: пары «значение для пути — подпись кнопки»
    :param suffix: метка значения в пути (`tckr`, `sctr`, `inds`)
    :param target: куда ведут кнопки списка, если это не текущий раздел;
        листание при этом остаётся на текущем пути и сохраняет заголовок экрана
    """
    base = callback_data.strip_page()
    item_base = target if target is not None else base
    builder = InlineKeyboardBuilder()

    total_pages = max(1, math.ceil(len(items) / page_size))
    current_page = min(max(page, 0), total_pages - 1)
    window = items[current_page * page_size : (current_page + 1) * page_size]

    for value, label in window:
        builder.add(
            InlineKeyboardButton(
                text=label,
                callback_data=item_base.with_value(value, suffix).pack(),
            )
        )
    builder.adjust(columns)

    if total_pages > 1:
        navigation = [
            InlineKeyboardButton(
                text=PREVIOUS_PAGE_TEXT,
                callback_data=(
                    base.with_page(current_page - 1).pack()
                    if current_page > 0
                    else NoopCallback().pack()
                ),
            ),
            InlineKeyboardButton(
                text=f"{current_page + 1}/{total_pages}",
                callback_data=NoopCallback().pack(),
            ),
            InlineKeyboardButton(
                text=NEXT_PAGE_TEXT,
                callback_data=(
                    base.with_page(current_page + 1).pack()
                    if current_page < total_pages - 1
                    else NoopCallback().pack()
                ),
            ),
        ]
        builder.row(*navigation)

    builder.row(base.back_button())
    return builder.as_markup()


def back_keyboard(callback_data: BaseCallback) -> InlineKeyboardMarkup:
    """Клавиатура с единственной кнопкой «Назад»."""
    builder = InlineKeyboardBuilder()
    builder.row(callback_data.back_button())
    return builder.as_markup()


def to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Аварийная клавиатура: возврат в главное меню."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="В главное меню", callback_data=MainMenuCallback(path="main_menu")
    )
    return builder.as_markup()
