"""Хендлеры Telegram.

Порядок роутеров важен: `fallback` регистрируется последним и ловит всё, что
не разобрали остальные.
"""

from functools import lru_cache

from aiogram import Router

from app.handlers import (
    analysis,
    company,
    fallback,
    forecast,
    main_menu,
    portfolio,
    profile,
    reference,
    ticker_input,
)


@lru_cache(maxsize=1)
def build_router() -> Router:
    """Собирает единый роутер приложения.

    Роутеры модулей — объекты уровня модуля, повторно включить их в другой
    родительский роутер нельзя, поэтому результат кешируется.
    """
    root = Router(name="root")
    root.include_router(main_menu.router)
    root.include_router(analysis.router)
    root.include_router(company.router)
    root.include_router(profile.router)
    root.include_router(portfolio.router)
    root.include_router(forecast.router)
    root.include_router(reference.router)
    root.include_router(ticker_input.router)
    root.include_router(fallback.router)
    return root


__all__ = ["build_router"]
