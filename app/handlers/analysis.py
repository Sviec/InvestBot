from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from callbacks import AnalysisCallback
from app.entities.industry import Industry
from app.entities.sector import Sector
from app.keyboards.make_markup import build_markup, input_markup, build_dynamic_markup
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
async def company_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("input_ticker")))
async def request_ticker_input(callback: types.CallbackQuery, callback_data: AnalysisCallback, state: FSMContext):
    data = get_path(callback_data.path)
    await callback.message.edit_text(
        data['input_text'],
        reply_markup=input_markup(callback_data=callback_data).as_markup()
    )
    await state.update_data(callback_path=callback_data.path)
    await state.set_state(AnalysisStates.waiting_ticker_input)
    await callback.answer()


@router.callback_query(AnalysisCallback.filter(F.path.endswith("sector")))
async def sector_analysis(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    data = get_path(callback_data.path)
    sectors = repositories.sector.get_all()
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
    industries = repositories.industry.get_all_by_sector_id(callback_data.path.split('#sctr')[0].split('%')[-1])
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
    industry_id = callback_data.path.split('#inds')[0].split('%')[-1]
    industry = Industry(repositories.industry.get_key_by_id(industry_id))
    await callback.message.edit_text(
        industry.get_overview(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_top")))
async def industry_top_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry_id = callback_data.path.split('#inds')[0].split('%')[-1]
    industry = Industry(repositories.industry.get_key_by_id(industry_id))
    await callback.message.edit_text(
        industry.get_top_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_top_growth")))
async def sector_top_growth_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry_id = callback_data.path.split('#inds')[0].split('%')[-1]
    industry = Industry(repositories.industry.get_key_by_id(industry_id))
    await callback.message.edit_text(
        industry.get_top_growth_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("i_top_perf")))
async def industry_top_performing_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    industry_id = callback_data.path.split('#inds')[0].split('%')[-1]
    industry = Industry(repositories.industry.get_key_by_id(industry_id))
    await callback.message.edit_text(
        industry.get_top_performing_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_overview")))
async def sector_overview(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sector_id = callback_data.path.split('#sctr')[0].split('%')[-1]
    sector = Sector(repositories.sector.get_name_by_id(sector_id))
    await callback.message.edit_text(
        sector.get_overview(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_top_companies")))
async def sector_top_companies(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sector_id = callback_data.path.split('#sctr')[0].split('%')[-1]
    sector = Sector(repositories.sector.get_name_by_id(sector_id))
    await callback.message.edit_text(
        sector.get_top_companies(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(AnalysisCallback.filter(F.path.endswith("s_top_etfs")))
async def sector_top_etfs(callback: types.CallbackQuery, callback_data: AnalysisCallback):
    sector_id = callback_data.path.split('#sctr')[0].split('%')[-1]
    sector = Sector(repositories.sector.get_name_by_id(sector_id))
    await callback.message.edit_text(
        sector.get_top_etfs(),
        reply_markup=callback.message.reply_markup
    )
