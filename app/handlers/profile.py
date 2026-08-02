"""Раздел «Профиль»: избранное, портфель, статистика."""

from __future__ import annotations

import logging
from decimal import Decimal
from functools import partial
from typing import cast

from aiogram import Router
from aiogram.types import CallbackQuery

from app.callbacks import TICKER_SUFFIX, CompanyCallback, Origin, ProfileCallback
from app.data.config import get_settings
from app.entities.company import Company
from app.handlers.common import (
    ack,
    db_call,
    market_call,
    node_is,
    send_report,
    show_items,
    show_menu,
    show_result,
    ticker_items,
)
from app.repositories import repositories
from app.repositories.dto import NamedItem, PositionDTO, UserActivityStats
from app.services.reports import render_pie_chart
from app.services.stats import (
    UserStatsView,
    estimate_ttm_dividends,
    format_user_stats,
    sector_allocation,
)
from app.utils.i18n import t

logger = logging.getLogger(__name__)

router = Router(name="profile")


@router.callback_query(ProfileCallback.filter(node_is("profile")))
async def profile_menu(callback: CallbackQuery, callback_data: ProfileCallback) -> None:
    await show_menu(callback, callback_data)


@router.callback_query(ProfileCallback.filter(node_is("favourites")))
async def favourites_list(
    callback: CallbackQuery, callback_data: ProfileCallback, user_id: int
) -> None:
    tickers = await db_call(
        repositories.favourites.list_tickers, user_id, description="список избранного"
    )
    await show_items(
        callback,
        callback_data,
        ticker_items(tickers),
        TICKER_SUFFIX,
        target=CompanyCallback(come_through=Origin.PROFILE, path="company"),
        empty_text=t("handlers.favourites.empty"),
        columns=3,
    )


@router.callback_query(ProfileCallback.filter(node_is("stats")))
async def user_stats(
    callback: CallbackQuery, callback_data: ProfileCallback, user_id: int
) -> None:
    await ack(callback, t("handlers.stats.progress"))

    positions = cast(
        list[PositionDTO],
        await db_call(
            repositories.portfolio.list_positions,
            user_id,
            description="позиции для статистики",
        ),
    )
    favourites_count = cast(
        int,
        await db_call(
            repositories.favourites.count,
            user_id,
            description="число избранного",
        ),
    )
    activity = cast(
        UserActivityStats,
        await db_call(
            partial(repositories.event.user_stats, user_id, top_n=5),
            description="активность пользователя",
        ),
    )
    sectors = cast(
        list[NamedItem],
        await db_call(
            repositories.sector.list_all, description="секторы для статистики"
        ),
    )

    quotes: dict[str, Decimal] = {}
    truncated = False
    estimated_dividends: Decimal | None = None
    if positions:
        quotes, truncated = await _load_quotes(positions)
        estimated_dividends = cast(
            Decimal | None,
            await market_call(
                estimate_ttm_dividends,
                positions,
                description="оценка дивидендов",
            ),
        )

    view = UserStatsView(
        positions=tuple(positions),
        quotes=quotes,
        quotes_truncated=truncated,
        favourites_count=favourites_count,
        activity=activity,
        sector_names={item.id: item.name for item in sectors},
        estimated_dividends=estimated_dividends,
    )
    text = format_user_stats(view)
    allocation = sector_allocation(view)
    if allocation.empty:
        await show_result(callback, callback_data, text)
        return

    await ack(callback, t("handlers.progress.report"))
    await send_report(
        callback,
        callback_data,
        render=partial(
            render_pie_chart,
            allocation,
            title=t("handlers.stats.pie_title"),
        ),
        description="распределение по секторам",
        caption=text,
    )


async def _load_quotes(
    positions: list[PositionDTO],
) -> tuple[dict[str, Decimal], bool]:
    limit = get_settings().portfolio_valuation_limit
    truncated = len(positions) > limit
    tickers = [position.ticker for position in positions[:limit]]
    if not tickers:
        return {}, truncated
    quotes = cast(
        dict[str, Decimal],
        await market_call(
            Company.quotes,
            tickers,
            description="котировки для статистики",
        ),
    )
    return quotes, truncated
