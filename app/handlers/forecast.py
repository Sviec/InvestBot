from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from callbacks import ForecastCallback
from app.keyboards.make_markup import build_markup, input_markup, build_dynamic_markup
from app.utils.navigation import get_path
from app.repositories import repositories

router = Router()


class ForecastStates(StatesGroup):
    waiting_ticker_input = State()


@router.callback_query(ForecastCallback.filter(F.path.endswith("forecast")))
async def forecast_menu(callback: types.CallbackQuery, callback_data: ForecastCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(ForecastCallback.filter(F.path.endswith("manual")))
async def request_ticker_input(callback: types.CallbackQuery, callback_data: ForecastCallback, state: FSMContext):
    data = get_path(callback_data.path)
    await callback.message.edit_text(
        data['input_text'],
        reply_markup=input_markup(callback_data=callback_data).as_markup()
    )
    await state.update_data(callback_path=callback_data.path)
    await state.set_state(ForecastStates.waiting_ticker_input)
    await callback.answer()


@router.callback_query(ForecastCallback.filter(F.path.endswith("favorites")))
async def get_ticker_from_favourites(callback: types.CallbackQuery, callback_data: ForecastCallback):
    data = get_path(callback_data.path)
    user_id = callback.from_user.id
    tickers = repositories.favourites.get_all_tickers(user_id)
    kb = build_dynamic_markup(callback_data, items=tickers, suffix='tckr')
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


