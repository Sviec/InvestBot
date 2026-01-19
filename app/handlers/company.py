from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InputFile, FSInputFile

from app.entities.company import Company
from app.handlers.analysis import AnalysisStates
from app.keyboards.make_markup import build_markup, build_input_markup
from app.utils.navigation import get_path
from callbacks import CompanyCallback

router = Router()

path = 'temp_data/user_files/report.png'


@router.message(AnalysisStates.waiting_ticker_input)
async def process_ticker_input(message: types.Message, state: FSMContext):
    ticker = message.text.strip().upper()
    company = Company(ticker)

    await state.clear()

    callback_data = CompanyCallback(path='company')

    data = get_path('company')
    kb = build_input_markup(callback_data, data, f'{ticker}', 'tckr')
    await message.answer(
        text=data['text'] + f"\n{company.get_name()}",
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("#tckr")))
async def process_ticker_input(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)

    data = get_path('company')
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        text=data['text'] + f"\n{company.get_name()}",
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_info")))
async def common_info(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("i_about")))
async def info_about(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        company.get_info(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("i_desc")))
async def info_about(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        company.get_description(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("i_divs")))
async def info_about(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        company.get_dividends(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("i_about")))
async def info_about(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        company.get_info(),
        reply_markup=callback.message.reply_markup
    )


# @router.callback_query(CompanyCallback.filter(F.path.endswith("i_sustain")))
# async def info_about(callback: types.CallbackQuery, callback_data: CompanyCallback):
#     ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
#     company = Company(ticker)
#     await callback.message.edit_text(
#         company.get_sustainability(),
#         reply_markup=callback.message.reply_markup
#     )


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_graph")))
async def graph(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("g_full")))
async def graph_full(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_graphic, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("g_period")))
async def graph_period(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_graphic, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_add_info")))
async def additional_info(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ai_mh")))
async def additional_info_major_holders(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_major_holders, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("ai_ih")))
async def additional_info_institutional_holders(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_institutional_holders, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("ai_news")))
async def additional_info_news(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        company.get_news(),
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ai_anls")))
async def additional_info_analysis(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_analysis, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_fa")))
async def fundamental_analysis(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("fa_fin")))
async def fundamental_analysis_financials(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("fin_year")))
async def financials_year(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_financials_year, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("fin_quarter")))
async def financials_quarter(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_financials_quarter, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_bs")))
async def fundamental_analysis_balance_sheet(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("bs_year")))
async def balance_sheet_year(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_balance_sheet_year, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("bs_quarter")))
async def balance_sheet_quarter(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_balance_sheet_quarter, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_cf")))
async def fundamental_analysis_cashflow(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("cf_year")))
async def cashflow_year(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_cash_flow_year, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("cf_quarter")))
async def cashflow_quarter(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_cash_flow_quarter, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_earns")))
async def fundamental_analysis_earnings(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)
    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("earns_year")))
async def earnings_year(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_earnings_year, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("earns_quarter")))
async def earnings_quarter(callback: types.CallbackQuery, callback_data: CompanyCallback):
    await send_photo(Company.get_earnings_quarter, callback, callback_data)


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_ti")))
async def tech_indicators(callback: types.CallbackQuery, callback_data: CompanyCallback):
    data = get_path(callback_data.path)
    kb = build_markup(callback_data, data)

    await callback.message.edit_text(
        data['text'],
        reply_markup=kb.as_markup()
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ti_ma")))
async def tech_indicators_ma(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        'В разработке',
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ti_MACD")))
async def tech_indicators_macd(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        'В разработке',
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ti_RSI")))
async def tech_indicators_rsi(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        'В разработке',
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ti_momentum")))
async def tech_indicators_momentum(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        'В разработке',
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("ti_bal_vlm")))
async def tech_indicators_vlm(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        'В разработке',
        reply_markup=callback.message.reply_markup
    )


@router.callback_query(CompanyCallback.filter(F.path.endswith("c_multipliers")))
async def multipliers(callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    await callback.message.edit_text(
        company.get_multiplier(),
        reply_markup=callback.message.reply_markup
    )


async def send_photo(func, callback: types.CallbackQuery, callback_data: CompanyCallback):
    ticker = callback_data.path.split('#tckr')[0].split('%')[-1]
    company = Company(ticker)
    func(company)
    text = callback.message.text
    kb = callback.message.reply_markup

    await callback.message.delete()

    photo_path = f"{path}"
    photo = FSInputFile(photo_path)
    await callback.message.answer_photo(
        photo=photo,
        reply_markup=None
    )
    await callback.message.answer(
        text,
        reply_markup=kb
    )

    await callback.answer()