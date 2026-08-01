"""Сектор экономики как источник рыночных данных."""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from app.core.errors import NoDataError
from app.data.config import get_settings
from app.entities.base import fetch
from app.entities.formatting import format_entities_table, format_overview
from app.entities.session import get_market_session
from app.utils.text import escape, join_lines

TOP_COMPANIES_LIMIT = 15
TOP_ETFS_LIMIT = 15


class Sector:
    """Обёртка над `yfinance.Sector` с кешированием и понятными ошибками."""

    def __init__(self, key: str, *, name: str | None = None) -> None:
        self.key = key.strip().lower()
        if not self.key:
            raise NoDataError(user_message="Сектор не найден в справочнике.")
        # Имя из БД передаёт хендлер: у yf.Sector.name отдельный запрос вне кеша.
        self._name = name.strip() if name and name.strip() else None
        self._yf = yf.Sector(self.key, session=get_market_session())

    def __repr__(self) -> str:
        return f"<Sector {self.key}>"

    def _overview(self) -> dict[str, object]:
        def _load() -> dict[str, object]:
            overview = self._yf.overview
            if not overview:
                raise NoDataError(user_message="Сводка по сектору недоступна.")
            return dict(overview)

        return fetch(
            f"sector:overview:{self.key}",
            _load,
            description=f"обзор сектора {self.key}",
            ttl=get_settings().market_cache_ttl_overview,
        )

    def _frame(self, attribute: str) -> pd.DataFrame:
        def _load() -> pd.DataFrame:
            frame = getattr(self._yf, attribute)
            if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
                raise NoDataError(user_message="По этому сектору нет данных.")
            return frame

        return fetch(
            f"sector:{attribute}:{self.key}",
            _load,
            description=f"{attribute} сектора {self.key}",
            ttl=get_settings().market_cache_ttl_rankings,
        )

    def industries(self) -> pd.DataFrame:
        """Отрасли сектора с рыночным весом.

        Один запрос к провайдеру; кеш — ярус обзора: состав отраслей меняется
        редко, как и сводка сектора.
        """

        def _load() -> pd.DataFrame:
            frame = self._yf.industries
            if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
                raise NoDataError(user_message="Список отраслей сектора недоступен.")
            return frame

        return fetch(
            f"sector:industries:{self.key}",
            _load,
            description=f"отрасли сектора {self.key}",
            ttl=get_settings().market_cache_ttl_overview,
        )

    def top_etfs(self) -> dict[str, str]:
        def _load() -> dict[str, str]:
            etfs = self._yf.top_etfs
            if not etfs:
                raise NoDataError(user_message="По этому сектору нет ETF.")
            return dict(etfs)

        return fetch(
            f"sector:top_etfs:{self.key}",
            _load,
            description=f"ETF сектора {self.key}",
            ttl=get_settings().market_cache_ttl_rankings,
        )

    def leading_etf_ticker(self) -> str:
        """Тикер первого ETF из уже кешируемого `top_etfs`."""
        etfs = self.top_etfs()
        ticker = next(iter(etfs), None)
        if not ticker:
            raise NoDataError(user_message="По этому сектору нет ETF.")
        return str(ticker)

    def format_overview(self) -> str:
        overview = self._overview()
        return format_overview(
            title=f"Сектор: {self._display_name()}",
            overview=overview,
            include_industries=True,
        )

    def format_top_companies(self) -> str:
        return format_entities_table(
            self._frame("top_companies"),
            title=f"Топ компаний сектора {self._display_name()}",
            limit=TOP_COMPANIES_LIMIT,
        )

    def format_top_etfs(self) -> str:
        etfs = self.top_etfs()
        lines = [
            f"<b>{escape(ticker)}</b> — {escape(name)}"
            for ticker, name in list(etfs.items())[:TOP_ETFS_LIMIT]
        ]
        return join_lines(
            [f"<b>Топ ETF сектора {escape(self._display_name())}</b>", "", *lines]
        )

    def _display_name(self) -> str:
        return self._name or self.key

    @property
    def display_name(self) -> str:
        return self._display_name()
