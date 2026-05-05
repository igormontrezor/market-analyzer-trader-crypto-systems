from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Union
import numpy as np
import pandas as pd
import sys
import os

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_system_root = os.path.dirname(current_dir)
sys.path.insert(0, analysis_system_root)

from assets.asset import Asset
from indicators.indicators import (
    Rsi, StochRsi, BollingerBands, Macd, SharpeRatio, SortinoRatio
)


@dataclass
class Signal(ABC):
    @abstractmethod
    def generate_signals(self, asset: Asset):
        pass


@dataclass
class RsiSignal(Signal):
    rsi: Rsi
    buy_threshold: float = 25
    sell_threshold: float = 80

    def generate_signals(self, asset: Asset) -> pd.Series:
        rsi = self.rsi.calculate(asset)
        signals = pd.Series(0, index=rsi.index)
        signals[(rsi < self.buy_threshold)] = -1  # Buy
        signals[(rsi > self.sell_threshold)] = 1  # Sell
        return signals


@dataclass
class StochRsiSignal(Signal):
    stoch: StochRsi
    buy_threshold: float = 5
    sell_threshold: float = 95

    def generate_signals(self, asset: Asset) -> pd.Series:
        stoch = self.stoch.calculate(asset)
        signals = pd.Series(0, index=stoch.index)
        signals[(stoch['d'] < self.buy_threshold)] = -1  # Buy
        signals[(stoch['d'] > self.sell_threshold)] = 1  # Sell
        return signals


@dataclass
class BollingerBandsSignal(Signal):
    bb: BollingerBands
    buy_threshold: float = 0
    sell_threshold: float = 1

    def generate_signals(self, asset: Asset) -> pd.Series:
        bb = self.bb.calculate(asset)
        signals = pd.Series(0, index=bb.index)
        signals[(bb < self.buy_threshold)] = -1  # Buy
        signals[(bb > self.sell_threshold)] = 1  # Sell
        return signals


@dataclass
class MacdSignal(Signal):
    macd: Macd

    def generate_signals(self, asset: Asset) -> pd.Series:
        macd = self.macd.calculate(asset)
        macd_line = macd['macd']
        signal_line = macd['signal']
        hist = macd_line - signal_line
        regime = pd.Series(0, index=hist.index)
        regime[(hist > 0) & (hist.shift(1) <= 0)] = 1
        regime[(hist < 0) & (hist.shift(1) >= 0)] = -1
        return regime


@dataclass
class SharpeSignal(Signal):
    sharpe: SharpeRatio
    buy_threshold: float = -1.5  # Default buy threshold (Sharpe 1wk)
    sell_threshold: float = 2.0  # Default sell threshold (Sharpe 1wk)

    def generate_signals(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        sharpe = self.sharpe.calculate(asset)
        signals = pd.Series(0, index=sharpe.index)
        signals[sharpe < self.buy_threshold] = -1
        signals[sharpe > self.sell_threshold] = 1
        return signals


@dataclass
class SortinoSignal(Signal):
    sortino: SortinoRatio
    buy_threshold: float = -1.5  # Default buy threshold (Sortino 1wk)
    sell_threshold: float = 4.5  # Default sell threshold (Sortino 1wk)

    def generate_signals(self, asset: Union[Asset, pd.Series]) -> pd.Series:
        sortino = self.sortino.calculate(asset)
        signals = pd.Series(0, index=sortino.index)
        signals[sortino < self.buy_threshold] = -1
        signals[sortino > self.sell_threshold] = 1
        return signals


@dataclass
class CombinedSignal:
    signals: List[Signal] = None
    weights: List[float] = None
    quantity_threshold: float = None
    window: int = 1
    min_periods: int = 1

    def generate_signals(self, asset: Asset):
        signals_list = [
            signal.generate_signals(asset)
            for signal in self.signals
        ]

        if self.quantity_threshold is None:
            self.quantity_threshold = len(self.signals)

        df = pd.concat(signals_list, axis=1).fillna(0)
        weights = np.array(self.weights)
        combined = (df * weights).sum(axis=1)

        final_signal = pd.Series(0, index=combined.index)
        final_signal[combined >= self.quantity_threshold] = 1
        final_signal[combined <= -self.quantity_threshold] = -1

        return final_signal

    def confirm_signals(self, asset: Asset):
        signal = self.generate_signals(asset)
        smooth = signal.rolling(
            window=self.window,
            min_periods=self.window
        ).mean()
        final_signal = pd.Series(0, index=signal.index)
        final_signal[smooth >= 1.0] = 1
        final_signal[smooth <= -1.0] = -1
        return final_signal
