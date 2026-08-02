"""Раздел «Портфель»: позиции, сводка, история и ввод сделок.

Обработка текстового ввода живёт здесь, а не в `ticker_input`: состояние
`PortfolioInput` не пересекается с ожиданием тикера, и строка сделки не должна
проходить рыночную проверку существования тикера — справочник компаний
проверяет репозиторий при записи.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from functools import partial

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.callbacks import CompanyCallback, ProfileCallback
from app.data.config import get_settings
from app.entities.company import Company
from app.handlers.common import (
    ack,
    db_call,
    market_call,
    node_for,
    node_is,
    required_ticker,
    show_menu,
    show_result,
)
from app.keyboards.make_markup import back_keyboard
from app.repositories import repositories
from app.repositories.dto import (
    AddTransactionResult,
    DeleteTransactionResult,
    PositionDTO,
    TransactionDTO,
)
from app.states import PortfolioInput
from app.utils.i18n import t
from app.utils.messaging import safe_edit
from app.utils.text import escape, format_number, format_percent, join_lines
from app.utils.validators import parse_entity_id, parse_trade

logger = logging.getLogger(__name__)

router = Router(name="portfolio")

_ADD_RESPONSE_KEYS = {
    AddTransactionResult.ADDED: "handlers.portfolio.add.ok",
    AddTransactionResult.COMPANY_NOT_FOUND: "handlers.portfolio.add.company_missing",
    AddTransactionResult.NOT_ENOUGH_SHARES: "handlers.portfolio.add.not_enough",
}

_DELETE_RESPONSE_KEYS = {
    DeleteTransactionResult.DELETED: "handlers.portfolio.delete.ok",
    DeleteTransactionResult.NOT_FOUND: "handlers.portfolio.delete.not_found",
}

_SIDE_KEYS = {
    "BUY": "handlers.portfolio.side.buy",
    "SELL": "handlers.portfolio.side.sell",
}
_ZERO = Decimal("0")


@router.callback_query(ProfileCallback.filter(node_is("portfolio")))
async def portfolio_menu(
    callback: CallbackQuery, callback_data: ProfileCallback
) -> None:
    await show_menu(callback, callback_data)


@router.callback_query(ProfileCallback.filter(node_is("pf_positions")))
async def positions_list(
    callback: CallbackQuery, callback_data: ProfileCallback, user_id: int
) -> None:
    await ack(callback, t("handlers.portfolio.quote_progress"))
    positions = await db_call(
        repositories.portfolio.list_positions,
        user_id,
        description="позиции портфеля",
    )
    if not positions:
        await show_result(
            callback, callback_data, escape(t("handlers.portfolio.empty_positions"))
        )
        return
    quotes, truncated = await _load_quotes(positions)
    await show_result(
        callback,
        callback_data,
        _format_positions(positions, quotes, truncated=truncated),
    )


@router.callback_query(ProfileCallback.filter(node_is("pf_summary")))
async def portfolio_summary(
    callback: CallbackQuery, callback_data: ProfileCallback, user_id: int
) -> None:
    await ack(callback, t("handlers.portfolio.quote_progress"))
    positions = await db_call(
        repositories.portfolio.list_positions,
        user_id,
        description="сводка портфеля",
    )
    if not positions:
        await show_result(
            callback, callback_data, escape(t("handlers.portfolio.empty_positions"))
        )
        return
    quotes, truncated = await _load_quotes(positions)
    await show_result(
        callback,
        callback_data,
        _format_summary(positions, quotes, truncated=truncated),
    )


@router.callback_query(ProfileCallback.filter(node_is("pf_history")))
async def transactions_history(
    callback: CallbackQuery, callback_data: ProfileCallback, user_id: int
) -> None:
    transactions = await db_call(
        repositories.portfolio.list_transactions,
        user_id,
        description="история сделок",
    )
    if not transactions:
        await show_result(
            callback, callback_data, escape(t("handlers.portfolio.empty_history"))
        )
        return
    await show_result(callback, callback_data, _format_history(transactions))


@router.callback_query(ProfileCallback.filter(node_is("pf_add")))
async def ask_add_trade(
    callback: CallbackQuery, callback_data: ProfileCallback, state: FSMContext
) -> None:
    node = node_for(callback_data)
    await safe_edit(
        callback,
        escape(node.input_text or node.text),
        back_keyboard(callback_data),
    )
    await state.set_state(PortfolioInput.waiting)
    await state.update_data(action="add", ticker=None)


@router.callback_query(ProfileCallback.filter(node_is("pf_del")))
async def ask_delete_trade(
    callback: CallbackQuery, callback_data: ProfileCallback, state: FSMContext
) -> None:
    node = node_for(callback_data)
    await safe_edit(
        callback,
        escape(node.input_text or node.text),
        back_keyboard(callback_data),
    )
    await state.set_state(PortfolioInput.waiting)
    await state.update_data(action="delete")


@router.callback_query(CompanyCallback.filter(node_is("buy")))
async def ask_add_trade_from_company(
    callback: CallbackQuery, callback_data: CompanyCallback, state: FSMContext
) -> None:
    """Тикер уже в пути карточки — пользователю остаются количество и цена."""
    ticker = required_ticker(callback_data)
    node = node_for(callback_data)
    prompt = node.input_text or node.text
    await safe_edit(
        callback,
        escape(f"{prompt}\n{t('handlers.portfolio.preset_ticker', ticker=ticker)}"),
        back_keyboard(callback_data),
    )
    await state.set_state(PortfolioInput.waiting)
    await state.update_data(action="add", ticker=ticker)


@router.message(PortfolioInput.waiting, F.text)
async def process_portfolio_input(
    message: Message, state: FSMContext, user_id: int
) -> None:
    data = await state.get_data()
    action = str(data.get("action", "add"))

    if action == "delete":
        transaction_id = parse_entity_id(
            message.text or "", entity=t("handlers.entity.trade")
        )
        result = await db_call(
            repositories.portfolio.delete_transaction,
            user_id,
            transaction_id,
            description="удаление сделки",
        )
        await state.clear()
        await message.answer(t(_DELETE_RESPONSE_KEYS[result]))
        return

    raw = (message.text or "").strip()
    preset_ticker = data.get("ticker")
    if preset_ticker:
        # Из карточки компании тикер уже известен — дописываем его в начало.
        raw = f"{preset_ticker} {raw}"

    trade = parse_trade(raw)
    result = await db_call(
        partial(
            repositories.portfolio.add_transaction,
            user_id,
            trade.ticker,
            trade.side,
            trade.quantity,
            trade.price,
            trade.traded_at,
            platform=trade.platform,
        ),
        description="добавление сделки",
    )
    await state.clear()
    await message.answer(t(_ADD_RESPONSE_KEYS[result]))


@router.message(PortfolioInput.waiting)
async def wrong_portfolio_input_type(message: Message) -> None:
    await message.answer(t("handlers.portfolio.wrong_type"))


async def _load_quotes(
    positions: list[PositionDTO],
) -> tuple[dict[str, Decimal], bool]:
    """Котировки для оценки; один `market_call` на всю пачку.

    Возвращает словарь цен и флаг, что лимит оценки обрезал портфель.
    """
    limit = get_settings().portfolio_valuation_limit
    truncated = len(positions) > limit
    tickers = [position.ticker for position in positions[:limit]]
    if not tickers:
        return {}, truncated
    quotes = await market_call(
        Company.quotes,
        tickers,
        description="котировки портфеля",
    )
    return quotes, truncated  # type: ignore[return-value]


def _format_decimal(value: Decimal, *, digits: int = 2) -> str:
    rendered = format_number(value, digits=digits)
    return rendered if rendered is not None else str(value)


def _format_signed(value: Decimal) -> str:
    body = _format_decimal(value)
    if value > 0:
        return f"+{body}"
    return body


def _unrealized(
    position: PositionDTO, quote: Decimal | None
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Рыночная стоимость, P&L в валюте и как доля от вложений."""
    if quote is None:
        return None, None, None
    market_value = position.quantity * quote
    pnl = market_value - position.invested
    ratio = (pnl / position.invested) if position.invested > _ZERO else None
    return market_value, pnl, ratio


