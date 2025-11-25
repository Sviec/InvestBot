from aiogram import types, Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup

from app.data.callbacks import AnalysisCallback
from app.keyboards.make_markup import build_markup
from app.utils.navigation import get_path

router = Router()


class AnalysisStates(StatesGroup):
    waiting_ticker_input = State()


@router.callback_query(AnalysisCallback.filter(F.path.endswith("analysis")))
async def analysis_menu(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback, callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("sector")))
async def select_sector(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sectors = ["IT", "Energy", "Finance"]
    kb = build_markup(callback, callback_data, sectors)
    await callback.message.edit_text(
        "Выберите сектор",
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.action == "select_sector"))
async def show_sector_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback, callback_data, data[0], data[1])
    kb.add(callback_data.get_back_button())
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[callback_data.get_back_button()]]
        )
    )
