from aiogram import Router, F, types
from aiogram.fsm.state import StatesGroup, State

from app.data.callbacks import ReferenceCallback
from app.keyboards.make_markup import build_markup
from app.utils.navigation import get_path

router = Router()


class ProfileStates(StatesGroup):
    waiting_ticker_input = State()


@router.callback_query(ReferenceCallback.filter(F.path.endswith("reference")))
async def reference_menu(callback: types.CallbackQuery, callback_data: ReferenceCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback, callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )
