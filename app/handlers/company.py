"""Карточка компании: справка, графики, отчётность, избранное.

Экраны описаны таблицами соответствий, а не двумя десятками почти одинаковых
функций: добавление нового отчёта — это одна строка в словаре.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from typing import Callable

import pandas as pd
from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.callbacks import CompanyCallback
from app.entities.company import Company
from app.handlers.common import (
    db_call,
    has_value,
    last_node,
    market_call,
    node_for,
    node_is,
    not_implemented,
    required_ticker,
    send_report,
    show_menu,
    show_result,
)
from app.keyboards.make_markup import back_keyboard, menu_keyboard
from app.repositories import repositories
from app.repositories.dto import AddFavouriteResult, RemoveFavouriteResult
from app.services.reports import render_line_chart, render_table
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

# Разделы, которых пока нет.
PLANNED = ("ti_ma", "ti_MACD", "ti_RSI", "ti_momentum", "ti_bal_vlm", "buy")

TEXT_ACTIONS: dict[str, Callable[[Company], str]] = {
    "i_about": Company.format_info,
    "i_desc": Company.format_description,
    "i_divs": Company.format_dividends,
    "ai_news": Company.format_news,
    "c_multipliers": Company.format_multipliers,
}


@dataclass(frozen=True, slots=True)
class TableReport:
    """Описание табличного отчёта: откуда взять данные и как подписать."""

    load: Callable[[Company], pd.DataFrame]
    title: str


TABLE_REPORTS: dict[str, TableReport] = {
    "fin_year": TableReport(
        lambda company: company.financials(quarterly=False),
        "Финансовая отчётность {name}, по годам",
    ),
    "fin_quarter": TableReport(
        lambda company: company.financials(quarterly=True),
        "Финансовая отчётность {name}, по кварталам",
    ),
    "bs_year": TableReport(
        lambda company: company.balance_sheet(quarterly=False),
        "Балансовая отчётность {name}, по годам",
    ),
    "bs_quarter": TableReport(
        lambda company: company.balance_sheet(quarterly=True),
        "Балансовая отчётность {name}, по кварталам",
    ),
    "cf_year": TableReport(
        lambda company: company.cash_flow(quarterly=False),
        "Денежный поток {name}, по годам",
    ),
    "cf_quarter": TableReport(
        lambda company: company.cash_flow(quarterly=True),
        "Денежный поток {name}, по кварталам",
    ),
    "inc_year": TableReport(
        lambda company: company.income_statement(quarterly=False),
        "Отчёт о прибыли {name}, по годам",
    ),
    "inc_quarter": TableReport(
        lambda company: company.income_statement(quarterly=True),
        "Отчёт о прибыли {name}, по кварталам",
    ),
    "ai_mh": TableReport(
        lambda company: company.major_holders(),
        "Основные держатели акций {name}",
    ),
    "ai_ih": TableReport(
        lambda company: company.institutional_holders(),
        "Институциональные держатели акций {name}",
    ),
}

CHART_PERIODS: dict[str, tuple[str, str]] = {
    "g_full": ("max", "за всё время"),
    "g_1mo": ("1mo", "за месяц"),
    "g_6mo": ("6mo", "за полгода"),
    "g_1y": ("1y", "за год"),
    "g_5y": ("5y", "за пять лет"),
}

SELECT_COMPANY = "Сначала выберите компанию."


async def company_name(company: Company) -> str:
    return await market_call(
        lambda: company.display_name, description=f"название {company.ticker}"
    )


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
    await safe_edit(callback, SELECT_COMPANY, back_keyboard(callback_data))


@router.callback_query(CompanyCallback.filter(node_is(*SUBMENUS)))
async def company_submenu(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
    await show_menu(callback, callback_data)


@router.callback_query(CompanyCallback.filter(node_is(*TEXT_ACTIONS)))
async def company_text_action(
    callback: CallbackQuery, callback_data: CompanyCallback
) -> None:
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
    report = TABLE_REPORTS[last_node(callback_data.path)]
    company = Company(required_ticker(callback_data))

    frame = await market_call(
        report.load, company, description=f"отчёт {company.ticker}"
    )
    name = await company_name(company)
    title = report.title.format(name=name)

    await send_report(
        callback,
        callback_data,
        render=partial(render_table, frame, title=title),
        description=title,
    )


@router.callback_query(CompanyCallback.filter(node_is(*CHART_PERIODS)))
async def company_chart(callback: CallbackQuery, callback_data: CompanyCallback) -> None:
    period, label = CHART_PERIODS[last_node(callback_data.path)]
    company = Company(required_ticker(callback_data))

    series = await market_call(
        company.price_history, period, description=f"котировки {company.ticker}"
    )
    name = await company_name(company)
    title = f"Котировки {name} {label}"

    await send_report(
        callback,
        callback_data,
        render=partial(render_line_chart, series, title=title),
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
        AddFavouriteResult.ADDED: f"{ticker} добавлен в избранное",
        AddFavouriteResult.ALREADY_EXISTS: f"{ticker} уже в избранном",
        AddFavouriteResult.COMPANY_NOT_FOUND: (
            f"{ticker} отсутствует в справочнике компаний, добавить не получится"
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
        RemoveFavouriteResult.REMOVED: f"{ticker} удалён из избранного",
        RemoveFavouriteResult.NOT_IN_FAVOURITES: f"{ticker} не был в избранном",
        RemoveFavouriteResult.COMPANY_NOT_FOUND: (
            f"{ticker} отсутствует в справочнике компаний"
        ),
    }
    await callback.answer(
        responses[result],
        show_alert=result is RemoveFavouriteResult.COMPANY_NOT_FOUND,
    )


@router.callback_query(CompanyCallback.filter(node_is(*PLANNED)))
async def planned_feature(callback: CallbackQuery) -> None:
    await not_implemented(callback)
