"""Репозиторий журнала сделок и позиций портфеля."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from itertools import groupby
from operator import attrgetter
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.portfolio import PortfolioTransaction
from app.repositories.base import BaseRepository
from app.repositories.dto import (
    AddTransactionResult,
    DeleteTransactionResult,
    PositionDTO,
    TransactionDTO,
)
from app.services.positions import (
    InsufficientSharesError,
    Side,
    TradeInput,
    compute_position,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
# Для ещё не вставленной сделки: после insert id будет больше всех текущих.
_PENDING_ID = 2**31 - 1


class PortfolioRepository(BaseRepository[PortfolioTransaction]):
    def __init__(self) -> None:
        super().__init__(PortfolioTransaction)

    def add_transaction(
        self,
        user_id: int,
        ticker: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        traded_at: date,
        *,
        fee: Decimal = _ZERO,
        currency: str = "USD",
        platform: str | None = None,
        note: str | None = None,
    ) -> AddTransactionResult:
        """Добавляет сделку в журнал.

        Продажа проверяется проходом по уже сохранённым сделкам тикера плюс
        новая (в порядке `traded_at`, `id`): отрицательная позиция не допускается.
        """
        normalized = ticker.strip().upper()
        normalized_side = side.strip().upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError(f"недопустимая сторона сделки: {side!r}")
        if quantity <= _ZERO or price < _ZERO or fee < _ZERO:
            raise ValueError(
                "количество должно быть > 0, цена и комиссия — неотрицательными"
            )

        def _operation(session: Session) -> AddTransactionResult:
            company_id = session.execute(
                select(Company.id).where(Company.ticker == normalized)
            ).scalar_one_or_none()
            if company_id is None:
                return AddTransactionResult.COMPANY_NOT_FOUND

            if normalized_side == "SELL":
                existing = session.execute(
                    select(
                        PortfolioTransaction.id,
                        PortfolioTransaction.traded_at,
                        PortfolioTransaction.side,
                        PortfolioTransaction.quantity,
                        PortfolioTransaction.price,
                        PortfolioTransaction.fee,
                    ).where(
                        PortfolioTransaction.user_id == user_id,
                        PortfolioTransaction.company_id == company_id,
                    )
                ).all()
                ordered = sorted(
                    [
                        *(
                            (
                                row.traded_at,
                                row.id,
                                TradeInput(
                                    side=cast(Side, row.side),
                                    quantity=Decimal(row.quantity),
                                    price=Decimal(row.price),
                                    fee=Decimal(row.fee),
                                ),
                            )
                            for row in existing
                        ),
                        (
                            traded_at,
                            _PENDING_ID,
                            TradeInput(
                                side="SELL",
                                quantity=quantity,
                                price=price,
                                fee=fee,
                            ),
                        ),
                    ],
                    key=lambda item: (item[0], item[1]),
                )
                try:
                    compute_position([item[2] for item in ordered])
                except InsufficientSharesError:
                    return AddTransactionResult.NOT_ENOUGH_SHARES

            session.add(
                PortfolioTransaction(
                    user_id=user_id,
                    company_id=company_id,
                    side=normalized_side,
                    quantity=quantity,
                    price=price,
                    fee=fee,
                    currency=currency.strip().upper(),
                    traded_at=traded_at,
                    platform=platform,
                    note=note,
                )
            )
            return AddTransactionResult.ADDED

        return self._write(_operation, "add_transaction")

    def list_transactions(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 500,
    ) -> list[TransactionDTO]:
        """Сделки пользователя от новых к старым, с пагинацией."""

        def _operation(session: Session) -> list[TransactionDTO]:
            rows = session.execute(
                select(
                    PortfolioTransaction.id,
                    Company.ticker,
                    PortfolioTransaction.side,
                    PortfolioTransaction.quantity,
                    PortfolioTransaction.price,
                    PortfolioTransaction.fee,
                    PortfolioTransaction.currency,
                    PortfolioTransaction.traded_at,
                    PortfolioTransaction.platform,
                    PortfolioTransaction.note,
                    PortfolioTransaction.created_at,
                )
                .join(Company, Company.id == PortfolioTransaction.company_id)
                .where(PortfolioTransaction.user_id == user_id)
                .order_by(
                    PortfolioTransaction.traded_at.desc(),
                    PortfolioTransaction.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            ).all()
            return [
                TransactionDTO(
                    id=row.id,
                    ticker=row.ticker,
                    side=row.side,
                    quantity=Decimal(row.quantity),
                    price=Decimal(row.price),
                    fee=Decimal(row.fee),
                    currency=row.currency,
                    traded_at=row.traded_at,
                    platform=row.platform,
                    note=row.note,
                    created_at=row.created_at,
                )
                for row in rows
            ]

        return self._read(_operation, "list_transactions")

    def delete_transaction(
        self, user_id: int, transaction_id: int
    ) -> DeleteTransactionResult:
        """Удаляет сделку пользователя по идентификатору."""

        def _operation(session: Session) -> DeleteTransactionResult:
            result = session.execute(
                delete(PortfolioTransaction).where(
                    PortfolioTransaction.id == transaction_id,
                    PortfolioTransaction.user_id == user_id,
                )
            )
            if result.rowcount:
                return DeleteTransactionResult.DELETED
            return DeleteTransactionResult.NOT_FOUND

        return self._write(_operation, "delete_transaction")

    def list_positions(self, user_id: int, *, limit: int = 500) -> list[PositionDTO]:
        """Открытые позиции пользователя (количество > 0), по тикеру.

        Средняя цена и реализованный P&L считаются в Python по сделкам,
        упорядоченным по `traded_at` и `id`.
        """

        def _operation(session: Session) -> list[PositionDTO]:
            rows = session.execute(
                select(
                    PortfolioTransaction.company_id,
                    PortfolioTransaction.side,
                    PortfolioTransaction.quantity,
                    PortfolioTransaction.price,
                    PortfolioTransaction.fee,
                    PortfolioTransaction.currency,
                    PortfolioTransaction.traded_at,
                    PortfolioTransaction.id,
                    Company.ticker,
                    Company.name,
                    Company.sector_id,
                    Company.industry_id,
                )
                .join(Company, Company.id == PortfolioTransaction.company_id)
                .where(PortfolioTransaction.user_id == user_id)
                .order_by(
                    Company.ticker,
                    PortfolioTransaction.traded_at,
                    PortfolioTransaction.id,
                )
            ).all()

            positions: list[PositionDTO] = []
            for _ticker, group_iter in groupby(rows, key=attrgetter("ticker")):
                group = list(group_iter)
                trades = [
                    TradeInput(
                        side=cast(Side, row.side),
                        quantity=Decimal(row.quantity),
                        price=Decimal(row.price),
                        fee=Decimal(row.fee),
                    )
                    for row in group
                ]
                state = compute_position(trades)
                if state.quantity <= _ZERO:
                    continue
                first = group[0]
                positions.append(
                    PositionDTO(
                        ticker=first.ticker,
                        name=first.name,
                        quantity=state.quantity,
                        average_price=state.average_price,
                        invested=state.invested,
                        realized_pnl=state.realized_pnl,
                        currency=first.currency,
                        sector_id=first.sector_id,
                        industry_id=first.industry_id,
                    )
                )
                if len(positions) >= limit:
                    break
            return positions

        return self._read(_operation, "list_positions")
