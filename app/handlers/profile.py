from aiogram import types, Router, F
from aiogram.fsm.state import StatesGroup, State

from callbacks import ProfileCallback
from app.keyboards.make_markup import build_markup
from app.utils.navigation import get_path

router = Router()


class ProfileStates(StatesGroup):
    waiting_ticker_input = State()


@router.callback_query(ProfileCallback.filter(F.path.endswith("profile")))
async def profile_menu(callback: types.CallbackQuery, callback_data: ProfileCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )
