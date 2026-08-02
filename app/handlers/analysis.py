"""Раздел «Анализ»: секторы, отрасли и переход к карточке компании."""

from __future__ import annotations

import logging
from functools import partial
from typing import Callable

import pandas as pd
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.callbacks import (
    INDUSTRY_SUFFIX,
    SECTOR_SUFFIX,
    TICKER_SUFFIX,
    AnalysisCallback,
    CompanyCallback,
    Origin,
)
from app.core.errors import ValidationError
from app.entities.company import Company
from app.entities.industry import Industry
from app.entities.sector import Sector
from app.handlers.common import (
    ack,
    db_call,
    has_value,
    last_node,
    market_call,
    named_items,
    node_for,
    node_is,
    required_id,
    send_report,
    show_items,
    show_menu,
    show_result,
    ticker_items,
)
from app.keyboards.make_markup import back_keyboard
from app.repositories import repositories
from app.services.reports import render_bar_chart, render_line_chart, render_table
from app.states import TickerInput
from app.utils.i18n import t
from app.utils.messaging import safe_edit
from app.utils.text import escape

logger = logging.getLogger(__name__)

router = Router(name="analysis")

# История ведущего ETF сектора: достаточно для динамики, без max.
SECTOR_ETF_CHART_PERIOD = "1y"

INDUSTRY_RANKINGS: dict[str, tuple[Callable[[Industry], pd.DataFrame], str, str]] = {
    "i_top": (
        Industry.top_companies,
        "handlers.analysis.ranking.top",
        "топ компаний отрасли",
    ),
    "i_top_growth": (
        Industry.top_growth_companies,
        "handlers.analysis.ranking.growth",
        "быстрорастущие компании отрасли",
    ),
    "i_top_perf": (
        Industry.top_performing_companies,
        "handlers.analysis.ranking.perf",
        "лучшие по динамике компании отрасли",
    ),
}


@router.callback_query(AnalysisCallback.filter(node_is("analysis", "company")))
async def analysis_menu(callback: CallbackQuery, callback_data: AnalysisCallback) -> None:
    await show_menu(callback, callback_data)


@router.callback_query(AnalysisCallback.filter(node_is("input_ticker")))
async def ask_for_ticker(
    callback: CallbackQuery, callback_data: AnalysisCallback, state: FSMContext
) -> None:
    node = node_for(callback_data)
    await safe_edit(
        callback,
        escape(node.input_text or node.text),
        back_keyboard(callback_data),
    )
    await state.set_state(TickerInput.waiting)
    await state.update_data(origin=Origin.ANALYSIS.value)


@router.callback_query(AnalysisCallback.filter(node_is("company_fav")))
async def favourites_picker(
    callback: CallbackQuery, callback_data: AnalysisCallback, user_id: int
) -> None:
    tickers = await db_call(
        repositories.favourites.list_tickers, user_id, description="список избранного"
    )
    await show_items(
        callback,
        callback_data,
        ticker_items(tickers),
        TICKER_SUFFIX,
        target=CompanyCallback(come_through=Origin.ANALYSIS, path="company"),
        empty_text=t("handlers.favourites.empty"),
        columns=3,
    )


# --- секторы ---


@router.callback_query(
    AnalysisCallback.filter(node_is("sector") & ~has_value(SECTOR_SUFFIX))
)
async def sector_list(callback: CallbackQuery, callback_data: AnalysisCallback) -> None:
    sectors = await db_call(repositories.sector.list_all, description="список секторов")
    await show_items(
        callback,
        callback_data,
        named_items(sectors),
        SECTOR_SUFFIX,
        empty_text=t("handlers.analysis.empty_sectors"),
        columns=1,
    )


@router.callback_query(
    AnalysisCallback.filter(node_is("sector") & has_value(SECTOR_SUFFIX))
)
async def sector_menu(callback: CallbackQuery, callback_data: AnalysisCallback) -> None:
    await show_menu(callback, callback_data)


async def _sector(callback_data: AnalysisCallback) -> Sector:
    sector_id = required_id(
        callback_data, SECTOR_SUFFIX, entity=t("handlers.entity.sector")
    )
    key = await db_call(
        repositories.sector.get_key, sector_id, description="ключ сектора"
    )
    if not key:
        raise ValidationError(t("handlers.analysis.sector_gone"))
    name = await db_call(
        repositories.sector.get_name, sector_id, description="имя сектора"
    )
    return Sector(key, name=name)


