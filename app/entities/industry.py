"""Отрасль как источник рыночных данных."""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from app.core.errors import NoDataError
from app.data.config import get_settings
from app.entities.base import fetch
from app.entities.formatting import format_entities_table, format_overview
from app.entities.session import get_market_session

TOP_LIMIT = 10

# Предпочтительные метрики для столбчатой диаграммы (порядок важен).
_CHART_METRIC_HINTS = (
    "market weight",
    "marketweight",
    "ytd return",
    "return",
    "growth",
    "perf",
    "change",
    "pe",
)


class Industry:
    """Обёртка над `yfinance.Industry` с кешированием и понятными ошибками."""

    def __init__(self, key: str, *, name: str | None = None) -> None:
        self.key = key.strip().lower()
        if not self.key:
            raise NoDataError(user_message="Отрасль не найдена в справочнике.")
        # Имя из БД передаёт хендлер: у yf.Industry.name отдельный запрос вне кеша.
        self._name = name.strip() if name and name.strip() else None
        self._yf = yf.Industry(self.key, session=get_market_session())

    def __repr__(self) -> str:
        return f"<Industry {self.key}>"

    def _frame(self, attribute: str) -> pd.DataFrame:
        def _load() -> pd.DataFrame:
            frame = getattr(self._yf, attribute)
            if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
                raise NoDataError(user_message="По этой отрасли нет данных.")
            return frame

        return fetch(
            f"industry:{attribute}:{self.key}",
            _load,
            description=f"{attribute} отрасли {self.key}",
            ttl=get_settings().market_cache_ttl_rankings,
        )

    def top_companies(self) -> pd.DataFrame:
        return self._frame("top_companies")

    def top_growth_companies(self) -> pd.DataFrame:
        return self._frame("top_growth_companies")

    def top_performing_companies(self) -> pd.DataFrame:
        return self._frame("top_performing_companies")

    def format_overview(self) -> str:
        def _load() -> dict[str, object]:
            overview = self._yf.overview
            if not overview:
                raise NoDataError(user_message="Сводка по отрасли недоступна.")
            return dict(overview)

        overview = fetch(
            f"industry:overview:{self.key}",
            _load,
            description=f"обзор отрасли {self.key}",
            ttl=get_settings().market_cache_ttl_overview,
        )
        return format_overview(
            title=f"Отрасль: {self._display_name()}",
            overview=overview,
            include_industries=False,
        )

    def format_top_companies(self) -> str:
        return format_entities_table(
            self.top_companies(),
            title=f"Топ компаний отрасли {self._display_name()}",
            limit=TOP_LIMIT,
        )

    def format_top_growth_companies(self) -> str:
        return format_entities_table(
            self.top_growth_companies(),
            title=f"Быстрорастущие компании отрасли {self._display_name()}",
            limit=TOP_LIMIT,
        )

    def format_top_performing_companies(self) -> str:
        return format_entities_table(
            self.top_performing_companies(),
            title=f"Лучшие по динамике компании отрасли {self._display_name()}",
            limit=TOP_LIMIT,
        )

    def chart_metric(self, frame: pd.DataFrame) -> pd.Series:
        """Числовой ряд для столбчатой диаграммы: индекс — тикер."""
        if frame is None or frame.empty:
            raise NoDataError(user_message="Список пуст.")
        data = frame.head(TOP_LIMIT)
        numeric = data.select_dtypes(include="number")
        if numeric.empty:
            raise NoDataError(user_message="Нет числовой метрики для диаграммы.")

        column = numeric.columns[0]
        for hint in _CHART_METRIC_HINTS:
            for candidate in numeric.columns:
                if hint in str(candidate).lower().replace("_", " "):
                    column = candidate
                    break
            else:
                continue
            break

        series = numeric[column].copy()
        series.index = [str(index) for index in data.index]
        series.name = str(column)
        series = series.dropna()
        if series.empty:
            raise NoDataError(user_message="Нет числовой метрики для диаграммы.")
        return series

    def _display_name(self) -> str:
        return self._name or self.key

    @property
    def display_name(self) -> str:
        return self._display_name()
