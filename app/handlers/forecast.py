from aiogram import Router, types, F
from aiogram.fsm.state import StatesGroup, State

from callbacks import ForecastCallback
from app.keyboards.make_markup import build_markup
from app.utils.navigation import get_path


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

