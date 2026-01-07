import yfinance as yf


class Industry:
    def __init__(self, industry: str):
        self.__industry = yf.Industry(industry.lower())

    def get_name(self) -> str:
        return self.__industry.name

    def get_sector_name(self) -> str:
        return self.__industry.sector_name

    def get_overview(self) -> str:
        overview = self.__industry.overview
        text = f"""
            Сектор: {self.__industry.name}\n
            {overview['description']}\n
            Количество компаний: {overview['companies_count']}\n
            Рыночная капитализация: {overview['market_cap']}\n
            Вес на рынке: {round(overview['market_weight'] * 100, 2)}%\n
            Общее количество сотрудников: {overview['employee_count']}\n
        """
        return text

    def get_top_companies(self) -> str:
        companies = self.__industry.top_companies
        text = "Ticker: Company name\nPrediction - Market weight"
        for ticker, body in zip(companies.index.tolist()[:10], companies.values.tolist()):
            text += f"{ticker}: {body[0]}\n{body[1]} - {body[2]}\n"
        return text

    def get_top_growth_companies(self):
        companies = self.__industry.top_growth_companies
        text = "Ticker: Company name\nytd return - Growth estimate"
        for ticker, body in zip(companies.index.tolist()[:10], companies.values.tolist()):
            text += f"{ticker}: {body[0]}\n{body[1]} - {body[2]}\n"
        return text

    def get_top_performing_companies(self):
        companies = self.__industry.top_performing_companies
        text = "Ticker: Company name\nytd return - Last price - Target price"
        for ticker, body in zip(companies.index.tolist()[:10], companies.values.tolist()):
            text += f"{ticker}: {body[0]}\n{body[1]} - {body[2]} - {body[3]}\n"
        return text
