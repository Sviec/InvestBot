"""Главное меню и базовые команды."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.callbacks import MainMenuCallback
from app.handlers.common import node_is
from app.keyboards.make_markup import main_menu_keyboard
from app.utils.i18n import t
from app.utils.messaging import safe_edit, send_text

logger = logging.getLogger(__name__)

router = Router(name="main_menu")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_text(message, t("handlers.welcome"))
    await message.answer(t("handlers.menu_prompt"), reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("handlers.menu_prompt"), reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("handlers.cancelled"), reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await send_text(message, t("handlers.welcome"))


@router.callback_query(MainMenuCallback.filter(node_is("main_menu")))
async def main_menu_screen(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback, t("handlers.menu_prompt"), main_menu_keyboard())