@router.callback_query(AnalysisCallback.filter(node_is("s_overview")))
async def sector_overview(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await ack(callback)
    sector = await _sector(callback_data)
    text = await market_call(sector.format_overview, description="обзор сектора")
    await show_result(callback, callback_data, text)


@router.callback_query(AnalysisCallback.filter(node_is("s_industries")))
async def sector_industries(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await ack(callback, t("handlers.progress.report"))
    sector = await _sector(callback_data)
    frame = await market_call(sector.industries, description="отрасли сектора")
    title = t("handlers.analysis.industries_title", name=sector.display_name)
    await send_report(
        callback,
        callback_data,
        render=partial(render_table, frame, title=title),
        description=title,
    )


@router.callback_query(AnalysisCallback.filter(node_is("s_top_companies")))
async def sector_top_companies(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await ack(callback)
    sector = await _sector(callback_data)
    text = await market_call(
        sector.format_top_companies, description="топ компаний сектора"
    )
    await show_result(callback, callback_data, text)


@router.callback_query(AnalysisCallback.filter(node_is("s_top_etfs")))
async def sector_top_etfs(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await ack(callback)
    sector = await _sector(callback_data)
    text = await market_call(sector.format_top_etfs, description="топ ETF сектора")
    await show_result(callback, callback_data, text)


@router.callback_query(AnalysisCallback.filter(node_is("s_etf_chart")))
async def sector_etf_chart(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await ack(callback, t("handlers.progress.report"))
    sector = await _sector(callback_data)
    ticker = await market_call(
        sector.leading_etf_ticker, description="ведущий ETF сектора"
    )
    company = Company(str(ticker))
    series = await market_call(
        company.price_history,
        SECTOR_ETF_CHART_PERIOD,
        description=f"котировки {ticker}",
    )
    title = t(
        "handlers.analysis.etf_chart_title",
        name=sector.display_name,
        ticker=ticker,
    )
    await send_report(
        callback,
        callback_data,
        render=partial(render_line_chart, series, title=title),
        description=title,
    )


# --- отрасли ---


@router.callback_query(
    AnalysisCallback.filter(node_is("s_industry") & ~has_value(INDUSTRY_SUFFIX))
)
async def industry_list(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    sector_id = required_id(
        callback_data, SECTOR_SUFFIX, entity=t("handlers.entity.sector")
    )
    industries = await db_call(
        repositories.industry.list_by_sector,
        sector_id,
        description="список отраслей",
    )
    await show_items(
        callback,
        callback_data,
        named_items(industries),
        INDUSTRY_SUFFIX,
        empty_text=t("handlers.analysis.empty_industries"),
        columns=1,
    )


@router.callback_query(
    AnalysisCallback.filter(node_is("s_industry") & has_value(INDUSTRY_SUFFIX))
)
async def industry_menu(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await show_menu(callback, callback_data)


async def _industry(callback_data: AnalysisCallback) -> Industry:
    industry_id = required_id(
        callback_data, INDUSTRY_SUFFIX, entity=t("handlers.entity.industry")
    )
    key = await db_call(
        repositories.industry.get_key, industry_id, description="ключ отрасли"
    )
    if not key:
        raise ValidationError(t("handlers.analysis.industry_gone"))
    name = await db_call(
        repositories.industry.get_name, industry_id, description="имя отрасли"
    )
    return Industry(key, name=name)


@router.callback_query(AnalysisCallback.filter(node_is("i_overview")))
async def industry_overview(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    await ack(callback)
    industry = await _industry(callback_data)
    text = await market_call(industry.format_overview, description="обзор отрасли")
    await show_result(callback, callback_data, text)


@router.callback_query(AnalysisCallback.filter(node_is(*INDUSTRY_RANKINGS)))
async def industry_ranking_report(
    callback: CallbackQuery, callback_data: AnalysisCallback
) -> None:
    """Топ отрасли: таблица и столбчатая диаграмма по ключевой метрике."""
    await ack(callback, t("handlers.progress.report"))
    load, title_key, description = INDUSTRY_RANKINGS[last_node(callback_data.path)]
    industry = await _industry(callback_data)
    frame = await market_call(load, industry, description=description)
    name = industry.display_name
    title = t(title_key, name=name)
    metric = industry.chart_metric(frame)

    await send_report(
        callback,
        callback_data,
        render=partial(render_table, frame, title=title),
        description=title,
    )
    chart_title = t(
        "handlers.analysis.chart_title_with_metric",
        title=title,
        metric=metric.name,
    )
    await send_report(
        callback,
        callback_data,
        render=partial(render_bar_chart, metric, title=chart_title),
        description=chart_title,
    )
