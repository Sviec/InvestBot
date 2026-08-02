"""Безопасная отправка и редактирование сообщений.

Telegram отвечает ошибкой на редактирование сообщения тем же текстом, на
редактирование текста у сообщения с фотографией и на слишком длинный текст.
Все три случая штатные, поэтому обрабатываются здесь, а не в каждом хендлере.
"""

from __future__ import annotations

import logging
from typing import Union

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InaccessibleMessage, InlineKeyboardMarkup, Message

from app.utils.text import TELEGRAM_TEXT_LIMIT, chunk

logger = logging.getLogger(__name__)

Event = Union[Message, CallbackQuery]

# Ошибки редактирования, которые означают «отредактировать нельзя, отправь новое».
_FALLBACK_TO_SEND = (
    "there is no text in the message",
    "message can't be edited",
    "message to edit not found",
    "message is not modified",
)
MAX_ALERT_LENGTH = 200


def _is_editable(message: Message | InaccessibleMessage | None) -> bool:
    return message is not None and not isinstance(message, InaccessibleMessage)


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Заменяет текст сообщения, разбивая длинный текст и обходя ошибки Telegram."""
    parts = chunk(text, TELEGRAM_TEXT_LIMIT)
    head, *tail = parts
    message = callback.message

    if not _is_editable(message):
        await _send_new(callback, parts, reply_markup)
        return

    assert isinstance(message, Message)
    try:
        await message.edit_text(
            head,
            reply_markup=None if tail else reply_markup,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest as exc:
        reason = str(exc).lower()
        if not any(marker in reason for marker in _FALLBACK_TO_SEND):
            raise
        if "not modified" in reason:
            logger.debug("Сообщение не изменилось, повторное редактирование пропущено")
            if not tail:
                return
        else:
            logger.debug("Редактирование невозможно (%s), отправляю новое сообщение", exc)
            await message.answer(
                head,
                reply_markup=None if tail else reply_markup,
                disable_web_page_preview=True,
            )

    for index, part in enumerate(tail):
        await message.answer(
            part,
            reply_markup=reply_markup if index == len(tail) - 1 else None,
            disable_web_page_preview=True,
        )


async def _send_new(
    callback: CallbackQuery,
    parts: list[str],
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    for index, part in enumerate(parts):
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=part,
            reply_markup=reply_markup if index == len(parts) - 1 else None,
            disable_web_page_preview=True,
        )


async def send_text(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Отправляет текст, разбивая его на части по лимиту Telegram."""
    parts = chunk(text, TELEGRAM_TEXT_LIMIT)
    for index, part in enumerate(parts):
        await message.answer(
            part,
            reply_markup=reply_markup if index == len(parts) - 1 else None,
            disable_web_page_preview=True,
        )


async def notify(event: Event, text: str, *, alert: bool = False) -> None:
    """Сообщает пользователю о результате или об ошибке.

    Для callback-а используется всплывающее уведомление: оно не засоряет чат
    и не требует прав на редактирование сообщения. Если callback уже закрыт
    ранним `ack`, Telegram отклонит повторный answer — тогда пишем в чат.
    """
    try:
        if isinstance(event, CallbackQuery):
            try:
                await event.answer(_plain(text)[:MAX_ALERT_LENGTH], show_alert=alert)
                return
            except TelegramAPIError:
                message = event.message
                if isinstance(message, Message):
                    await send_text(message, text)
                else:
                    await event.bot.send_message(
                        chat_id=event.from_user.id,
                        text=_plain(text),
                    )
                return
        await send_text(event, text)
    except TelegramForbiddenError:
        logger.info("Пользователь заблокировал бота, уведомление не доставлено")
    except TelegramAPIError as exc:
        logger.warning("Не удалось доставить уведомление: %s", exc)


def _plain(text: str) -> str:
    """Убирает HTML-разметку: всплывающие уведомления её не поддерживают."""
    result = text
    for tag in ("<b>", "</b>", "<i>", "</i>", "<code>", "</code>"):
        result = result.replace(tag, "")
    return result


async def delete_silently(message: Message | InaccessibleMessage | None) -> None:
    """Удаляет сообщение, игнорируя запрет на удаление старых сообщений."""
    if not _is_editable(message):
        return
    assert isinstance(message, Message)
    try:
        await message.delete()
    except TelegramAPIError as exc:
        logger.debug("Сообщение не удалено: %s", exc)
