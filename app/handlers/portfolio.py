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
from app.utils.messaging import safe_edit
from app.utils.text import escape, format_number, format_percent, join_lines
from app.utils.validators import parse_entity_id, parse_trade

logger = logging.getLogger(__name__)

router = Router(name="portfolio")

EMPTY_POSITIONS = "Открытых позиций пока нет. Добавьте сделку в портфель."
EMPTY_HISTORY = "Сделок пока нет."
WRONG_INPUT_TYPE = "Пришлите данные текстом."
QUOTE_PROGRESS = "Обновляю котировки…"

ADD_RESPONSES = {
    AddTransactionResult.ADDED: "Сделка добавлена.",
    AddTransactionResult.COMPANY_NOT_FOUND: (
        "Тикер отсутствует в справочнике компаний, добавить сделку не получится."
    ),
    AddTransactionResult.NOT_ENOUGH_SHARES: (
        "Недостаточно бумаг для продажи: на руках меньше, чем указано в сделке."
    ),
}

DELETE_RESPONSES = {
    DeleteTransactionResult.DELETED: "Сделка удалена.",
    DeleteTransactionResult.NOT_FOUND: "Сделка с таким номером не найдена.",
}

SIDE_LABELS = {"BUY": "покупка", "SELL": "продажа"}
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
    await ack(callback, QUOTE_PROGRESS)
    positions = await db_call(
        repositories.portfolio.list_positions,
        user_id,
        description="позиции портфеля",
    )
    if not positions:
        await show_result(callback, callback_data, escape(EMPTY_POSITIONS))
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
    await ack(callback, QUOTE_PROGRESS)
    positions = await db_call(
        repositories.portfolio.list_positions,
        user_id,
        description="сводка портфеля",
    )
    if not positions:
        await show_result(callback, callback_data, escape(EMPTY_POSITIONS))
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
        await show_result(callback, callback_data, escape(EMPTY_HISTORY))
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
        escape(f"{prompt}\nТикер: {ticker}"),
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
        transaction_id = parse_entity_id(message.text or "", entity="сделки")
        result = await db_call(
            repositories.portfolio.delete_transaction,
            user_id,
            transaction_id,
            description="удаление сделки",
        )
        await state.clear()
        await message.answer(DELETE_RESPONSES[result])
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
    await message.answer(ADD_RESPONSES[result])


@router.message(PortfolioInput.waiting)
async def wrong_portfolio_input_type(message: Message) -> None:
    await message.answer(WRONG_INPUT_TYPE)


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
            f"Рыночная оценка доступна для первых {limit} позиций "
            f"из {total}; остальные показаны без котировок."
        )
    elif priced < total:
        parts.append(
            f"Котировки получены по {priced} из {total} позиций; "
            "остальные показаны без рыночной оценки."
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
            f"количество: {_format_decimal(position.quantity, digits=4)}",
            f"средняя цена: {_format_decimal(position.average_price)}",
            (
                f"вложено: {_format_decimal(position.invested)} "
                f"{escape(position.currency)}"
            ),
        ]
        if market_value is not None and pnl is not None:
            priced += 1
            lines.append(
                f"рыночная стоимость: {_format_decimal(market_value)} "
                f"{escape(position.currency)}"
            )
            pnl_line = (
                f"нереализованный P&amp;L: {_format_signed(pnl)} "
                f"{escape(position.currency)}"
            )
            percent = format_percent(ratio) if ratio is not None else None
            if percent:
                pnl_line += f" ({percent})"
            lines.append(pnl_line)
        else:
            lines.append("рыночная оценка недоступна")
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
        f"<b>Открытых позиций:</b> {len(positions)}",
        f"<b>Вложено:</b> {_format_decimal(invested)} {escape(currency)}",
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
            f"<b>Рыночная стоимость:</b> {_format_decimal(market_total)} "
            f"{escape(currency)}"
        )
        pnl_line = (
            f"<b>Нереализованный P&amp;L:</b> {_format_signed(unrealized_total)} "
            f"{escape(currency)}"
        )
        percent = format_percent(ratio) if ratio is not None else None
        if percent:
            pnl_line += f" ({percent})"
        lines.append(pnl_line)
    else:
        lines.append("<b>Рыночная стоимость:</b> недоступна")

    lines.append(
        f"<b>Реализованный P&amp;L</b> (по открытым): "
        f"{_format_decimal(realized)} {escape(currency)}"
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
        side = SIDE_LABELS.get(tx.side, tx.side)
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
