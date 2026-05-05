from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import numpy as np
from binance.client import Client
from pycoingecko import CoinGeckoAPI

@dataclass
class Provider(ABC):

    @abstractmethod
    def get_prices(self, symbol: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def test_symbol(self, symbol: str) -> str:
        pass

@dataclass
class YahooProvider(Provider):

    period: str = "1d"
    interval: str = "1m"

    def get_prices(self, symbol: str) -> pd.DataFrame:
        data = yf.download(symbol, period=self.period, interval=self.interval)
        if data.empty:
            raise ValueError(f"Failed to fetch data for {symbol}")
        return data

    def test_symbol(self, symbol: str) -> str:
        try:
            data = self.get_prices(symbol)
            if data.empty:
                raise ValueError
            return symbol
        except Exception:
            raise ValueError(f"Symbol {symbol} not found")

@dataclass
class BinanceProvider(Provider):
    period: str = "10y"
    interval: str = "1wk"
    client: Client = Client()

    def __post_init__(self):
        if self.interval == "1wk":
            self.interval = "1w"
        elif self.interval == "1mo":
            self.interval = "1M"

    def get_prices(self, symbol: str) -> pd.DataFrame:
        limit = self.period_to_limit(self.period, self.interval)
        data = self.client.get_klines(symbol=symbol, interval=self.interval, limit=limit)
        columns = [
            'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close_time', 'Quote_asset_volume', 'Number_of_trades',
            'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'
        ]
        df = pd.DataFrame(data, columns=columns)
        df = df[['Close_time', 'Open', 'High', 'Low', 'Close', 'Volume']]
        df['Close_time'] = pd.to_datetime(df['Close_time'], unit='ms')
        return df

    def test_symbol(self, symbol: str) -> str:
        try:
            data = self.get_prices(symbol)
            if data.empty:
                raise ValueError
            return symbol
        except Exception:
            raise ValueError(f"Symbol {symbol} not found")

    def period_to_limit(self, period: str, interval: str = "1m") -> int:
        period_map = {
            "1d": 1440,
            "5d": 7200,
            "1mo": 43200,
            "3mo": 129600,
            "6mo": 259200,
            "1y": 525600,
            "2y": 1051200,
            "5y": 2628000,
            "10y": 5256000,
            "ytd": 525600,
            "max": 1000,
        }

        interval_minutes = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
            "3d": 4320,
            "1w": 10080,
            "1M": 43200,
        }

        if period in period_map:
            total_minutes = period_map[period]
            interval_min = interval_minutes.get(interval, 1)
            calculated_limit = total_minutes // interval_min
            return min(calculated_limit, 1000)

        return 1000

@dataclass
class CoinGeckoProvider(Provider):
    from_timestamp: datetime = datetime.now() - timedelta(days=365)
    to_timestamp: datetime = datetime.now()
    vs_currencies: str = 'usd'
    days: int = 365

    def get_prices(self, symbol: str) -> pd.DataFrame:
        cg = CoinGeckoAPI()
        data = cg.get_coin_market_chart_by_id(
            id=symbol,
            vs_currency=self.vs_currencies,
            days=self.days
        )

        prices = data['prices']
        timestamps = [pd.to_datetime(item[0], unit='ms') for item in prices]
        values = [item[1] for item in prices]

        df = pd.DataFrame({'Date': timestamps, 'Close': values})
        df.set_index('Date', inplace=True)

        df['Open'] = df['Close']
        df['High'] = df['Close']
        df['Low'] = df['Close']
        df['Volume'] = 0

        return df

    def test_symbol(self, symbol: str) -> str:
        try:
            data = self.get_prices(symbol)
            if data.empty:
                raise ValueError
            return symbol
        except Exception:
            raise ValueError(f"Symbol {symbol} not found")
