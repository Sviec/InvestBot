from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.callbacks import AnalysisCallback
from app.entities.industry import Industry
from app.entities.sector import Sector
from app.keyboards.make_markup import build_markup, input_markup, build_dynamic_markup
from app.services.analysis_service import get_ticker
from app.utils.navigation import get_path
from app.repositories import repositories

router = Router()


class AnalysisStates(StatesGroup):
    waiting_ticker_input = State()


@router.callback_query(AnalysisCallback.filter(F.path.endswith("analysis")))
async def analysis_menu(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("company")))
async def request_ticker_input(callback: types.CallbackQuery, callback_data: AnalysisCallback, state: FSMContext):
    data = get_path(callback_data.path)
    await callback.message.edit_text(
        data['input_text'],
        reply_markup=input_markup(callback_data=callback_data).as_markup()
    )
    await state.set_state(AnalysisStates.waiting_ticker_input)
    await callback.answer()


@router.message(AnalysisStates.waiting_ticker_input)
async def process_ticker_input(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    ticker = await get_ticker(message.text.strip().upper())
    await state.clear()

    callback_path = state_data.get('callback_path', 'analysis-company')
    callback_data = AnalysisCallback(path=callback_path)

    data = get_path(callback_path)
    kb = build_markup(callback_data, data)

    await message.answer(
        text=data['text'] + f"{ticker.get_name()}",
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("c_common_info")))
async def common_info(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("c_graph")))
async def graph(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("c_additional_info")))
async def additional_info(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("c_fundamental_analysis")))
async def fundamental_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("c_tech_indicators")))
async def tech_indicators(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("c_multipliers")))
async def multipliers(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("sector")))
async def sector_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    sectors = repositories.sector.get_all_names()
    kb = build_dynamic_markup(callback_data, items=sectors, suffix='sctr')
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("#sctr")))
async def sector_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path('%'.join(callback_data.path.split('%')[:-1]))
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_industry")))
async def industry_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    industries = repositories.industry.get_all_names()
    kb = build_dynamic_markup(callback_data, items=industries, suffix='inds')
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("#inds")))
async def industry_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path('%'.join(callback_data.path.split('%')[:-1]))
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_overview")))
async def industry_overview(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry = Industry(callback_data.path.split('#inds')[0].split('%')[-1])
    await callback.message.edit_text(
        industry.get_overview(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_top_companies")))
async def industry_top_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry = Industry(callback_data.path.split('#inds')[0].split('%')[-1])
    await callback.message.edit_text(
        industry.get_top_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_top_growth_companies")))
async def sector_top_growth_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry = Industry(callback_data.path.split('#inds')[0].split('%')[-1])
    await callback.message.edit_text(
        industry.get_top_growth_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_top_performing_companies")))
async def industry_top_performing_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry = Industry(callback_data.path.split('#inds')[0].split('%')[-1])
    await callback.message.edit_text(
        industry.get_top_performing_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_overview")))
async def sector_overview(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sector = Sector(callback_data.path.split('#sctr')[0].split('%')[-1])
    print(sector.get_name())
    await callback.message.edit_text(
        sector.get_overview(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_top_companies")))
async def sector_top_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sector = Sector(callback_data.path.split('#sctr')[0].split('%')[-1])
    await callback.message.edit_text(
        sector.get_top_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_top_etfs")))
async def sector_top_etfs(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sector = Sector(callback_data.path.split('#sctr')[0].split('%')[-1])
    await callback.message.edit_text(
        sector.get_top_etfs(),
        reply_markup=callback.message.reply_markup
    )
