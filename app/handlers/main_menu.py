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
from app.utils.messaging import safe_edit, send_text

logger = logging.getLogger(__name__)

router = Router(name="main_menu")

WELCOME = (
    "Привет! Я телеграм-бот, который помогает разобраться в инвестициях.\n\n"
    "Вот что я умею:\n"
    "• показывать график котировок компании;\n"
    "• считать основные мультипликаторы;\n"
    "• присылать финансовую, балансовую отчётность и денежный поток;\n"
    "• показывать обзоры секторов и отраслей;\n"
    "• вести список избранных компаний.\n\n"
    "Если непонятно, что означает конкретный мультипликатор, "
    'загляните в раздел «Справка».'
)
MENU_PROMPT = "Выберите действие"
CANCELLED = "Отменил. Возвращаю в главное меню."


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_text(message, WELCOME)
    await message.answer(MENU_PROMPT, reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(MENU_PROMPT, reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(CANCELLED, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await send_text(message, WELCOME)


@router.callback_query(MainMenuCallback.filter(node_is("main_menu")))
async def main_menu_screen(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback, MENU_PROMPT, main_menu_keyboard())
