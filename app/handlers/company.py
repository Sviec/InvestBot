"""Карточка компании: справка, графики, отчётность, избранное.

Экраны описаны таблицами соответствий, а не двумя десятками почти одинаковых
функций: добавление нового отчёта — это одна строка в словаре.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from typing import Callable, Mapping

import pandas as pd
from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.callbacks import CompanyCallback
from app.entities.company import Company
from app.entities import indicators as ti
from app.handlers.common import (
    ack,
    db_call,
    has_value,
    last_node,
    market_call,
    node_for,
    node_is,
    required_ticker,
    send_report,
    show_menu,
    show_result,
)
from app.keyboards.make_markup import back_keyboard, menu_keyboard
from app.repositories import repositories
from app.repositories.dto import AddFavouriteResult, RemoveFavouriteResult
from app.services.reports import render_indicator_chart, render_line_chart, render_table
from app.utils.i18n import t
from app.utils.messaging import safe_edit
from app.utils.text import escape

logger = logging.getLogger(__name__)

router = Router(name="company")

# Экраны, которые просто показывают вложенное меню.
SUBMENUS = (
    "c_info",
    "c_graph",
    "g_period",
    "c_add_info",
    "c_fa",
    "fa_fin",
    "c_bs",
    "c_cf",
    "c_earns",
    "c_ti",
)

TEXT_ACTIONS: dict[str, Callable[[Company], str]] = {
    "i_about": Company.format_info,
    "i_desc": Company.format_description,
    "i_divs": Company.format_dividends,
    "ai_news": Company.format_news,
    "c_multipliers": Company.format_multipliers,
    "fa_key": Company.format_key_metrics,
}


@dataclass(frozen=True, slots=True)
class TableReport:
    """Описание табличного отчёта: откуда взять данные и как подписать."""

    load: Callable[[Company], pd.DataFrame]
    title_key: str


TABLE_REPORTS: dict[str, TableReport] = {
    "fin_year": TableReport(
        lambda company: company.financials(quarterly=False),
        "handlers.company.table.fin_year",
    ),
    "fin_quarter": TableReport(
        lambda company: company.financials(quarterly=True),
        "handlers.company.table.fin_quarter",
    ),
    "bs_year": TableReport(
        lambda company: company.balance_sheet(quarterly=False),
        "handlers.company.table.bs_year",
    ),
    "bs_quarter": TableReport(
        lambda company: company.balance_sheet(quarterly=True),
        "handlers.company.table.bs_quarter",
    ),
    "cf_year": TableReport(
        lambda company: company.cash_flow(quarterly=False),
        "handlers.company.table.cf_year",
    ),
    "cf_quarter": TableReport(
        lambda company: company.cash_flow(quarterly=True),
        "handlers.company.table.cf_quarter",
    ),
    "inc_year": TableReport(
        lambda company: company.income_statement(quarterly=False),
        "handlers.company.table.inc_year",
    ),
    "inc_quarter": TableReport(
        lambda company: company.income_statement(quarterly=True),
        "handlers.company.table.inc_quarter",
    ),
    "ai_mh": TableReport(
        lambda company: company.major_holders(),
        "handlers.company.table.major_holders",
    ),
    "ai_ih": TableReport(
        lambda company: company.institutional_holders(),
        "handlers.company.table.inst_holders",
    ),
}

CHART_PERIODS: dict[str, tuple[str, str]] = {
    "g_full": ("max", "handlers.company.chart.period_full"),
    "g_1mo": ("1mo", "handlers.company.chart.period_1mo"),
    "g_6mo": ("6mo", "handlers.company.chart.period_6mo"),
    "g_1y": ("1y", "handlers.company.chart.period_1y"),
    "g_5y": ("5y", "handlers.company.chart.period_5y"),
}

# Двух лет хватает на MA200; отдельный запрос к провайдеру не нужен —
# индикаторы считаются локально по OHLCV из price_frame.
INDICATOR_HISTORY_PERIOD = "2y"


@dataclass(frozen=True, slots=True)
class IndicatorChart:
    """Данные для render_indicator_chart после локального расчёта."""

    price: pd.Series
    overlays: Mapping[str, pd.Series]
    panel: Mapping[str, pd.Series]
    panel_bars: Mapping[str, pd.Series]


@dataclass(frozen=True, slots=True)
class IndicatorReport:
    """Описание техиндикатора: как подписать и как посчитать по OHLCV."""

    title_key: str
    build: Callable[[pd.DataFrame], IndicatorChart]


def _ma_chart(frame: pd.DataFrame) -> IndicatorChart:
    close = frame["Close"]
    averages = ti.moving_averages(close)
    return IndicatorChart(
        price=close,
        overlays={column: averages[column] for column in averages.columns},
        panel={},
        panel_bars={},
    )


def _rsi_chart(frame: pd.DataFrame) -> IndicatorChart:
    close = frame["Close"]
    values = ti.rsi(close)
    return IndicatorChart(price=close, overlays={}, panel={"RSI": values}, panel_bars={})


def _macd_chart(frame: pd.DataFrame) -> IndicatorChart:
    close = frame["Close"]
    values = ti.macd(close)
    return IndicatorChart(
        price=close,
        overlays={},
        panel={"MACD": values["MACD"], "Signal": values["Signal"]},
        panel_bars={"Histogram": values["Histogram"]},
    )


def _momentum_chart(frame: pd.DataFrame) -> IndicatorChart:
    close = frame["Close"]
    values = ti.momentum(close)
    return IndicatorChart(
        price=close, overlays={}, panel={"Momentum": values}, panel_bars={}
    )


def _obv_chart(frame: pd.DataFrame) -> IndicatorChart:
    close = frame["Close"]
    values = ti.obv(close, frame["Volume"])
    return IndicatorChart(price=close, overlays={}, panel={"OBV": values}, panel_bars={})


INDICATORS: dict[str, IndicatorReport] = {
    "ti_ma": IndicatorReport("handlers.company.indicator.ma", _ma_chart),
    "ti_MACD": IndicatorReport("handlers.company.indicator.macd", _macd_chart),
    "ti_RSI": IndicatorReport("handlers.company.indicator.rsi", _rsi_chart),
    "ti_momentum": IndicatorReport("handlers.company.indicator.momentum", _momentum_chart),
    "ti_bal_vlm": IndicatorReport("handlers.company.indicator.obv", _obv_chart),
}


async def company_name(company: Company) -> str:
    """Имя из справочника БД; при отсутствии записи — тикер.

    Раньше ходило в yfinance.info только ради подписи — лишний запрос на
    каждую карточку и отчёт.
    """
    row = await db_call(
        repositories.company.get_by_ticker,
        company.ticker,
        description=f"название {company.ticker}",
    )
    if row is not None and row.name:
        return row.name
    return company.ticker


async def render_company_card(
    callback_data: CompanyCallback, name: str
) -> tuple[str, object]:
    node = node_for(callback_data)
    text = f"{escape(node.text)}\n<b>{escape(name)}</b>"
    return text, menu_keyboard(callback_data, node)


async def send_company_card(
    message: Message, callback_data: CompanyCallback, name: str
) -> None:
    """Отправляет карточку компании новым сообщением (после ввода тикера)."""
    text, markup = await render_company_card(callback_data, name)
    await message.answer(text, reply_markup=markup)


@router.callback_query(CompanyCallback.filter(node_is("company") & has_value("tckr")))
async def company_card(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    company = Company(required_ticker(callback_data))
    name = await company_name(company)
    text, markup = await render_company_card(callback_data, name)
    await safe_edit(callback, text, markup)


@router.callback_query(CompanyCallback.filter(node_is("company") & ~has_value("tckr")))
async def company_without_ticker(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    """Страховка: путь карточки без тикера означает устаревшую кнопку."""
    await safe_edit(
        callback, t("handlers.select_company"), back_keyboard(callback_data)
    )


@router.callback_query(CompanyCallback.filter(node_is(*SUBMENUS)))
async def company_submenu(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    await show_menu(callback, callback_data)


@router.callback_query(CompanyCallback.filter(node_is(*TEXT_ACTIONS)))
async def company_text_action(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    await ack(callback)
    action = TEXT_ACTIONS[last_node(callback_data.path)]
    company = Company(required_ticker(callback_data))
    text = await market_call(
        action, company, description=f"{action.__name__} для {company.ticker}"
    )
    await show_result(callback, callback_data, text)


@router.callback_query(CompanyCallback.filter(node_is(*TABLE_REPORTS)))
async def company_table_report(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    await ack(callback, t("handlers.progress.report"))
    report = TABLE_REPORTS[last_node(callback_data.path)]
    company = Company(required_ticker(callback_data))

    frame = await market_call(
        report.load, company, description=f"отчёт {company.ticker}"
    )
    name = await company_name(company)
    title = t(report.title_key, name=name)

    await send_report(
        callback,
        callback_data,
        render=partial(render_table, frame, title=title),
        description=title,
    )


@router.callback_query(CompanyCallback.filter(node_is(*CHART_PERIODS)))
async def company_chart(callback: CallbackQuery, callback_data: CompanyCallback) -> None:
    await ack(callback, t("handlers.progress.report"))
    period, period_key = CHART_PERIODS[last_node(callback_data.path)]
    company = Company(required_ticker(callback_data))

    series = await market_call(
        company.price_history, period, description=f"котировки {company.ticker}"
    )
    name = await company_name(company)
    title = t(
        "handlers.company.chart.title",
        name=name,
        period_label=t(period_key),
    )

    await send_report(
        callback,
        callback_data,
        render=partial(render_line_chart, series, title=title),
        description=title,
    )


@router.callback_query(CompanyCallback.filter(node_is(*INDICATORS)))
async def company_indicator(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    await ack(callback, t("handlers.progress.report"))
    report = INDICATORS[last_node(callback_data.path)]
    company = Company(required_ticker(callback_data))

    frame = await market_call(
        company.price_frame,
        INDICATOR_HISTORY_PERIOD,
        description=f"OHLCV {company.ticker}",
    )
    chart = report.build(frame)
    name = await company_name(company)
    title = t(report.title_key, name=name)

    await send_report(
        callback,
        callback_data,
        render=partial(
            render_indicator_chart,
            chart.price,
            title=title,
            overlays=chart.overlays,
            panel=chart.panel,
            panel_bars=chart.panel_bars,
        ),
        description=title,
    )


@router.callback_query(CompanyCallback.filter(node_is("add")))
async def add_to_favourites(
    callback: CallbackQuery, callback_data: CompanyCallback, user_id: int
) -> None:
    ticker = required_ticker(callback_data)
    result = await db_call(
        repositories.favourites.add,
        user_id,
        ticker,
        description="добавление в избранное",
    )
    responses = {
        AddFavouriteResult.ADDED: t("handlers.company.fav.added", ticker=ticker),
        AddFavouriteResult.ALREADY_EXISTS: t(
            "handlers.company.fav.exists", ticker=ticker
        ),
        AddFavouriteResult.COMPANY_NOT_FOUND: t(
            "handlers.company.fav.not_in_catalog", ticker=ticker
        ),
    }
    await callback.answer(
        responses[result],
        show_alert=result is AddFavouriteResult.COMPANY_NOT_FOUND,
    )


@router.callback_query(CompanyCallback.filter(node_is("remove")))
async def remove_from_favourites(
    callback: CallbackQuery, callback_data: CompanyCallback, user_id: int
) -> None:
    ticker = required_ticker(callback_data)
    result = await db_call(
        repositories.favourites.remove,
        user_id,
        ticker,
        description="удаление из избранного",
    )
    responses = {
        RemoveFavouriteResult.REMOVED: t(
            "handlers.company.fav.removed", ticker=ticker
        ),
        RemoveFavouriteResult.NOT_IN_FAVOURITES: t(
            "handlers.company.fav.not_in_list", ticker=ticker
        ),
        RemoveFavouriteResult.COMPANY_NOT_FOUND: t(
            "handlers.company.fav.remove_not_in_catalog", ticker=ticker
        ),
    }
    await callback.answer(
        responses[result],
        show_alert=result is RemoveFavouriteResult.COMPANY_NOT_FOUND,
    )
