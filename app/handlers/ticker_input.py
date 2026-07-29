"""Обработка тикера, введённого вручную.

Ввод един для «Анализа» и «Прогноза»: раздел-источник читается из данных
состояния. Тикер проверяется дважды — сначала по шаблону, затем по факту
существования у провайдера, чтобы пользователь узнал об опечатке сразу.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.callbacks import CompanyCallback, ForecastCallback, Origin
from app.core.errors import NoDataError
from app.entities.company import Company
from app.handlers.common import TICKER_PROGRESS, market_call
from app.handlers.company import company_name, send_company_card
from app.handlers.forecast import FORECAST_STUB
from app.keyboards.make_markup import back_keyboard
from app.states import TickerInput
from app.utils.messaging import delete_silently
from app.utils.text import escape
from app.utils.validators import normalize_ticker

logger = logging.getLogger(__name__)

router = Router(name="ticker_input")

WRONG_INPUT_TYPE = "Пришлите тикер текстом, например AAPL."


def _origin(raw: object) -> Origin:
    try:
        return Origin(str(raw))
    except ValueError:
        logger.warning("В состоянии некорректный раздел-источник: %r", raw)
        return Origin.ANALYSIS


@router.message(TickerInput.waiting, F.text)
async def process_ticker(message: Message, state: FSMContext) -> None:
    ticker = normalize_ticker(message.text)
    company = Company(ticker)
    # Индикатор вместо «часиков» на кнопке: здесь событие — сообщение, не callback.
    status = await message.answer(TICKER_PROGRESS)
    try:
        # Имя берём из БД, но существование тикера по-прежнему проверяем
        # у провайдера: иначе опечатка всплыла бы только на следующем экране.
        try:
            await market_call(
                lambda: company.info, description=f"проверка {company.ticker}"
            )
        except NoDataError:
            # Профиль пуст, но бумагу провайдер подтвердил: пускаем в карточку,
            # графики и отчёты по ней работают. Отказ здесь означал бы, что
            # существующий тикер невозможно открыть.
            logger.info("Открываю %s без профиля провайдера", company.ticker)
        name = await company_name(company)

        data = await state.get_data()
        origin = _origin(data.get("origin", Origin.ANALYSIS.value))
        await state.clear()

        if origin is Origin.FORECAST:
            callback_data = ForecastCallback(path=f"forecast%manual%{ticker}#tckr")
            await message.answer(
                FORECAST_STUB.format(name=escape(name)),
                reply_markup=back_keyboard(callback_data),
            )
            return

        callback_data = CompanyCallback(
            come_through=origin, path=f"company%{ticker}#tckr"
        )
        await send_company_card(message, callback_data, name)
    finally:
        await delete_silently(status)


@router.message(TickerInput.waiting)
async def wrong_input_type(message: Message) -> None:
    await message.answer(WRONG_INPUT_TYPE)
