import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np


class Sector:
    def __init__(self, sector: str):
        self.__sector = sector

