from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from app.data.config import config

default_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
bot = Bot(token=config.bot_token, default=default_properties)
dp = Dispatcher(storage=MemoryStorage())
