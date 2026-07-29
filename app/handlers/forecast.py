"""Раздел «Прогноз».

Модель прогнозирования ещё не реализована, поэтому раздел доводит пользователя
до выбора компании и честно сообщает о статусе, вместо того чтобы обрывать
навигацию на кнопке без обработчика.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.callbacks import TICKER_SUFFIX, ForecastCallback, Origin
from app.handlers.common import (
    db_call,
    has_value,
    node_for,
    node_is,
    required_ticker,
    show_items,
    show_menu,
    ticker_items,
)
from app.keyboards.make_markup import back_keyboard
from app.repositories import repositories
from app.states import TickerInput
from app.utils.messaging import safe_edit
from app.utils.text import escape

logger = logging.getLogger(__name__)

router = Router(name="forecast")

FORECAST_STUB = (
    "Компания: <b>{name}</b>\n\n"
    "Прогнозирование котировок ещё в разработке. "
    "Пока посмотрите отчётность и мультипликаторы в разделе «Анализ»."
)
EMPTY_FAVOURITES = (
    "В избранном пока пусто. Добавьте компанию через «Анализ» → «Компания»."
)


@router.callback_query(ForecastCallback.filter(node_is("forecast")))
async def forecast_menu(
    callback: CallbackQuery, callback_data: ForecastCallback
) -> None:
    await show_menu(callback, callback_data)


@router.callback_query(
    ForecastCallback.filter(node_is("manual") & ~has_value(TICKER_SUFFIX))
)
async def ask_for_ticker(
    callback: CallbackQuery, callback_data: ForecastCallback, state: FSMContext
) -> None:
    node = node_for(callback_data)
    await safe_edit(
        callback,
        escape(node.input_text or node.text),
        back_keyboard(callback_data),
    )
    await state.set_state(TickerInput.waiting)
    await state.update_data(origin=Origin.FORECAST.value)


@router.callback_query(
    ForecastCallback.filter(node_is("favorites") & ~has_value(TICKER_SUFFIX))
)
async def favourites_picker(
    callback: CallbackQuery, callback_data: ForecastCallback, user_id: int
) -> None:
    tickers = await db_call(
        repositories.favourites.list_tickers, user_id, description="список избранного"
    )
    await show_items(
        callback,
        callback_data,
        ticker_items(tickers),
        TICKER_SUFFIX,
        empty_text=EMPTY_FAVOURITES,
        columns=3,
    )


@router.callback_query(
    ForecastCallback.filter(node_is("manual", "favorites") & has_value(TICKER_SUFFIX))
)
async def forecast_placeholder(
    callback: CallbackQuery, callback_data: ForecastCallback
) -> None:
    ticker = required_ticker(callback_data)
    await safe_edit(
        callback,
        FORECAST_STUB.format(name=escape(ticker)),
        back_keyboard(callback_data),
    )
