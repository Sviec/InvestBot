"""Доменные исключения приложения.

Каждое исключение несёт два сообщения: техническое (в лог) и `user_message`
(показывается пользователю). Хендлеры никогда не формируют текст ошибки сами —
они берут его из `user_message`, поэтому формулировки собраны в одном месте.
"""

from __future__ import annotations


class InvestBotError(Exception):
    """Базовое исключение приложения."""

    user_message = "Произошла внутренняя ошибка. Попробуйте позже."

    def __init__(self, message: str = "", *, user_message: str | None = None) -> None:
        super().__init__(message or self.user_message)
        if user_message is not None:
            self.user_message = user_message


class ConfigurationError(InvestBotError):
    """Некорректная или неполная конфигурация приложения."""

    user_message = "Бот сконфигурирован неверно. Сообщите администратору."


class OperationTimeoutError(InvestBotError):
    """Блокирующая операция не уложилась в отведённое время."""

    user_message = "Запрос выполняется слишком долго. Попробуйте ещё раз."


class StorageError(InvestBotError):
    """Ошибка обращения к базе данных."""

    user_message = "База данных временно недоступна. Попробуйте через минуту."


class NavigationError(InvestBotError):
    """Ошибка разбора пути навигации."""

    user_message = "Не удалось открыть раздел. Вернитесь в меню командой /start."


class UnknownPathError(NavigationError):
    """Путь не найден в дереве меню."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Путь {path!r} отсутствует в дереве меню")
        self.path = path


class MarketDataError(InvestBotError):
    """Базовая ошибка получения рыночных данных."""

    user_message = "Не удалось получить рыночные данные. Попробуйте позже."


class TickerNotFoundError(MarketDataError):
    """Тикер не найден у провайдера данных."""

    def __init__(self, ticker: str) -> None:
        super().__init__(f"Тикер {ticker!r} не найден")
        self.ticker = ticker
        self.user_message = (
            f"Тикер <b>{ticker}</b> не найден. "
            "Проверьте написание — например, AAPL, MSFT, BRK-B."
        )


class MarketDataUnavailableError(MarketDataError):
    """Провайдер данных недоступен или ограничил частоту запросов."""

    user_message = (
        "Источник рыночных данных сейчас недоступен. Попробуйте через несколько минут."
    )


class NoDataError(MarketDataError):
    """Провайдер ответил, но по этому объекту данных нет."""

    user_message = "По этому запросу нет данных."

    def __init__(self, message: str = "", *, user_message: str | None = None) -> None:
        super().__init__(message or "Данные отсутствуют", user_message=user_message)


class ReportRenderError(InvestBotError):
    """Не удалось построить изображение отчёта."""

    user_message = "Не удалось построить отчёт. Попробуйте другой период или компанию."


class ValidationError(InvestBotError):
    """Пользовательский ввод не прошёл валидацию."""

    user_message = "Некорректный ввод."

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message, user_message=user_message)
