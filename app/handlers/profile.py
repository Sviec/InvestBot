from aiogram import types, Router, F
from aiogram.fsm.state import StatesGroup, State

from callbacks import ProfileCallback, CompanyCallback
from app.keyboards.make_markup import build_markup, build_dynamic_markup
from app.utils.navigation import get_path
from app.repositories import repositories

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


@router.callback_query(ProfileCallback.filter(F.path.endswith("portfolio")))
async def portfolio(callback: types.CallbackQuery, callback_data: ProfileCallback):
    await callback.answer(f"Данный функионал в разработке", show_alert=False)


@router.callback_query(ProfileCallback.filter(F.path.endswith("stats")))
async def stats(callback: types.CallbackQuery, callback_data: ProfileCallback):
    await callback.answer(f"Данный функионал в разработке", show_alert=False)


@router.callback_query(ProfileCallback.filter(F.path.endswith("favourites")))
async def favourites(callback: types.CallbackQuery, callback_data: ProfileCallback):
    data = get_path(callback_data.path)
    user_id = callback.from_user.id

    tickers = repositories.favourites.get_all_tickers(user_id)
    kb = build_dynamic_markup(CompanyCallback(come_through='profile', path='company'), items=tickers, suffix='tckr')

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )
