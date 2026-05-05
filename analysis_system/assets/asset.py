#import matplotlib.pyplot as plt
#import plotly.express as px
#import seaborn as sns
import pandas as pd
import numpy as np
from typing import Optional
#from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field

from .provider import Provider, YahooProvider



@dataclass
class Asset(ABC):
    symbol: str
    _prices: Optional[pd.DataFrame] = None

    @abstractmethod
    def get_prices(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def test_symbol(self) -> str:
        pass

@dataclass
class MarketAsset(Asset):

    provider: Optional[Provider] = None
    def __post_init__(self):
        if self.provider is None:
            self.provider = YahooProvider()

    def get_prices(self) -> pd.DataFrame:
        if self._prices is None:
            logging.info(f"Fetching prices for {self.symbol}...")
            self._prices = self.provider.get_prices(self.symbol)
        return self._prices

    def test_symbol(self) -> str:
        return self.provider.test_symbol(self.symbol)

    def get_close_series(self) -> pd.Series:
        prices = self.get_prices()
        if 'Close' not in prices.columns:
            raise ValueError("Missing 'Close' column in price data")
        return prices['Close'][self.symbol]

    def get_current_price(self) -> float:
        return self.get_prices()['Close'].iloc[-1]
