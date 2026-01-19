from aiogram import types
from aiogram.filters.callback_data import CallbackData

from app.entities.company import Company


class BaseCallback(CallbackData, prefix="base"):
    path: str

    def get_back_button(self):
        items = self.path.split('%')
        if len(items[:-1]) <= 1:
            back_callback = MainMenuCallback.create(path="main_menu")
        else:
            back_path = '%'.join(items[:-1])
            back_callback = type(self).create(path=back_path)
        return types.InlineKeyboardButton(
            text="Назад",
            callback_data=back_callback.pack()
        )


class MainMenuCallback(BaseCallback, prefix="main_menu"):
    @staticmethod
    def create(path: str = "") -> 'MainMenuCallback':
        return MainMenuCallback(path=path)


class AnalysisCallback(BaseCallback, prefix="analysis"):
    @staticmethod
    def create(path: str) -> 'AnalysisCallback':
        print(path)
        return AnalysisCallback(path=path)


class CompanyCallback(BaseCallback, prefix="company"):

    def get_back_button(self):
        items = self.path.split('%')
        if len(items[:-1]) <= 1:
            back_callback = AnalysisCallback.create(path="analysis%company")
        else:
            back_path = '%'.join(items[:-1])
            back_callback = type(self).create(path=back_path)
        return types.InlineKeyboardButton(
            text="Назад",
            callback_data=back_callback.pack()
        )

    @staticmethod
    def create(path: str) -> 'CompanyCallback':
        print(path)
        return CompanyCallback(path=path)


class ForecastCallback(BaseCallback, prefix="forecast"):
    @staticmethod
    def create(path: str) -> 'ForecastCallback':
        return ForecastCallback(path=path)


class ProfileCallback(BaseCallback, prefix="profile"):
    @staticmethod
    def create(path: str) -> 'ProfileCallback':
        return ProfileCallback(path=path)


class ReferenceCallback(BaseCallback, prefix="reference"):
    @staticmethod
    def create(path: str) -> 'ReferenceCallback':
        return ReferenceCallback(path=path)