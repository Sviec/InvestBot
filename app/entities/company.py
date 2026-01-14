import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import six


class Company:
    def __init__(self, ind: str = 'AAPL'):
        self.ind = yf.Ticker(ind.upper())
        self.info = self.ind.info

    def get_info(self) -> str:
        info = ""
        if 'country' in self.info and self.info['country'] is not None:
            info += f"Страна: {self.info['country']}\n"
        if 'city' in self.info and self.info['city'] is not None:
            info += f"Город: {self.info['city']}\n"
        if 'sector' in self.info and self.info['sector'] is not None:
            info += f"Сектор: {self.info['sector']}\n"
        if 'industry' in self.info and self.info['industry'] is not None:
            info += f"Индустрия: {self.info['industry']}\n"
        if 'marketCap' in self.info and  self.info['marketCap'] is not None:
            info += f"Капитализация: {'{:,.1f}'.format(self.info['marketCap'])}\n"
        if 'fullTimeEmployees' in self.info and self.info['fullTimeEmployees'] is not None:
            info += f"Кол-во сотрудников: {self.info['fullTimeEmployees']}\n"
        if 'website' in self.info and self.info['website'] is not None:
            info += f"Сайт: {self.info['website']}"
        return info

    def get_description(self):
        return self.info['longBusinessSummary']

    def get_dividends(self) -> str:
        dividends = self.ind.dividends
        if len(dividends) == 0:
            return 'Компания не выплачивает дивиденды'
        temp_text = 'Последние выплаты:\n'
        max_payments = min(10, len(dividends.values))
        for i_payment in range(1, max_payments):
            temp_text += f'{dividends.index[-i_payment]} - {dividends.values[-i_payment]}\n'
        return temp_text

    def get_sustainability(self) -> str:
        sustainability = self.ind.sustainability
        if sustainability is None:
            return 'По этой компании нет данных'
        result_text = f"Total ESG Risk score: {sustainability.loc['totalEsg']['Value']}\n" \
                      f"Environment Risk Score: {sustainability.loc['environmentScore']['Value']}\n" \
                      f"Social Risk Score: {sustainability.loc['socialScore']['Value']}\n" \
                      f"Governance Risk Score: {sustainability.loc['governanceScore']['Value']}\n" \
                      f"Controversy Level: {sustainability.loc['highestControversy']['Value']}"
        return result_text

    def get_name(self):
        try:
            return self.info['longName']
        except Exception as e:
            return None

    def get_price(self):
        return self.info['currentPrice']

    def set_ticker(self, new_ind):
        self.ind = yf.Ticker(new_ind.upper())
        self.info = self.ind.info

    def get_graphic(self, start='', end=''):
        if start == '':
            df = self.ind.history(period='max')['Close']
        else:
            df = self.ind.history(start=start, end=end)['Close']
        fig, ax = plt.subplots(figsize=(12, 6))

        sns.set_style("darkgrid", {'axes.grid': True})
        sns.lineplot(data=df, ax=ax)
        ax.yaxis.tick_right()

        ax.set_title(f'График акций компании {self.get_name()}')
        ax.set_xlabel('')
        ax.set_ylabel('')
        plt.savefig("../users_files/fig.png")

    def get_multiplier(self) -> str:
        multiplier_data = f"Основные мультипликаторы:\n"
        if 'trailingPE' in self.info:
            multiplier_data += f"Trailing P/E: {round(self.info['trailingPE'], 2)}\n"
        if 'priceToSalesTrailing12Months' in self.info:
            multiplier_data += f"P/S: {round(self.info['priceToSalesTrailing12Months'], 2)}\n"
        if 'priceToBook' in self.info:
            multiplier_data += f"P/B: {round(self.info['priceToBook'], 2)}\n"
        if 'debtToEquity' in self.info and type(self.info['debtToEquity']) is float:
            f"TotalDebt/Equity: {round(self.info['debtToEquity'], 2)}\n"
        if 'totalDebt' in self.info and 'totalCash' in self.info and \
                'ebitda' in self.info and type(self.info['ebitda']) is float:
            multiplier_data += f"NetDebt/EBITDA: " \
                                f"{round((self.info['totalDebt'] - self.info['totalCash']) / self.info['ebitda'], 2)}\n"
        if 'currentRatio' in self.info and type(self.info['currentRatio']) is float:
            multiplier_data += f"Current Ratio: {round(self.info['currentRatio'], 2)}\n"
        if 'returnOnEquity' in self.info:
            multiplier_data += f"ROE: {str(round(self.info['returnOnEquity'] * 100, 2)) + '%'}\n"
        if 'returnOnAssets' in self.info:
            multiplier_data += f"ROA: {str(round(self.info['returnOnAssets'] * 100, 2)) + '%'}\n"
        if 'enterpriseToEbitda' in self.info and type(self.info['enterpriseToEbitda']) is float:
            multiplier_data += f"EV/EBITDA: {round(self.info['enterpriseToEbitda'], 2)}"

        return multiplier_data

    def get_balance_sheet_year(self):
        self.get_report(
            pd.DataFrame(self.ind.balance_sheet),
            '../../users_files/balance_sheet.png',
            f'Балансовая отчетность компании {self.get_name()} по годам'
        )

    def get_balance_sheet_quarter(self):
        self.get_report(
            pd.DataFrame(self.ind.quarterly_balance_sheet),
            '../../users_files/quarterly_balance_sheet.png',
            f'Балансовая отчетность компании {self.get_name()} по кварталам'
        )

    def get_financials_year(self):
        self.get_report(
            pd.DataFrame(self.ind.financials),
            '../../users_files/financials.png',
            f'Финансовая отчетность компании {self.get_name()} по годам'
        )

    def get_financials_quarter(self):
        self.get_report(
            pd.DataFrame(self.ind.quarterly_financials),
            '../../users_files/quarterly_financials.png',
            f'Финансовая отчетность компании {self.get_name()} по кварталам'
        )

    def get_cash_flow_year(self):
        self.get_report(
            pd.DataFrame(self.ind.cashflow),
            '../../users_files/cash_flow.png',
            f'Денежный поток компании {self.get_name()} по годам'
        )

    def get_cash_flow_quarter(self):
        self.get_report(
            pd.DataFrame(self.ind.quarterly_cashflow),
            '../../users_files/quarterly_cash_flow.png',
            f'Денежный поток компании {self.get_name()} по кварталам'
        )

    def get_earnings_year(self):
        self.get_report(
            pd.DataFrame(self.ind.earnings),
            '../../users_files/earnings.png',
            f'Выручка компании {self.get_name()} по годам'
        )

    def get_earnings_quarter(self):
        self.get_report(
            pd.DataFrame(self.ind.quarterly_earnings),
            '../../users_files/quarterly_earnings.png',
            f'Выручка компании {self.get_name()} по кварталам'
        )

    @staticmethod
    def make_photo(df, file: str, title: str = ''):
        indexes = df.index
        df.insert(0, 'Parameter', indexes)

        row_colors = ['#f1f1f2', 'w']
        size = (np.array(df.shape[::-1]) + np.array([1, 1])) * np.array([3.0, 0.625])
        fig, ax = plt.subplots(figsize=size)
        ax.axis('off')
        mpl_table = ax.table(cellText=df.values, bbox=[0, 0, 1, 1], colLabels=df.columns)

        mpl_table.auto_set_font_size(False)
        mpl_table.set_fontsize(13)
        mpl_table.auto_set_column_width(col=list(range(len(df.columns))))
        ax.set_title(label=title)

        for k, cell in six.iteritems(mpl_table._cells):
            cell.set_edgecolor('w')
            if k[0] == 0:
                cell.set_text_props(weight='bold', color='w')
                cell.set_facecolor('#40466e')
            else:
                cell.set_facecolor(row_colors[k[0] % 2])

        plt.savefig(file)

    def get_report(self, df: pd.DataFrame, filename: str, text: str):
        df.iloc[[i for i in range(1, len(df))], :] /= 1000
        df.drop(index=[df.index[0]], inplace=True)
        for row in range(df.shape[0]):
            for elem in range(len(df.columns)):
                df.iloc[row, elem] = '{:,.1f}'.format(df.iloc[row, elem])
        self.make_photo(df, filename, text)

    def get_major_holders(self):
        df = pd.DataFrame(self.ind.major_holders)
        self.make_photo(df, '../../users_files/major_holders.png', f'Основные держатели акций компании {self.get_name()}')

    def get_institutional_holders(self):
        df = pd.DataFrame(self.ind.institutional_holders)
        self.make_photo(df, '../../users_files/institutional_holders.png',
                        f'Институциональные держатели акций компании {self.get_name()}')

    def get_news(self):
        news = "Последние новости (на английском):\n"
        for elem in self.ind.news:
            news += f"{elem['title']} - {elem['link']}\n"
        return news

    def get_analysis(self):
        df = pd.DataFrame(self.ind.analyst_price_target)
        self.make_photo(df, '../../users_files/analysis.png', f'Аналитика компании {self.get_name()}')


'''
multiplier_list = {'p/b': 'priceToBook', 
                    'p/s': 'priceToSalesTrailing12Months', 
                    'trailing P/E': 'trailingPE',
                   'TotalDebt/Equity': 'debtToEquity',
                   'TotalCash': 'totalCash', 
                   'TotalDebt': 'totalDebt', # totaldebt - totalcash = netdebt
                  'Current Ratio': 'currentRatio',
                  'ROA': 'returnOnAssets', 
                  'ROE': 'returnOnEquity',
                   'EV': 'enterpriseValue', 
                   'EBITDA': 'ebitda',
                   'EV/EBITDA': 'enterpriseToEbitda'
                   }
'''