def _valuation_note(*, truncated: bool, priced: int, total: int) -> str | None:
    parts: list[str] = []
    if truncated:
        limit = get_settings().portfolio_valuation_limit
        parts.append(
            t("handlers.portfolio.note.truncated", limit=limit, total=total)
        )
    elif priced < total:
        parts.append(
            t("handlers.portfolio.note.partial", priced=priced, total=total)
        )
    return " ".join(parts) if parts else None


def _format_positions(
    positions: list[PositionDTO],
    quotes: dict[str, Decimal],
    *,
    truncated: bool,
) -> str:
    blocks: list[str] = []
    priced = 0
    for position in positions:
        quote = quotes.get(position.ticker)
        market_value, pnl, ratio = _unrealized(position, quote)
        lines = [
            f"<b>{escape(position.ticker)}</b> — {escape(position.name)}",
            t(
                "handlers.portfolio.field.quantity",
                value=_format_decimal(position.quantity, digits=4),
            ),
            t(
                "handlers.portfolio.field.avg_price",
                value=_format_decimal(position.average_price),
            ),
            t(
                "handlers.portfolio.field.invested",
                value=_format_decimal(position.invested),
                currency=escape(position.currency),
            ),
        ]
        if market_value is not None and pnl is not None:
            priced += 1
            lines.append(
                t(
                    "handlers.portfolio.field.market_value",
                    value=_format_decimal(market_value),
                    currency=escape(position.currency),
                )
            )
            pnl_line = t(
                "handlers.portfolio.field.unrealized",
                value=_format_signed(pnl),
                currency=escape(position.currency),
            )
            percent = format_percent(ratio) if ratio is not None else None
            if percent:
                pnl_line += f" ({percent})"
            lines.append(pnl_line)
        else:
            lines.append(t("handlers.portfolio.field.no_valuation"))
        blocks.append(join_lines(lines))

    note = _valuation_note(
        truncated=truncated, priced=priced, total=len(positions)
    )
    body = "\n\n".join(blocks)
    if note:
        return f"{escape(note)}\n\n{body}"
    return body


