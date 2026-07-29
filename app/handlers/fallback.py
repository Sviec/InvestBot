"""Обработчики последней надежды.

Регистрируются последними. Сюда попадают нажатия кнопок из сообщений,
отправленных до изменения структуры меню: раньше такие апдейты оставляли
«часики» на кнопке навсегда.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.callbacks import NoopCallback
from app.keyboards.make_markup import main_menu_keyboard
from app.utils.messaging import safe_edit

logger = logging.getLogger(__name__)

router = Router(name="fallback")

OUTDATED = (
    "Это сообщение устарело — структура меню изменилась.\n"
    "Открываю главное меню."
)
UNKNOWN_MESSAGE = (
    "Я понимаю только команды и кнопки. Наберите /menu, чтобы открыть меню."
)


@router.callback_query(NoopCallback.filter())
async def noop(callback: CallbackQuery) -> None:
    """Индикатор страницы и неактивные стрелки листания."""
    await callback.answer()


@router.callback_query()
async def outdated_button(callback: CallbackQuery) -> None:
    logger.info("Не распознаны callback-данные: %r", callback.data)
    await safe_edit(callback, OUTDATED, main_menu_keyboard())


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer(UNKNOWN_MESSAGE, reply_markup=main_menu_keyboard())
