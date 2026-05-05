"""
Market Analysis System

Sistema completo para análise de mercado financeiro com indicadores técnicos,
sinais de trading e visualizações.
"""

from .assets import (
    Asset,
    Portfolio,
    Position,
    LongPosition,
    ShortPosition,
    Provider,
    YahooProvider,
    BinanceProvider,
    CoinGeckoProvider,
)
from .indicators import (
    Indicator, SimpleMovingAverage, ExponentialMovingAverage, Rsi,
    StochRsi, BollingerBands, Macd, SharpeRatio, SortinoRatio, Calculations
)
from .signals import (
    Signal, RsiSignal, StochRsiSignal, BollingerBandsSignal,
    MacdSignal, SharpeSignal, SortinoSignal, CombinedSignal
)
from .plotting import ChartPlotter
from .strategies import Strategy, BtcStrategy
from .utils import DataAggregator
from .trading import Arbitration

__version__ = "1.0.0"
__author__ = "Market Montrezor System"

__all__ = [
    # Assets
    'Asset', 'Portfolio', 'Position', 'LongPosition', 'ShortPosition',
    'Provider', 'YahooProvider', 'BinanceProvider', 'CoinGeckoProvider',

    # Indicators
    'Indicator', 'SimpleMovingAverage', 'ExponentialMovingAverage', 'Rsi',
    'StochRsi', 'BollingerBands', 'Macd', 'SharpeRatio', 'SortinoRatio',
    'Calculations',

    # Signals
    'Signal', 'RsiSignal', 'StochRsiSignal', 'BollingerBandsSignal',
    'MacdSignal', 'SharpeSignal', 'SortinoSignal', 'CombinedSignal',

    # Plotting
    'ChartPlotter',

    # Strategies
    'Strategy', 'BtcStrategy',

    # Utils
    'DataAggregator',

    # Trading
    'Arbitration'
]
