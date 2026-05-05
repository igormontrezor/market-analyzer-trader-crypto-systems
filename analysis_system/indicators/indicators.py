from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from typing import Union
import sys
import os

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_system_root = os.path.dirname(current_dir)
sys.path.insert(0, analysis_system_root)

from assets.asset import Asset


@dataclass
class Indicator(ABC):
    @abstractmethod
    def calculate(self, asset: Union[Asset, pd.Series]):
        pass

    def apply_indicator(self, result, indicator=None):
        if indicator is None:
            return result
        return indicator.calculate(result)

    def calculate_with(self, asset, indicator=None):
        result = self.calculate(asset)
        if indicator is not None:
            result = self.apply_indicator(result, indicator)
        return result


@dataclass
class SimpleMovingAverage(Indicator):
    period: int = 20

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        result = asset.rolling(window=self.period).mean()
        result.name = f"SMA_{self.period}"
        return result


@dataclass
class ExponentialMovingAverage(Indicator):
    period: int = 20

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        result = asset.ewm(span=self.period, adjust=False).mean()
        result.name = f"EMA_{self.period}"
        return result


@dataclass
class Rsi(Indicator):
    period: int = 14

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        delta = asset.diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
        loss = loss.replace(0, np.nan)
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi.name = f"RSI_{self.period}"
        return rsi


@dataclass
class StochRsi(Indicator):
    period: int = 14
    smooth: int = 3
    rsi: Rsi = field(default_factory=Rsi)

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.DataFrame:
        rsi_series = self.rsi.calculate(asset)
        rsi_low = rsi_series.rolling(self.period).min()
        rsi_high = rsi_series.rolling(self.period).max()
        denom = (rsi_high - rsi_low).replace(0, np.nan)
        k_raw = (rsi_series - rsi_low) / denom * 100
        k = k_raw.rolling(window=self.smooth).mean() if self.smooth and self.smooth > 1 else k_raw
        d = k.rolling(window=self.smooth).mean() if self.smooth and self.smooth > 1 else k
        k.name = f"Stoch_RSI_K_{self.period}_{self.smooth}"
        d.name = f"Stoch_RSI_D_{self.period}_{self.smooth}"
        return pd.DataFrame({
            "rsi": rsi_series,
            "k": k,
            "d": d
        }).dropna()


@dataclass
class BollingerBands(Indicator):
    window: int = 20
    std_dev: int = 2

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        price = asset
        middle = price.rolling(self.window).mean()
        std = price.rolling(self.window).std()
        upper = middle + self.std_dev * std
        lower = middle - self.std_dev * std
        bb_percent_b = (price - lower) / (upper - lower)
        bb_percent_b.name = f"BB_percent_b_{self.window}_{self.std_dev}"
        return bb_percent_b


@dataclass
class Macd(Indicator):
    fast: int = 12
    slow: int = 26
    signal: int = 9

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.DataFrame:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        close = asset
        exp1 = close.ewm(span=self.fast).mean()
        exp2 = close.ewm(span=self.slow).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.signal).mean()
        histogram = macd - signal
        macd.name = f"MACD_{self.fast}_{self.slow}_{self.signal}"
        signal.name = f"MACD_Signal_{self.fast}_{self.slow}_{self.signal}"
        histogram.name = f"MACD_Histogram_{self.fast}_{self.slow}_{self.signal}"
        return pd.DataFrame({
            "macd": macd,
            "signal": signal,
            "histogram": histogram
        })


@dataclass
class SharpeRatio(Indicator):
    period: int = 52  # Default period for 1wk
    window: int = 60  # Default window for 1wk
    rf: float = 0.01

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        close_prices = asset
        returns = self._log_return(close_prices)
        sharpe_ratio = self._annualized_sharpe(returns, period=self.period, window=self.window, rf=self.rf)
        sharpe_ratio.name = f"Sharpe_{self.period}_{self.window}_{self.rf}"
        return sharpe_ratio

    def _log_return(self, prices: pd.Series) -> pd.Series:
        returns = np.log(prices / prices.shift(1)).dropna()
        returns.name = 'log_return'
        return returns

    def _annualized_sharpe(self, returns: pd.Series, period=52, rf=0.01, window=60) -> pd.Series:
        rolling_mean = returns.rolling(window=window).mean() * period
        rolling_std = returns.rolling(window=window).std() * np.sqrt(period)
        sharpe_ratio = (rolling_mean - rf) / rolling_std
        sharpe_ratio = sharpe_ratio.replace([np.inf, -np.inf], np.nan)
        return sharpe_ratio


@dataclass
class SortinoRatio(Indicator):
    period: int = 52  # Default period for 1wk
    window: int = 60  # Default window for 1wk
    rf: float = 0.01

    def calculate(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        if hasattr(asset, 'get_close_series'):
            asset = asset.get_close_series()
        close_prices = asset
        returns = self._log_return(close_prices)
        sortino_ratio = self._annualized_sortino(returns, period=self.period, window=self.window, rf=self.rf)
        sortino_ratio.name = f"Sortino_{self.period}_{self.window}_{self.rf}"
        return sortino_ratio

    def _log_return(self, prices: pd.Series) -> pd.Series:
        returns = np.log(prices / prices.shift(1)).dropna()
        returns.name = 'log_return'
        return returns

    def _annualized_sortino(self, returns: pd.Series, period=52, rf=0.01, window=60) -> pd.Series:
        mar = rf / period
        excess = returns - mar
        downside = np.minimum(0, excess)
        downside_deviation = downside.rolling(window=window).std() * np.sqrt(period)
        rolling_mean = excess.rolling(window=window).mean() * period
        sortino_ratio = rolling_mean / downside_deviation
        sortino_ratio = sortino_ratio.replace([np.inf, -np.inf], np.nan)
        return sortino_ratio


class Calculations:
    @staticmethod
    def log_return(prices: Union[pd.Series, Asset]) -> pd.Series:
        if hasattr(prices, 'get_close_series'):
            prices = prices.get_close_series()
        returns = np.log(prices / prices.shift(1)).dropna()
        returns.name = 'log_return'
        return returns

    @staticmethod
    def annualized_sharpe(returns: pd.Series, period=52, rf=0.01, window=60) -> pd.Series:
        rolling_mean = returns.rolling(window=window).mean() * period
        rolling_std = returns.rolling(window=window).std() * np.sqrt(period)
        sharpe_ratio = (rolling_mean - rf) / rolling_std
        sharpe_ratio = sharpe_ratio.replace([np.inf, -np.inf], np.nan)
        return sharpe_ratio

    @staticmethod
    def annualized_sortino(returns: pd.Series, period=52, rf=0.01, window=60) -> pd.Series:
        mar = rf / period
        excess = returns - mar
        downside = np.minimum(0, excess)
        downside_deviation = downside.rolling(window=window).std() * np.sqrt(period)
        rolling_mean = excess.rolling(window=window).mean() * period
        sortino_ratio = rolling_mean / downside_deviation
        sortino_ratio = sortino_ratio.replace([np.inf, -np.inf], np.nan)
        return sortino_ratio
