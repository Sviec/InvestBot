from app.data.models.ticker import Ticker


async def get_sector_analysis(sector: str) -> str:
    return f"Анализ сектора {sector}:\n- Рост +3%\n- Лучшие компании: A, B, C"


async def get_multipliers(ticker: Ticker, analysis_type: str) -> str:
    ticker.get_multiplier()
    return f"{analysis_type.capitalize()} анализ компании {ticker}:\n- Показатели хорошие"