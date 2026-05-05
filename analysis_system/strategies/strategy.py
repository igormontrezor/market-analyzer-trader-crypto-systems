from dataclasses import dataclass, field
from typing import List
import sys
import os

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_system_root = os.path.dirname(current_dir)
sys.path.insert(0, analysis_system_root)

from indicators.indicators import (
    SimpleMovingAverage, ExponentialMovingAverage, Rsi, StochRsi,
    BollingerBands, Macd, SharpeRatio, SortinoRatio
)
from signals.signals import (
    RsiSignal, StochRsiSignal, BollingerBandsSignal,
    MacdSignal, SharpeSignal, SortinoSignal, CombinedSignal
)

@dataclass
class Strategy:
    def get_signal(self, timeframe: str, name_indicator: str):
        return self.signals[timeframe][name_indicator]

    def get_combined(self, timeframe: str, weights: list, threshold: float,
                    indicators: list[str] | None = None, window: int = 1, min_periods: int = 1):
        all_signals = self.signals[timeframe]
        if indicators is None:
            signals = list(all_signals.values())
        else:
            signals = [all_signals[indicator] for indicator in indicators]
        return CombinedSignal(signals=signals, weights=weights, quantity_threshold=threshold, window=window, min_periods=min_periods)

    def get_indicator_default(self, timeframe: str, name_indicator: str):
        return self.indicators[timeframe][name_indicator]

@dataclass
class BtcStrategy(Strategy):
    daily: dict = field(default_factory=dict)
    weekly: dict = field(default_factory=dict)
    monthly: dict = field(default_factory=dict)

    def __post_init__(self):
        self.indicators = {
            "daily": {
                'sma': SimpleMovingAverage(period=20),
                'ema': ExponentialMovingAverage(period=20),
                'rsi': Rsi(period=14),
                'stochrsi': StochRsi(period=20, smooth=3),
                'bb': BollingerBands(window=30, std_dev=2),
                'macd': Macd(fast=12, slow=26, signal=9),
                'sharpe': SharpeRatio(period=252, window=252, rf=0.01),
                'sortino': SortinoRatio(period=252, window=252, rf=0.01)
            },
            "weekly": {
                'sma': SimpleMovingAverage(period=20),
                'ema': ExponentialMovingAverage(period=20),
                'rsi': Rsi(period=14),
                'stochrsi': StochRsi(period=14, smooth=3),
                'bb': BollingerBands(window=30, std_dev=2),
                'macd': Macd(fast=12, slow=26, signal=9),
                'sharpe': SharpeRatio(period=52, window=60, rf=0.01),
                'sortino': SortinoRatio(period=52, window=60, rf=0.01)
            },
            "monthly": {
                'sma': SimpleMovingAverage(period=20),
                'ema': ExponentialMovingAverage(period=20),
                'rsi': Rsi(period=20),
                'stochrsi': StochRsi(period=14, smooth=3),
                'bb': BollingerBands(window=20, std_dev=2),
                'macd': Macd(fast=12, slow=26, signal=9),
                'sharpe': SharpeRatio(period=12, window=6, rf=0.01),
                'sortino': SortinoRatio(period=12, window=14, rf=0.01)
            }
        }

        self.signals = {
            "daily": {
                'rsi': RsiSignal(rsi=self.indicators["daily"]["rsi"], buy_threshold=25, sell_threshold=80),
                'stochrsi': StochRsiSignal(stoch=self.indicators["daily"]["stochrsi"], buy_threshold=5, sell_threshold=95),
                'bb': BollingerBandsSignal(bb=self.indicators["daily"]["bb"], buy_threshold=0, sell_threshold=1),
                'macd': MacdSignal(macd=self.indicators["daily"]["macd"]),
                'sharpe': SharpeSignal(sharpe=self.indicators["daily"]["sharpe"], buy_threshold=-2.0, sell_threshold=2.0),
                'sortino': SortinoSignal(sortino=self.indicators["daily"]["sortino"], buy_threshold=-2.0, sell_threshold=4.0)
            },
            "weekly": {
                'rsi': RsiSignal(rsi=self.indicators["weekly"]["rsi"], buy_threshold=20, sell_threshold=80),
                'stochrsi': StochRsiSignal(stoch=self.indicators["weekly"]["stochrsi"], buy_threshold=5, sell_threshold=95),
                'bb': BollingerBandsSignal(bb=self.indicators["weekly"]["bb"], buy_threshold=0, sell_threshold=1),
                'macd': MacdSignal(macd=self.indicators["weekly"]["macd"]),
                'sharpe': SharpeSignal(sharpe=self.indicators["weekly"]["sharpe"], buy_threshold=-1.5, sell_threshold=2.0),
                'sortino': SortinoSignal(sortino=self.indicators["weekly"]["sortino"], buy_threshold=-1.5, sell_threshold=4.9)
            },
            "monthly": {
                'rsi': RsiSignal(rsi=self.indicators["monthly"]["rsi"], buy_threshold=25, sell_threshold=80),
                'stochrsi': StochRsiSignal(stoch=self.indicators["monthly"]["stochrsi"], buy_threshold=5, sell_threshold=95),
                'bb': BollingerBandsSignal(bb=self.indicators["monthly"]["bb"], buy_threshold=0.1, sell_threshold=1),
                'macd': MacdSignal(macd=self.indicators["monthly"]["macd"]),
                'sharpe': SharpeSignal(sharpe=self.indicators["monthly"]["sharpe"], buy_threshold=-2.0, sell_threshold=3.5),
                'sortino': SortinoSignal(sortino=self.indicators["monthly"]["sortino"], buy_threshold=-1.5, sell_threshold=6.0)
            }
        }
