"""Общие помощники хендлеров.

Здесь собрано всё, что раньше копировалось из хендлера в хендлер: разбор пути,
вызов блокирующего кода, отрисовка экрана меню и отправка отчёта.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from aiogram import F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message
from magic_filter import MagicFilter

from app.callbacks import BaseCallback
from app.core.errors import NavigationError, ValidationError
from app.core.executor import run_blocking
from app.data.config import get_settings
from app.keyboards.make_markup import back_keyboard, items_keyboard, menu_keyboard
from app.repositories.dto import NamedItem
from app.services.reports import temporary_report
from app.utils.messaging import delete_silently, safe_edit
from app.utils.navigation import MenuNode, SEGMENT_SEPARATOR, SUFFIX_SEPARATOR, resolve
from app.utils.text import TELEGRAM_CAPTION_LIMIT, escape

logger = logging.getLogger(__name__)

_render_limiter: asyncio.Semaphore | None = None
_market_limiter: asyncio.Semaphore | None = None

# Дольше секунды — INFO, иначе DEBUG: иначе лог тонет в шуме быстрых стадий.
_SLOW_STAGE_SECONDS = 1.0

REPORT_PROGRESS = "Готовлю отчёт…"
TICKER_PROGRESS = "Проверяю тикер…"


# --- фильтры маршрутизации ---


def last_node(path: str) -> str:
    """Последний сегмент пути, который является узлом меню.

    Подставленные значения (`AAPL#tckr`, `3#pg`) пропускаются, поэтому фильтр
    экрана не ломается ни от выбора тикера, ни от перехода на другую страницу.
    """
    for segment in reversed(path.split(SEGMENT_SEPARATOR)):
        if segment and SUFFIX_SEPARATOR not in segment:
            return segment
    return ""


#: Экраны, для которых зарегистрирован хотя бы один хендлер. Наполняется при
#: импорте модулей хендлеров и проверяется тестом: новый пункт меню без
#: обработчика иначе обнаружился бы только в проде.
REGISTERED_SCREENS: set[str] = set()


def node_is(*names: str) -> MagicFilter:
    """Фильтр по текущему экрану меню."""
    expected = frozenset(names)
    REGISTERED_SCREENS.update(expected)
    return F.path.func(lambda path: last_node(path) in expected)


def has_value(suffix: str) -> MagicFilter:
    """Фильтр наличия подставленного значения указанного типа."""
    marker = f"{SUFFIX_SEPARATOR}{suffix}"
    return F.path.func(lambda path: marker in path)


# --- вызов блокирующего кода ---


async def _measured_call(
    stage: str,
    func: Callable[..., object],
    *args: object,
    description: str,
    **run_kwargs: object,
) -> object:
    """Выполняет блокирующий вызов и пишет длительность стадии в лог."""
    started = time.perf_counter()
    try:
        return await run_blocking(func, *args, description=description, **run_kwargs)
    finally:
        elapsed = time.perf_counter() - started
        log = logger.info if elapsed > _SLOW_STAGE_SECONDS else logger.debug
        log("Стадия %s «%s»: %.3f с", stage, description, elapsed)


async def db_call(func: Callable[..., object], *args: object, description: str) -> object:
    return await _measured_call(
        "db",
        func,
        *args,
        description=description,
        timeout=get_settings().db_timeout,
    )


async def market_call(
    func: Callable[..., object], *args: object, description: str, **kwargs: object
) -> object:
    return await _measured_call(
        "market",
        func,
        *args,
        description=description,
        timeout=get_settings().market_timeout,
        limiter=_market_semaphore(),
        **kwargs,
    )


def _market_semaphore() -> asyncio.Semaphore:
    """Ограничитель рыночных запросов.

    Держит часть пула потоков свободной: недоступный провайдер занимает поток
    на весь таймаут, и без ограничителя несколько таких запросов заблокировали
    бы и работу с БД.
    """
    global _market_limiter
    if _market_limiter is None:
        _market_limiter = asyncio.Semaphore(get_settings().market_concurrency)
    return _market_limiter


def _limiter() -> asyncio.Semaphore:
    global _render_limiter
    if _render_limiter is None:
        _render_limiter = asyncio.Semaphore(get_settings().render_concurrency)
    return _render_limiter


async def render_call(
    func: Callable[..., None], *args: object, description: str, **kwargs: object
) -> None:
    await _measured_call(
        "render",
        func,
        *args,
        description=description,
        timeout=get_settings().render_timeout,
        limiter=_limiter(),
        **kwargs,
    )


# --- экраны ---


async def ack(callback: CallbackQuery, text: str | None = None) -> None:
    """Снимает «часики» с кнопки до начала долгой работы.

    На устаревший callback ответить нельзя — ошибка Telegram подавляется.
    Если передан text, сообщение заменяется индикатором прогресса, чтобы
    пользователь видел, что бот ещё занят.
    """
    with suppress(TelegramAPIError):
        await callback.answer()
    if text is not None:
        await safe_edit(callback, escape(text), _current_markup(callback))


def node_for(callback_data: BaseCallback) -> MenuNode:
    return resolve(callback_data.path)


async def show_menu(
    callback: CallbackQuery,
    callback_data: BaseCallback,
    *,
    columns: int = 1,
    text: str | None = None,
) -> None:
    """Отрисовывает экран меню по текущему пути."""
    node = node_for(callback_data)
    await safe_edit(
        callback,
        text or escape(node.text),
        menu_keyboard(callback_data, node, columns=columns),
    )


async def show_result(
    callback: CallbackQuery, callback_data: BaseCallback, text: str
) -> None:
    """Показывает результат, сохраняя клавиатуру текущего экрана."""
    markup = _current_markup(callback) or back_keyboard(callback_data)
    await safe_edit(callback, text, markup)


def _current_markup(callback: CallbackQuery) -> InlineKeyboardMarkup | None:
    message = callback.message
    if isinstance(message, Message) and message.reply_markup:
        return message.reply_markup
    return None


async def show_items(
    callback: CallbackQuery,
    callback_data: BaseCallback,
    items: Sequence[tuple[str, str]],
    suffix: str,
    *,
    target: BaseCallback | None = None,
    empty_text: str,
    columns: int = 2,
) -> None:
    """Отрисовывает динамический список с пагинацией или сообщение о пустоте."""
    node = node_for(callback_data)
    if not items:
        await safe_edit(callback, escape(empty_text), back_keyboard(callback_data))
        return
    await safe_edit(
        callback,
        escape(node.text),
        items_keyboard(
            callback_data,
            items,
            suffix,
            target=target,
            page=callback_data.page,
            columns=columns,
        ),
    )


def named_items(items: Sequence[NamedItem]) -> list[tuple[str, str]]:
    return [(str(item.id), item.name) for item in items]


def ticker_items(tickers: Sequence[str]) -> list[tuple[str, str]]:
    return [(ticker, ticker) for ticker in tickers]


# --- отчёты ---


async def send_report(
    callback: CallbackQuery,
    callback_data: BaseCallback,
    *,
    render: Callable[..., None],
    description: str,
    caption: str | None = None,
) -> None:
    """Строит изображение отчёта и отправляет его, сохраняя навигацию.

    Подпись и клавиатура уходят вместе с медиа — так навигация доступна сразу
    и лишний запрос к Telegram не нужен. Если подпись длиннее лимита caption,
    она уходит отдельным сообщением. Слишком большая картинка — документом:
    Telegram не принимает фото больше 10 МБ.
    """
    message = callback.message
    if not isinstance(message, Message):
        raise NavigationError("Сообщение недоступно для обновления")

    caption_text = (
        caption
        if caption is not None
        else (message.text or escape(node_for(callback_data).text))
    )
    markup = _current_markup(callback) or back_keyboard(callback_data)
    # Caption ограничен 1024 символами; сверх лимита — откат к отдельному сообщению.
    caption_fits = len(caption_text) <= TELEGRAM_CAPTION_LIMIT

    with temporary_report() as path:
        await render_call(render, destination=path, description=description)
        size = path.stat().st_size
        logger.info("Отчёт «%s» построен, %.1f КБ", description, size / 1024)

        await delete_silently(message)
        media = FSInputFile(path, filename="report.png")
        as_document = size > get_settings().max_photo_bytes
        if as_document:
            logger.warning("Отчёт %.1f МБ, отправляю документом", size / 1024 / 1024)

        send = message.answer_document if as_document else message.answer_photo
        if caption_fits:
            await send(media, caption=caption_text, reply_markup=markup)
        else:
            await send(media)
            await message.answer(caption_text, reply_markup=markup)


def required_ticker(callback_data: BaseCallback) -> str:
    """Тикер из пути или ошибка, если путь собран некорректно."""
    ticker = callback_data.ticker
    if not ticker:
        raise ValidationError("Сначала выберите компанию.")
    return ticker


def required_id(callback_data: BaseCallback, suffix: str, *, entity: str) -> int:
    from app.utils.validators import parse_entity_id

    raw = callback_data.arg(suffix)
    if raw is None:
        raise ValidationError(f"Сначала выберите {entity}.")
    return parse_entity_id(raw, entity=entity)


HandlerType = Callable[..., Awaitable[None]]
ReportRenderer = Callable[[Path], None]
