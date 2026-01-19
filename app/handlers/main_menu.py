from aiogram import types, Router, F

from callbacks import MainMenuCallback
from app.keyboards.make_markup import main_menu
from aiogram.filters import Command
from app.repositories import repositories
router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_repo = repositories.user
    user_repo.create_user(message.from_user.id, message.from_user.username)

    await message.answer(
        'Привет!\n'
        'Я телеграм бот, созданный для помощи тебе в инвестициях\n'
        'Полагаю тебе интересно, что я умею?\nВот список вещей, которые я делаю:\n'
        '- высылаю текущий график и корректировки компании\n'
        '- высылаю основные мультипликаторы компани\n'
        '- высылаю высылать график с техиндикаторами\n'
        '- высылаю основные пункты из отчета компании\n'
        'Если вдруг тебя интересует вопрос, какие техиндикаторы или мультипликаторы я могу выслать,'
        'нажми кнопку "Справка". Там можно будет найти список доступных параметров и гайд по ним\n'
    )
    await message.answer(
        "Выберите действие",
        reply_markup=main_menu()
    )


@router.callback_query(MainMenuCallback.filter(F.path == "main_menu"))
async def main_menu_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите действие",
        reply_markup=main_menu()
    )
