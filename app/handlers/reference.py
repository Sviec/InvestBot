"""Раздел «Справка»: ссылки на внешние материалы."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery

from app.callbacks import ReferenceCallback
from app.handlers.common import node_is, show_menu

router = Router(name="reference")


@router.callback_query(ReferenceCallback.filter(node_is("reference")))
async def reference_menu(
    callback: CallbackQuery, callback_data: ReferenceCallback
) -> None:
    await show_menu(callback, callback_data)
