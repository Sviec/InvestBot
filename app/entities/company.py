"""Компания как источник рыночных данных."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

import pandas as pd
import yfinance as yf

from app.core.errors import (
    MarketDataError,
    MarketDataUnavailableError,
    NoDataError,
    TickerNotFoundError,
)
from app.data.config import get_settings
from app.entities.base import fetch, get_cache
from app.entities.formatting import format_key_metrics
from app.entities.fundamentals import (
    free_cash_flow_from_cashflow,
    growth_from_income,
    margins_from_income,
    next_earnings_date,
    normalize_analyst_targets,
)
from app.entities.probe import SymbolStatus, probe_symbol
from app.entities.session import get_market_session
from app.utils.i18n import t
from app.utils.text import escape, format_number, format_percent, join_lines, truncate
from app.utils.validators import normalize_ticker

logger = logging.getLogger(__name__)

MAX_DIVIDEND_ROWS = 10
MAX_NEWS_ITEMS = 8

# Периоды, которые ещё имеет смысл обновлять чаще внутри дня.
_SHORT_HISTORY_PERIODS = frozenset({"1d", "5d", "7d", "1wk", "2wk", "1mo", "3mo"})


def _quote_cache_key(ticker: str) -> str:
    return f"market:quote:{ticker}"


def _load_quotes_from_provider(tickers: Sequence[str]) -> dict[str, Decimal]:
    """Один запрос к провайдеру за последними ценами пачки тикеров.

    Вынесено из `Company.quotes`, чтобы тесты подменяли провайдера без сети.
    Ошибка по всей пачке возвращает пустой словарь: вызывающий код отдаст
    устаревший кеш по тем тикерам, где он есть.
    """
    if not tickers:
        return {}

    symbols = list(tickers)
    try:
        frame = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            # Уже внутри рабочего потока; вложенный пул yfinance только мешает.
            threads=False,
            session=get_market_session(),
        )
    except Exception as exc:  # noqa: BLE001 — пачка не должна ронять экран портфеля
        logger.warning(
            "Пакетная загрузка котировок не удалась (%d тикеров): %s: %s",
            len(symbols),
            type(exc).__name__,
            exc,
        )
        return {}

    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return {}

    single = len(symbols) == 1
    result: dict[str, Decimal] = {}
    for ticker in symbols:
        price = _extract_last_close(frame, ticker, single=single)
        if price is not None:
            result[ticker] = price
    return result


def _extract_last_close(
    frame: pd.DataFrame, ticker: str, *, single: bool
) -> Decimal | None:
    """Достаёт последнее Close из ответа `yf.download` для одного тикера."""
    try:
        series: pd.Series | None = None
        if single and "Close" in frame.columns:
            series = frame["Close"]
        elif isinstance(frame.columns, pd.MultiIndex):
            levels = [str(level) for level in frame.columns.get_level_values(0)]
            if ticker in levels:
                series = frame[ticker]["Close"]
            elif "Close" in levels:
                series = frame["Close"][ticker]
        if series is None:
            return None
        clean = series.dropna()
        if clean.empty:
            return None
        # Через str, чтобы не тащить двоичную погрешность float в Decimal.
        return Decimal(str(clean.iloc[-1]))
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError):
        return None


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

    @staticmethod
    def quotes(tickers: Sequence[str]) -> dict[str, Decimal]:
        """Пакетная загрузка последних цен.

        Кеш ведётся по каждому тикеру (`market:quote:TICKER`), поэтому повторный
        запрос портфеля почти бесплатен, а в провайдера уходят только промахи.
        Вся пачка — один вызов провайдера. Тикер без цены просто отсутствует
        в результате: экран портфеля показывает позицию без рыночной оценки.
        """
        settings = get_settings()
        cache = get_cache()
        ttl = settings.market_cache_ttl_quote

        result: dict[str, Decimal] = {}
        missing: list[str] = []
        seen: set[str] = set()

        for raw in tickers:
            ticker = normalize_ticker(raw)
            if ticker in seen:
                continue
            seen.add(ticker)
            key = _quote_cache_key(ticker)
            cached = cache.get(key)
            if cached is not None:
                if isinstance(cached, MarketDataError):
                    continue
                result[ticker] = cached  # type: ignore[assignment]
                continue
            missing.append(ticker)

        if not missing:
            return result

        fetched = _load_quotes_from_provider(missing)
        got_any = bool(fetched)

        for ticker in missing:
            key = _quote_cache_key(ticker)
            price = fetched.get(ticker)
            if price is not None:
                cache.set(key, price, ttl=ttl)
                result[ticker] = price
                continue

            stale = cache.get_stale(key)
            if stale is not None and not isinstance(stale, MarketDataError):
                result[ticker] = stale  # type: ignore[assignment]
                continue

            # Пакет ответил хотя бы по одному тикеру — по этому цены нет
            # осознанно, кешируем отрицательный результат коротко.
            if got_any:
                cache.set(
                    key,
                    NoDataError(f"нет котировки для {ticker}"),
                    ttl=settings.market_negative_ttl,
                )

        return result

    # --- загрузка ---

    def _load_info(self) -> dict[str, Any]:
        data = self._yf.info
        # yfinance на несуществующий тикер отвечает почти пустым словарём
        # вместо исключения, поэтому проверяем содержимое.
        if isinstance(data, dict) and (
            data.get("symbol") or data.get("shortName") or data.get("longName")
        ):
            return data
        # Пустой ответ сам по себе ничего не означает: так выглядят и сбой
        # провайдера, и несуществующий тикер, и бумага без профиля. Решение
        # принимается по отдельному запросу к chart-эндпоинту.
        status = probe_symbol(self.ticker)
        if status is SymbolStatus.MISSING:
            raise TickerNotFoundError(self.ticker)
        if status is SymbolStatus.PRESENT:
            raise NoDataError(
                f"Профиль {self.ticker} пуст при доступных котировках",
                user_message=t(
                    "errors.company.profile_empty",
                    ticker=escape(self.ticker),
                ),
            )
        raise MarketDataUnavailableError(f"Провайдер не вернул данные по {self.ticker}")

    @property
    def info(self) -> dict[str, Any]:
        return fetch(
            f"company:info:{self.ticker}",
            self._load_info,
            description=f"сведения о {self.ticker}",
            ttl=get_settings().market_cache_ttl_info,
        )

    def _load_frame(self, attribute: str) -> pd.DataFrame:
        frame = getattr(self._yf, attribute)
        if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
            raise NoDataError(
                f"{attribute} для {self.ticker} пуст",
                user_message=t("errors.company.attribute_unavailable"),
            )
        return frame

    def _frame(self, attribute: str) -> pd.DataFrame:
        return fetch(
            f"company:{attribute}:{self.ticker}",
            lambda: self._load_frame(attribute),
            description=f"{attribute} для {self.ticker}",
            ttl=get_settings().market_cache_ttl_fundamentals,
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

    def analyst_price_targets(self) -> dict[str, float]:
        """Целевые цены аналитиков. Пустой словарь, если провайдер молчит."""

        def _load() -> dict[str, float]:
            raw = self._yf.analyst_price_targets
            return normalize_analyst_targets(raw)

        return fetch(
            f"company:analyst_targets:{self.ticker}",
            _load,
            description=f"целевые цены {self.ticker}",
            ttl=get_settings().market_cache_ttl_analyst,
        )

    def earnings_calendar(self) -> str | None:
        """Дата следующего отчёта или None, если её нет у провайдера."""

        def _load() -> str | None:
            return next_earnings_date(self._yf.calendar)

        return fetch(
            f"company:calendar:{self.ticker}",
            _load,
            description=f"календарь отчётов {self.ticker}",
            ttl=get_settings().market_cache_ttl_analyst,
        )

    def _soft(self, loader: Any, *, description: str) -> Any:
        """Мягкая загрузка для сборного экрана: отсутствие данных не роняет остальное."""
        try:
            return loader()
        except (NoDataError, MarketDataUnavailableError, TickerNotFoundError) as exc:
            logger.info("Пропускаю блок «%s»: %s", description, exc)
            return None
        except Exception as exc:  # noqa: BLE001 — экран ключевых метрик терпим к сбоям блока
            logger.warning(
                "Пропускаю блок «%s» из-за ошибки %s: %s",
                description,
                type(exc).__name__,
                exc,
            )
            return None

    def price_history(self, period: str = "max") -> pd.Series:
        def _load() -> pd.Series:
            history = self._yf.history(period=period)
            if history is None or history.empty or "Close" not in history:
                raise NoDataError(
                    f"История котировок {self.ticker} пуста",
                    user_message=t("errors.company.no_price_history"),
                )
            return history["Close"]

        settings = get_settings()
        ttl = (
            settings.market_cache_ttl_history_short
            if period in _SHORT_HISTORY_PERIODS
            else settings.market_cache_ttl_history_long
        )
        return fetch(
            f"company:history:{period}:{self.ticker}",
            _load,
            description=f"котировки {self.ticker} за {period}",
            ttl=ttl,
        )

    def price_frame(self, period: str = "max") -> pd.DataFrame:
        """Полный OHLCV для техиндикаторов.

        Отдельный ключ кеша: графики котировок продолжают брать только Close
        через `price_history`, а OBV нужен ещё и объём.
        """

        def _load() -> pd.DataFrame:
            history = self._yf.history(period=period)
            required = {"Open", "High", "Low", "Close", "Volume"}
            if (
                history is None
                or not isinstance(history, pd.DataFrame)
                or history.empty
                or not required.issubset(history.columns)
            ):
                raise NoDataError(
                    f"OHLCV {self.ticker} пуст",
                    user_message=t("errors.company.no_price_history"),
                )
            return history.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()

        settings = get_settings()
        ttl = (
            settings.market_cache_ttl_ohlcv_short
            if period in _SHORT_HISTORY_PERIODS
            else settings.market_cache_ttl_ohlcv_long
        )
        return fetch(
            f"company:ohlcv:{period}:{self.ticker}",
            _load,
            description=f"OHLCV {self.ticker} за {period}",
            ttl=ttl,
        )

    # --- форматирование ---

    @property
    def display_name(self) -> str:
        info = self.info
        return str(info.get("longName") or info.get("shortName") or self.ticker)

    def format_info(self) -> str:
        info = self.info
        fields = (
            ("formatting.company.country", info.get("country")),
            ("formatting.company.city", info.get("city")),
            ("formatting.company.sector", info.get("sector")),
            ("formatting.company.industry", info.get("industry")),
            (
                "formatting.company.market_cap",
                format_number(info.get("marketCap"), digits=0),
            ),
            (
                "formatting.company.employees",
                format_number(info.get("fullTimeEmployees"), digits=0),
            ),
            ("formatting.company.website", info.get("website")),
        )
        lines = [
            f"<b>{escape(t(label_key))}:</b> {escape(value)}"
            for label_key, value in fields
            if value not in (None, "")
        ]
        if not lines:
            raise NoDataError(user_message=t("errors.company.no_info"))
        return join_lines([f"<b>{escape(self.display_name)}</b>", "", *lines])

    def format_description(self) -> str:
        summary = self.info.get("longBusinessSummary")
        if not summary:
            raise NoDataError(user_message=t("errors.company.no_description"))
        return f"<b>{escape(self.display_name)}</b>\n\n{escape(summary)}"

    def format_dividends(self) -> str:
        dividends = self.dividends_series()
        recent = dividends.tail(MAX_DIVIDEND_ROWS).iloc[::-1]
        lines = [
            f"{index.date().isoformat()} — {format_number(value)}"
            for index, value in recent.items()
        ]
        return join_lines(
            [
                f"<b>{t('formatting.company.dividends_title', ticker=escape(self.ticker))}</b>",
                "",
                *lines,
            ]
        )

    def dividends_series(self) -> pd.Series:
        """История дивидендных выплат на акцию (кешируется)."""

        def _load() -> pd.Series:
            dividends = self._yf.dividends
            if dividends is None or len(dividends) == 0:
                raise NoDataError(user_message=t("errors.company.no_dividends"))
            return dividends

        return fetch(
            f"company:dividends:{self.ticker}",
            _load,
            description=f"дивиденды {self.ticker}",
            ttl=get_settings().market_cache_ttl_dividends,
        )

    def format_multipliers(self) -> str:
        info = self.info
        net_debt_to_ebitda = self._net_debt_to_ebitda(info)
        rows = (
            ("formatting.multipliers.pe", format_number(info.get("trailingPE"))),
            (
                "formatting.multipliers.ps",
                format_number(info.get("priceToSalesTrailing12Months")),
            ),
            ("formatting.multipliers.pb", format_number(info.get("priceToBook"))),
            (
                "formatting.multipliers.debt_equity",
                format_number(info.get("debtToEquity")),
            ),
            (
                "formatting.multipliers.net_debt_ebitda",
                format_number(net_debt_to_ebitda),
            ),
            (
                "formatting.multipliers.current_ratio",
                format_number(info.get("currentRatio")),
            ),
            ("formatting.multipliers.roe", format_percent(info.get("returnOnEquity"))),
            ("formatting.multipliers.roa", format_percent(info.get("returnOnAssets"))),
            (
                "formatting.multipliers.ev_ebitda",
                format_number(info.get("enterpriseToEbitda")),
            ),
        )
        lines = [
            f"{escape(t(label_key))}: <b>{value}</b>" for label_key, value in rows if value
        ]
        if not lines:
            raise NoDataError(user_message=t("errors.company.no_multipliers"))
        return join_lines(
            [
                f"<b>{t('formatting.company.multipliers_title', name=escape(self.display_name))}</b>",
                "",
                *lines,
            ]
        )

    def format_key_metrics(self) -> str:
        """Сводный экран: дивиденды, маржи, рост, FCF, аналитики, календарь.

        Маржи/рост/FCF считаются из уже кешируемых income_stmt и cashflow.
        Целевые цены и дата отчёта — отдельные лёгкие запросы с TTL 6 ч;
        их отсутствие не превращает экран в список прочерков.
        """
        metrics: dict[str, object] = {}
        name = self.ticker

        info = self._soft(lambda: self.info, description=f"info {self.ticker}")
        if isinstance(info, dict):
            name = str(info.get("longName") or info.get("shortName") or self.ticker)
            for key, src in (
                ("dividend_yield", "dividendYield"),
                ("payout_ratio", "payoutRatio"),
            ):
                value = info.get(src)
                if value is not None:
                    metrics[key] = value

        income = self._soft(
            lambda: self.income_statement(quarterly=False),
            description=f"income_stmt {self.ticker}",
        )
        if isinstance(income, pd.DataFrame):
            metrics.update(margins_from_income(income))
            metrics.update(growth_from_income(income))

        cashflow = self._soft(
            lambda: self.cash_flow(quarterly=False),
            description=f"cashflow {self.ticker}",
        )
        if isinstance(cashflow, pd.DataFrame):
            fcf = free_cash_flow_from_cashflow(cashflow)
            if fcf is not None:
                metrics["free_cash_flow"] = fcf

        targets = self._soft(
            self.analyst_price_targets,
            description=f"analyst targets {self.ticker}",
        )
        if isinstance(targets, dict):
            mapping = {
                "current": "target_current",
                "low": "target_low",
                "high": "target_high",
                "mean": "target_mean",
                "median": "target_median",
            }
            for src, dest in mapping.items():
                if src in targets:
                    metrics[dest] = targets[src]

        earnings = self._soft(
            self.earnings_calendar,
            description=f"calendar {self.ticker}",
        )
        if earnings:
            metrics["next_earnings_date"] = earnings

        return format_key_metrics(
            title=t("formatting.company.key_metrics_title", name=name),
            metrics=metrics,
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
                raise NoDataError(user_message=t("errors.company.no_news"))
            return list(news)

        news = fetch(
            f"company:news:{self.ticker}",
            _load,
            description=f"новости {self.ticker}",
            ttl=get_settings().market_cache_ttl_news,
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
            raise NoDataError(user_message=t("errors.company.no_news"))
        return join_lines(
            [f"<b>{t('formatting.company.news_title')}</b>", "", *lines]
        )
