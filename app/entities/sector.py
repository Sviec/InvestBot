import yfinance as yf


class Sector:
    def __init__(self, sector: str):
        self.__sector = yf.Sector(sector)

    def get_name(self):
        return self.__sector.name

    def get_industries(self) -> list:
        return list(self.__sector.industries.name.values())

    def get_overview(self) -> str:
        overview = self.__sector.overview
        text = f"""
            Сектор: {self.__sector.name}\n
            {overview['description']}\n
            Количество компаний: {overview['companies_count']}\n
            Рыночная капитализация: {overview['market_cap']}\n
            Вес на рынке: {round(overview['market_weight'] * 100, 2)}%\n
            Количество индустрий: {overview['industries_count']}\n
            Общее количество сотрудников: {overview['employee_count']}\n
        """
        return text

    def get_top_companies(self) -> str:
        text = "Ticker: Company Name\nPrediction - Market weight\n"
        companies = self.__sector.top_companies
        for ticker, body in zip(companies.index.tolist()[:15], companies.values.tolist()[:15]):
            text += f"{ticker}: {body[0]}\n{body[1]} - {body[2]}\n"
        return text

    def get_top_etfs(self):
        text = "Ticker: ETF Name\n"
        etfs = self.__sector.top_etfs
        for ticker, name in etfs.items():
            text += f"{ticker}: {name}\n"
        return text
