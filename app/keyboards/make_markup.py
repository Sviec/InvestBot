from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data.callbacks import AnalysisCallback, ProfileCallback, ReferenceCallback, ForecastCallback


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text='Прогноз',
            callback_data=ForecastCallback.create(path="forecast").pack()
        )],
        [InlineKeyboardButton(
            text='Анализ',
            callback_data=AnalysisCallback.create(path="analysis").pack()
        )],
        [InlineKeyboardButton(
            text='Профиль',
            callback_data=ProfileCallback.create(path="profile").pack()
        )],
        [InlineKeyboardButton(
            text='Справка',
            callback_data=ReferenceCallback.create(path="reference").pack()
        )]
    ])


def build_markup(callback: CallbackQuery,
                 callback_data: CallbackData,
                 path: dict,
                 *sizes) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for button, values in path['buttons'].items():
        kb.add(InlineKeyboardButton(
            text=values["button_text"],
            callback_data=type(callback_data).create(
                path='-'.join(callback.data.split(":")) + f"-{button}",
            ).pack(),
            url=path["buttons"][button].get("url") if path["buttons"][button].get("url") else None
        ))
    kb.add(callback_data.get_back_button())
    if sizes:
        kb.adjust(*sizes)
    else:
        kb.adjust(1)
    return kb