def _format_summary(
    positions: list[PositionDTO],
    quotes: dict[str, Decimal],
    *,
    truncated: bool,
) -> str:
    invested = sum((p.invested for p in positions), _ZERO)
    realized = sum((p.realized_pnl for p in positions), _ZERO)
    currency = positions[0].currency

    market_total = _ZERO
    unrealized_total = _ZERO
    priced = 0
    for position in positions:
        quote = quotes.get(position.ticker)
        market_value, pnl, _ratio = _unrealized(position, quote)
        if market_value is None or pnl is None:
            continue
        priced += 1
        market_total += market_value
        unrealized_total += pnl

    lines = [
        t("handlers.portfolio.summary.open_count", count=len(positions)),
        t(
            "handlers.portfolio.summary.invested",
            value=_format_decimal(invested),
            currency=escape(currency),
        ),
    ]
    if priced:
        invested_priced = sum(
            (p.invested for p in positions if p.ticker in quotes),
            _ZERO,
        )
        ratio = (
            unrealized_total / invested_priced if invested_priced > _ZERO else None
        )
        lines.append(
            t(
                "handlers.portfolio.summary.market",
                value=_format_decimal(market_total),
                currency=escape(currency),
            )
        )
        pnl_line = t(
            "handlers.portfolio.summary.unrealized",
            value=_format_signed(unrealized_total),
            currency=escape(currency),
        )
        percent = format_percent(ratio) if ratio is not None else None
        if percent:
            pnl_line += f" ({percent})"
        lines.append(pnl_line)
    else:
        lines.append(t("handlers.portfolio.summary.market_na"))

    lines.append(
        t(
            "handlers.portfolio.summary.realized",
            value=_format_decimal(realized),
            currency=escape(currency),
        )
    )

    note = _valuation_note(
        truncated=truncated, priced=priced, total=len(positions)
    )
    if note:
        lines.extend(["", escape(note)])
    return join_lines(lines)


def _format_history(transactions: list[TransactionDTO]) -> str:
    lines: list[str] = []
    for tx in transactions:
        side_key = _SIDE_KEYS.get(tx.side)
        side = t(side_key) if side_key else tx.side
        platform = f" · {escape(tx.platform)}" if tx.platform else ""
        lines.append(
            (
                f"<b>#{tx.id}</b> {escape(tx.ticker)} · {escape(side)} · "
                f"{_format_decimal(tx.quantity, digits=4)} × "
                f"{_format_decimal(tx.price)} · {tx.traded_at.isoformat()}"
                f"{platform}"
            )
        )
    return "\n".join(lines)
