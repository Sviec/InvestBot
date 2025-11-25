import asyncio

from bot import bot, dp
from app.handlers import forecast, main_menu, profile, analysis, reference


async def main():
    dp.include_router(main_menu.router)
    dp.include_router(forecast.router)
    dp.include_router(analysis.router)
    dp.include_router(profile.router)
    dp.include_router(reference.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
