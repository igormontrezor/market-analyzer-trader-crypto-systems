import streamlit as st
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime
import sys
import os

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_system_root = os.path.dirname(current_dir)
sys.path.insert(0, analysis_system_root)

# Imports diretos
from assets import MarketAsset, YahooProvider, BinanceProvider, CoinGeckoProvider
from indicators import (
    SimpleMovingAverage, ExponentialMovingAverage, Rsi, StochRsi,
    BollingerBands, Macd, SharpeRatio, SortinoRatio
)
from signals import (
    RsiSignal, StochRsiSignal, BollingerBandsSignal,
    MacdSignal, SharpeSignal, SortinoSignal, CombinedSignal
)
from strategies import BtcStrategy
from plotting import ChartPlotter
from utils import DataAggregator
from web.chart_catalog import ChartCatalog

class ChartRenderer:
    """Renderizador de gráficos baseado exatamente no notebook"""

    def __init__(self):
        self.strategy = BtcStrategy()
        self.catalog = ChartCatalog()

    def _get_asset(self, chart_config: Dict) -> MarketAsset:
        """Cria asset com provider específico como no notebook"""
        if chart_config["provider"] == "yahoo":
            return MarketAsset(
                symbol=chart_config["symbol"],
                provider=YahooProvider(period="4y", interval="1d")
            )
        elif chart_config["provider"] == "binance":
            return MarketAsset(
                symbol=chart_config["symbol"],
                provider=BinanceProvider(period="10y", interval="1wk")
            )
        elif chart_config["provider"] == "coingecko":
            return MarketAsset(
                symbol=chart_config["symbol"],
                provider=CoinGeckoProvider()
            )
        else:
            return MarketAsset(symbol=chart_config["symbol"])

    def render_rsi_daily(self, chart_config: Dict):
        """Renderiza RSI Daily exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # Cria RSI strategy como no notebook
        btc_rsi_daily = self.strategy
        rsi_values = btc_rsi_daily.get_indicator_default('daily', 'rsi').calculate(asset)
        rsi_signals = btc_rsi_daily.get_signal('daily', 'rsi').generate_signals(asset)
        rsi_sma_20 = SimpleMovingAverage(period=20).calculate(rsi_values)
        rsi_buy = rsi_signals == -1
        rsi_sell = rsi_signals == 1

        # Renderiza como no notebook
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=rsi_values,
            title=f"{chart_config['name']} - RSI",
            buy_signals=rsi_buy,
            sell_signals=rsi_sell,
            indicator_name="RSI"
        )

    def render_rsi_weekly(self, chart_config: Dict):
        """Renderiza RSI Weekly exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # RSI weekly como no notebook
        rsi_weekly = Rsi(period=14)
        rsi_values_weekly = rsi_weekly.calculate(asset)
        rsi_signals_weekly = RsiSignal(rsi=rsi_weekly, buy_threshold=20, sell_threshold=80)
        rsi_signals_weekly_gen = rsi_signals_weekly.generate_signals(asset)
        rsi_weekly_sma_20 = SimpleMovingAverage(period=20).calculate(rsi_values_weekly)
        rsi_buy = rsi_signals_weekly_gen == -1
        rsi_sell = rsi_signals_weekly_gen == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=rsi_values_weekly,
            title=f"{chart_config['name']} - RSI Weekly",
            buy_signals=rsi_buy,
            sell_signals=rsi_sell,
            indicator_name="RSI Weekly"
        )

    def render_stochrsi_daily(self, chart_config: Dict):
        """Renderiza StochRSI Daily exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # StochRSI como no notebook
        btc_stochrsi_daily = self.strategy
        stochrsi_values = btc_stochrsi_daily.get_indicator_default('daily', 'stochrsi').calculate(asset)
        stochrsi_signals = btc_stochrsi_daily.get_signal('daily', 'stochrsi').generate_signals(asset)
        stochrsi_buy = stochrsi_signals == -1
        stochrsi_sell = stochrsi_signals == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=stochrsi_values,
            title=f"{chart_config['name']} - StochRSI",
            buy_signals=stochrsi_buy,
            sell_signals=stochrsi_sell,
            indicator_name="StochRSI"
        )

    def render_bollinger_bands_daily(self, chart_config: Dict):
        """Renderiza Bollinger Bands Daily exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # Bollinger Bands como no notebook
        btc_bb_daily = self.strategy
        bb_values = btc_bb_daily.get_indicator_default('daily', 'bb').calculate(asset)
        bb_strategy = btc_bb_daily.get_signal('daily', 'bb').generate_signals(asset)
        bb_buy = bb_strategy == -1
        bb_sell = bb_strategy == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=bb_values,
            title=f"{chart_config['name']} - Bollinger Bands",
            buy_signals=bb_buy,
            sell_signals=bb_sell,
            indicator_name="BB"
        )

    def render_macd_daily(self, chart_config: Dict):
        """Renderiza MACD Daily exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # MACD como no notebook
        btc_macd_daily = self.strategy
        macd_value = btc_macd_daily.get_indicator_default('daily', 'macd').calculate(asset)
        macd_signals = btc_macd_daily.get_signal('daily', 'macd').generate_signals(asset)
        macd_buy = macd_signals == 1
        macd_sell = macd_signals == -1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=macd_value,
            title=f"{chart_config['name']} - MACD",
            buy_signals=macd_buy,
            sell_signals=macd_sell,
            indicator_name="MACD"
        )

    def render_sharpe_weekly(self, chart_config: Dict):
        """Renderiza Sharpe Ratio Weekly exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # Sharpe como no notebook
        btc_sharpe_daily = self.strategy
        sharpe_values = btc_sharpe_daily.get_indicator_default('weekly', 'sharpe').calculate(asset)
        sharpe_signals = btc_sharpe_daily.get_signal('weekly', 'sharpe').generate_signals(asset)
        sharpe_sma_slow = SimpleMovingAverage(period=35).calculate(sharpe_values)
        sharpe_sma_fast = SimpleMovingAverage(period=10).calculate(sharpe_values)
        sharpe_buy = sharpe_signals == -1
        sharpe_sell = sharpe_signals == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=sharpe_values,
            title=f"{chart_config['name']} - Sharpe Ratio",
            buy_signals=sharpe_buy,
            sell_signals=sharpe_sell,
            indicator_name="Sharpe"
        )

    def render_sortino_weekly(self, chart_config: Dict):
        """Renderiza Sortino Ratio Weekly exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # Sortino como no notebook
        btc_sortino_daily = self.strategy
        sortino_values = btc_sortino_daily.get_indicator_default('weekly', 'sortino').calculate(asset)
        sortino_signals = btc_sortino_daily.get_signal('weekly', 'sortino').generate_ma_signals(asset, ma_fast=20, ma_slow=70)
        sortino_sma_14 = SimpleMovingAverage(period=70).calculate(sortino_values)
        sortino_sma_7 = SimpleMovingAverage(period=20).calculate(sortino_values)
        sortino_buy = sortino_signals == -1
        sortino_sell = sortino_signals == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=sortino_values,
            title=f"{chart_config['name']} - Sortino Ratio",
            buy_signals=sortino_buy,
            sell_signals=sortino_sell,
            indicator_name="Sortino"
        )

    def render_combined_daily(self, chart_config: Dict):
        """Renderiza Combined Daily exatamente como no notebook"""
        asset = self._get_asset(chart_config)

        # Combined como no notebook
        daily_df = asset.get_prices()

        combined_signal = self.strategy.get_combined(
            timeframe='daily',
            indicators=['rsi', 'stochrsi', 'bb'],
            weights=[0.5, 0.5, 2.0],
            threshold=3.0,
            min_periods=5,
            window=2
        ).confirm_signals(asset)

        combined_signal = combined_signal.reindex(daily_df.index).fillna(0)
        combined_buy = combined_signal == -1

        # Renderiza
        ChartPlotter.plot_candlestick_with_signals(
            df=daily_df,
            title=f"{chart_config['name']} - Combined Signals",
            buy_signals=combined_buy,
            sell_signals=None,  # Combined não tem sell signals no notebook
            show_volume=True
        )

    def render_vix_weekly(self, chart_config: Dict):
        """Renderiza VIX Weekly com EMA como no notebook"""
        asset = self._get_asset(chart_config)

        # VIX com EMA como no notebook
        vix_series = asset.get_close_series()
        vix_sma_9 = ExponentialMovingAverage(period=7).calculate(vix_series)
        vix_sma_20 = ExponentialMovingAverage(period=14).calculate(vix_series)

        # Renderiza múltiplos indicadores em subplots
        data = {
            "VIX": vix_series,
            "EMA 7": vix_sma_9,
            "EMA 14": vix_sma_20
        }

        ChartPlotter.plot_multiple_indicators(
            data=data,
            title=f"{chart_config['name']} - VIX Analysis"
        )

    def render_spy_weekly_rsi(self, chart_config: Dict):
        """Renderiza SPY Weekly RSI como no notebook"""
        asset = self._get_asset(chart_config)

        # SPY RSI como no notebook
        spy_weekly_rsi = Rsi(period=14)
        spy_weekly_rsi_values = spy_weekly_rsi.calculate(asset)
        spy_weekly_rsi_signals = RsiSignal(rsi=spy_weekly_rsi, buy_threshold=28, sell_threshold=85)
        spy_weekly_rsi_signals_gen = spy_weekly_rsi_signals.generate_signals(asset)
        spy_weekly_rsi_sma_20 = SimpleMovingAverage(period=20).calculate(spy_weekly_rsi_values)
        spy_weekly_rsi_buy = spy_weekly_rsi_signals_gen == -1
        spy_weekly_rsi_sell = spy_weekly_rsi_signals_gen == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=spy_weekly_rsi_values,
            title=f"{chart_config['name']} - RSI",
            buy_signals=spy_weekly_rsi_buy,
            sell_signals=spy_weekly_rsi_sell,
            indicator_name="RSI"
        )

    def render_forex_daily_rsi(self, chart_config: Dict):
        """Renderiza FOREX Daily RSI como no notebook"""
        asset = self._get_asset(chart_config)

        # FOREX RSI como no notebook
        forex_rsi_daily = self.strategy
        forex_rsi_values = forex_rsi_daily.get_indicator_default('daily', 'rsi').calculate(asset)
        forex_rsi_signals = forex_rsi_daily.get_signal('daily', 'rsi').generate_signals(asset)
        forex_rsi_sma_20 = SimpleMovingAverage(period=20).calculate(forex_rsi_values)
        forex_rsi_buy = forex_rsi_signals == -1
        forex_rsi_sell = forex_rsi_signals == 1

        # Renderiza
        ChartPlotter.plot_indicator_with_signals(
            price_data=asset.get_close_series(),
            indicator_data=forex_rsi_values,
            title=f"{chart_config['name']} - RSI",
            buy_signals=forex_rsi_buy,
            sell_signals=forex_rsi_sell,
            indicator_name="RSI"
        )

    def render_btc_multi_timeframe(self, chart_config: Dict):
        """Renderiza BTC em múltiplos timeframes como no notebook"""
        asset = self._get_asset(chart_config)

        # Obter dados em múltiplos timeframes
        btc_daily = MarketAsset(symbol="BTC-USD", provider=YahooProvider(period="4y", interval="1d"))
        btc_weekly = MarketAsset(symbol="BTC-USD", provider=YahooProvider(period="8y", interval="1wk"))
        btc_monthly = MarketAsset(symbol="BTC-USD", provider=YahooProvider(period="8y", interval="1mo"))

        daily_prices = btc_daily.get_close_series()
        weekly_prices = btc_weekly.get_close_series()
        monthly_prices = btc_monthly.get_close_series()

        # Calcular SMAs como no notebook
        sma_200 = SimpleMovingAverage(period=200)
        sma_100 = SimpleMovingAverage(period=100)
        sma_50 = SimpleMovingAverage(period=50)
        sma_20 = SimpleMovingAverage(period=20)

        btc_sma_200 = sma_200.calculate(daily_prices)
        btc_sma_100 = sma_100.calculate(daily_prices)
        btc_sma_50 = sma_50.calculate(daily_prices)
        btc_sma_20 = sma_20.calculate(daily_prices)

        ema_200 = ExponentialMovingAverage(period=200)
        ema_100 = ExponentialMovingAverage(period=100)
        ema_50 = ExponentialMovingAverage(period=50)
        ema_20 = ExponentialMovingAverage(period=20)

        btc_ema_200 = ema_200.calculate(daily_prices)
        btc_ema_100 = ema_100.calculate(daily_prices)
        btc_ema_50 = ema_50.calculate(daily_prices)
        btc_ema_20 = ema_20.calculate(daily_prices)

        # Preparar dados para plotagem múltipla
        data = {
            "Price": daily_prices,
            "SMA 200": btc_sma_200,
            "SMA 100": btc_sma_100,
            "SMA 50": btc_sma_50,
            "SMA 20": btc_sma_20,
            "EMA 200": btc_ema_200,
            "EMA 100": btc_ema_100,
            "EMA 50": btc_ema_50,
            "EMA 20": btc_ema_20
        }

        ChartPlotter.plot_multiple_indicators(
            data=data,
            title=f"{chart_config['name']} - Multiple Timeframes"
        )

    def render_chart(self, chart_config: Dict):
        """Renderiza gráfico específico baseado no notebook"""
        try:
            chart_id = chart_config["id"]

            if chart_id == "rsi_daily":
                self.render_rsi_daily(chart_config)
            elif chart_id == "rsi_weekly":
                self.render_rsi_weekly(chart_config)
            elif chart_id == "stochrsi_daily":
                self.render_stochrsi_daily(chart_config)
            elif chart_id == "bb_daily":
                self.render_bollinger_bands_daily(chart_config)
            elif chart_id == "macd_daily":
                self.render_macd_daily(chart_config)
            elif chart_id == "sharpe_weekly":
                self.render_sharpe_weekly(chart_config)
            elif chart_id == "sortino_weekly":
                self.render_sortino_weekly(chart_config)
            elif chart_id == "combined_daily":
                self.render_combined_daily(chart_config)
            elif chart_id == "vix_weekly":
                self.render_vix_weekly(chart_config)
            elif chart_id == "spy_weekly_rsi":
                self.render_spy_weekly_rsi(chart_config)
            elif chart_id == "forex_daily_rsi":
                self.render_forex_daily_rsi(chart_config)
            elif chart_id == "btc_multi_timeframe":
                self.render_btc_multi_timeframe(chart_config)
            else:
                st.error(f"Gráfico não encontrado: {chart_id}")

        except Exception as e:
            st.error(f"Erro ao renderizar gráfico {chart_config.get('name', 'Unknown')}: {e}")
            st.error("Verifique os dados do ativo ou configurações.")
