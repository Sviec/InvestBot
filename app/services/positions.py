"""Расчёт позиций по журналу сделок методом средней стоимости.

Чистая функция без БД: репозиторий передаёт упорядоченную последовательность
сделок, а здесь получается количество, средняя цена, вложения и реализованный
P&L. Продажа сверх остатка — ошибка, а не отрицательная позиция.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Sequence

ZERO = Decimal("0")
Side = Literal["BUY", "SELL"]


class InsufficientSharesError(ValueError):
    """Продажа превышает текущий остаток по позиции."""


@dataclass(frozen=True, slots=True)
class TradeInput:
    """Одна сделка для последовательного прохода."""

    side: Side
    quantity: Decimal
    price: Decimal
    fee: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class PositionState:
    """Состояние позиции после прохода по сделкам."""

    quantity: Decimal
    average_price: Decimal
    invested: Decimal
    realized_pnl: Decimal


def compute_position(trades: Sequence[TradeInput]) -> PositionState:
    """Агрегирует сделки в позицию методом средней стоимости.

    Покупка увеличивает количество; комиссия входит в себестоимость и поднимает
    среднюю цену. Продажа уменьшает количество, средняя цена остатка не меняется;
    комиссия продажи уменьшает реализованный P&L. Количество и цены — `Decimal`.
    """
    quantity = ZERO
    average_price = ZERO
    invested = ZERO
    realized_pnl = ZERO

    for trade in trades:
        qty = trade.quantity
        if qty <= ZERO:
            raise ValueError("количество сделки должно быть положительным")

        if trade.side == "BUY":
            cost = qty * trade.price + trade.fee
            quantity += qty
            invested += cost
            average_price = invested / quantity
            continue

        if qty > quantity:
            raise InsufficientSharesError(
                f"продажа {qty} при остатке {quantity}"
            )

        cost_basis = qty * average_price
        proceeds = qty * trade.price - trade.fee
        realized_pnl += proceeds - cost_basis
        quantity -= qty
        invested -= cost_basis
        if quantity == ZERO:
            # После полного закрытия не оставляем хвост от деления Decimal.
            average_price = ZERO
            invested = ZERO

    return PositionState(
        quantity=quantity,
        average_price=average_price,
        invested=invested,
        realized_pnl=realized_pnl,
    )
