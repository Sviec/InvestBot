"""Валидация пользовательского ввода.

Любая строка от пользователя доходит до внешнего HTTP-запроса (yfinance),
поэтому она проверяется до выхода из хендлера: сначала по длине, затем по
шаблону. Разбор сделки портфеля тоже здесь: формат один для меню и для
карточки компании.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.errors import ValidationError
from app.utils.i18n import t

MAX_TICKER_LENGTH = 15
MAX_PLATFORM_LENGTH = 50
# Латиница, цифры, точка и дефис покрывают биржевые тикеры (BRK-B, SBER.ME),
# ведущий «^» — биржевые индексы (^GSPC).
TICKER_PATTERN = re.compile(r"^\^?[A-Z0-9][A-Z0-9.\-]{0,13}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SIDES = frozenset({"BUY", "SELL"})


def _trade_hint() -> str:
    return t("validators.trade.hint", example=t("validators.trade.example"))


@dataclass(frozen=True, slots=True)
class ParsedTrade:
    """Разобранная строка сделки для передачи в репозиторий."""

    ticker: str
    quantity: Decimal
    price: Decimal
    traded_at: date
    side: str
    platform: str | None = None


def normalize_ticker(raw: str | None) -> str:
    """Приводит тикер к каноническому виду и проверяет его.

    :raises ValidationError: если ввод пустой, слишком длинный или содержит
        недопустимые символы
    """
    if not raw:
        raise ValidationError(t("validators.ticker.empty"))

    candidate = raw.strip().upper()
    if not candidate:
        raise ValidationError(t("validators.ticker.empty"))
    if len(candidate) > MAX_TICKER_LENGTH:
        raise ValidationError(t("validators.ticker.too_long", max=MAX_TICKER_LENGTH))
    if not TICKER_PATTERN.match(candidate):
        raise ValidationError(t("validators.ticker.pattern"))
    return candidate


def parse_entity_id(raw: str, *, entity: str) -> int:
    """Разбирает числовой идентификатор, подставленный в путь навигации."""
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(t("validators.entity_id.invalid", entity=entity)) from exc
    if value <= 0:
        raise ValidationError(t("validators.entity_id.invalid", entity=entity))
    return value


def parse_trade(raw: str | None) -> ParsedTrade:
    """Разбирает сделку из одной строки.

    Обязательны тикер, количество и цена. Дата по умолчанию — сегодня,
    сторона — buy, площадка необязательна. Количество и цена — `Decimal`.

    :raises ValidationError: при мусорном или неполном вводе
    """
    if not raw or not raw.strip():
        raise ValidationError(_trade_hint())

    tokens = raw.split()
    if len(tokens) < 3:
        raise ValidationError(_trade_hint())

    try:
        ticker = normalize_ticker(tokens[0])
    except ValidationError as exc:
        raise ValidationError(f"{exc.user_message} {_trade_hint()}") from exc
    quantity = _parse_positive_decimal(
        tokens[1], label=t("validators.trade.label.quantity")
    )
    price = _parse_positive_decimal(tokens[2], label=t("validators.trade.label.price"))

    traded_at = date.today()
    side = "BUY"
    platform: str | None = None
    rest = tokens[3:]
    index = 0

    if index < len(rest) and _DATE_PATTERN.match(rest[index]):
        traded_at = _parse_iso_date(rest[index])
        index += 1

    if index < len(rest) and rest[index].upper() in _SIDES:
        side = rest[index].upper()
        index += 1

    if index < len(rest):
        platform = rest[index].strip()
        if not platform or len(platform) > MAX_PLATFORM_LENGTH:
            raise ValidationError(
                t(
                    "validators.trade.platform_too_long",
                    max=MAX_PLATFORM_LENGTH,
                    hint=_trade_hint(),
                )
            )
        index += 1

    if index < len(rest):
        raise ValidationError(_trade_hint())

    return ParsedTrade(
        ticker=ticker,
        quantity=quantity,
        price=price,
        traded_at=traded_at,
        side=side,
        platform=platform,
    )


def _parse_positive_decimal(raw: str, *, label: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValidationError(
            t("validators.trade.bad_number", label=label, hint=_trade_hint())
        ) from exc
    if value <= 0:
        raise ValidationError(
            t(
                "validators.trade.must_be_positive",
                label=label.capitalize(),
                hint=_trade_hint(),
            )
        )
    return value


def _parse_iso_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError(
            t("validators.trade.bad_date", hint=_trade_hint())
        ) from exc
