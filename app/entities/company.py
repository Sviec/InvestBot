"""Компания как источник рыночных данных."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from app.core.errors import NoDataError, TickerNotFoundError
from app.entities.base import fetch
from app.entities.session import get_market_session
from app.utils.text import escape, format_number, format_percent, join_lines, truncate
from app.utils.validators import normalize_ticker

logger = logging.getLogger(__name__)

MAX_DIVIDEND_ROWS = 10
MAX_NEWS_ITEMS = 8


class Company:
    """Доступ к данным компании по тикеру.

    Объект дешёвый: сетевых запросов в конструкторе нет, `info` загружается
    при первом обращении и переиспользуется из кеша.
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = normalize_ticker(ticker)
        self._yf = yf.Ticker(self.ticker, session=get_market_session())

    def __repr__(self) -> str:
        return f"<Company {self.ticker}>"

    # --- загрузка ---

    def _load_info(self) -> dict[str, Any]:
        data = self._yf.info
        # yfinance на несуществующий тикер отвечает почти пустым словарём
        # вместо исключения, поэтому проверяем содержимое.
        if not isinstance(data, dict) or not (
            data.get("symbol") or data.get("shortName") or data.get("longName")
        ):
            raise TickerNotFoundError(self.ticker)
        return data

    @property
    def info(self) -> dict[str, Any]:
        return fetch(
            f"company:info:{self.ticker}",
            self._load_info,
            description=f"сведения о {self.ticker}",
        )

    def _load_frame(self, attribute: str) -> pd.DataFrame:
        frame = getattr(self._yf, attribute)
        if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
            raise NoDataError(
                f"{attribute} для {self.ticker} пуст",
                user_message="Провайдер не публикует эти данные по выбранной компании.",
            )
        return frame

    def _frame(self, attribute: str) -> pd.DataFrame:
        return fetch(
            f"company:{attribute}:{self.ticker}",
            lambda: self._load_frame(attribute),
            description=f"{attribute} для {self.ticker}",
        )

    # --- отчётные таблицы ---

    def financials(self, *, quarterly: bool) -> pd.DataFrame:
        return self._frame("quarterly_financials" if quarterly else "financials")

    def balance_sheet(self, *, quarterly: bool) -> pd.DataFrame:
        return self._frame("quarterly_balance_sheet" if quarterly else "balance_sheet")

    def cash_flow(self, *, quarterly: bool) -> pd.DataFrame:
        return self._frame("quarterly_cashflow" if quarterly else "cashflow")

    def income_statement(self, *, quarterly: bool) -> pd.DataFrame:
        return self._frame("quarterly_income_stmt" if quarterly else "income_stmt")

    def major_holders(self) -> pd.DataFrame:
        return self._frame("major_holders")

    def institutional_holders(self) -> pd.DataFrame:
        return self._frame("institutional_holders")

    def price_history(self, period: str = "max") -> pd.Series:
        def _load() -> pd.Series:
            history = self._yf.history(period=period)
            if history is None or history.empty or "Close" not in history:
                raise NoDataError(
                    f"История котировок {self.ticker} пуста",
                    user_message="По этой компании нет истории котировок.",
                )
            return history["Close"]

        return fetch(
            f"company:history:{period}:{self.ticker}",
            _load,
            description=f"котировки {self.ticker} за {period}",
        )

    # --- форматирование ---

    @property
    def display_name(self) -> str:
        info = self.info
        return str(info.get("longName") or info.get("shortName") or self.ticker)

    def format_info(self) -> str:
        info = self.info
        fields = (
            ("Страна", info.get("country")),
            ("Город", info.get("city")),
            ("Сектор", info.get("sector")),
            ("Индустрия", info.get("industry")),
            ("Капитализация", format_number(info.get("marketCap"), digits=0)),
            ("Сотрудников", format_number(info.get("fullTimeEmployees"), digits=0)),
            ("Сайт", info.get("website")),
        )
        lines = [
            f"<b>{escape(label)}:</b> {escape(value)}"
            for label, value in fields
            if value not in (None, "")
        ]
        if not lines:
            raise NoDataError(user_message="По этой компании нет справочных данных.")
        return join_lines([f"<b>{escape(self.display_name)}</b>", "", *lines])

    def format_description(self) -> str:
        summary = self.info.get("longBusinessSummary")
        if not summary:
            raise NoDataError(user_message="Описание компании недоступно.")
        return f"<b>{escape(self.display_name)}</b>\n\n{escape(summary)}"

    def format_dividends(self) -> str:
        def _load() -> pd.Series:
            dividends = self._yf.dividends
            if dividends is None or len(dividends) == 0:
                raise NoDataError(user_message="Компания не выплачивает дивиденды.")
            return dividends

        dividends = fetch(
            f"company:dividends:{self.ticker}",
            _load,
            description=f"дивиденды {self.ticker}",
        )
        recent = dividends.tail(MAX_DIVIDEND_ROWS).iloc[::-1]
        lines = [
            f"{index.date().isoformat()} — {format_number(value)}"
            for index, value in recent.items()
        ]
        return join_lines([f"<b>Последние выплаты, {escape(self.ticker)}</b>", "", *lines])

    def format_multipliers(self) -> str:
        info = self.info
        net_debt_to_ebitda = self._net_debt_to_ebitda(info)
        rows = (
            ("Trailing P/E", format_number(info.get("trailingPE"))),
            ("P/S", format_number(info.get("priceToSalesTrailing12Months"))),
            ("P/B", format_number(info.get("priceToBook"))),
            ("TotalDebt/Equity", format_number(info.get("debtToEquity"))),
            ("NetDebt/EBITDA", format_number(net_debt_to_ebitda)),
            ("Current Ratio", format_number(info.get("currentRatio"))),
            ("ROE", format_percent(info.get("returnOnEquity"))),
            ("ROA", format_percent(info.get("returnOnAssets"))),
            ("EV/EBITDA", format_number(info.get("enterpriseToEbitda"))),
        )
        lines = [f"{escape(label)}: <b>{value}</b>" for label, value in rows if value]
        if not lines:
            raise NoDataError(user_message="Мультипликаторы по этой компании недоступны.")
        return join_lines(
            [f"<b>Мультипликаторы {escape(self.display_name)}</b>", "", *lines]
        )

    @staticmethod
    def _net_debt_to_ebitda(info: dict[str, Any]) -> float | None:
        total_debt = info.get("totalDebt")
        total_cash = info.get("totalCash")
        ebitda = info.get("ebitda")
        try:
            if None in (total_debt, total_cash, ebitda) or float(ebitda) == 0:
                return None
            return (float(total_debt) - float(total_cash)) / float(ebitda)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def format_news(self) -> str:
        def _load() -> list[dict[str, Any]]:
            news = self._yf.news
            if not news:
                raise NoDataError(user_message="Свежих новостей по компании нет.")
            return list(news)

        news = fetch(
            f"company:news:{self.ticker}",
            _load,
            description=f"новости {self.ticker}",
        )

        lines: list[str] = []
        for item in news[:MAX_NEWS_ITEMS]:
            content = item.get("content") if isinstance(item, dict) else None
            if not isinstance(content, dict):
                continue
            title = content.get("title")
            url = (content.get("canonicalUrl") or {}).get("url")
            if not title:
                continue
            lines.append(
                f'• <a href="{escape(url)}">{escape(truncate(title, 150))}</a>'
                if url
                else f"• {escape(truncate(title, 150))}"
            )
        if not lines:
            raise NoDataError(user_message="Свежих новостей по компании нет.")
        return join_lines(["<b>Последние новости (на английском)</b>", "", *lines])
