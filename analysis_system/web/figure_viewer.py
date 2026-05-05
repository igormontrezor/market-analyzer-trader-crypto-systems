import streamlit as st
import pandas as pd
from typing import List, Dict, Optional, Tuple
import sys
import os

# Adicionar o diretório raiz ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_system_root = os.path.dirname(current_dir)
sys.path.insert(0, analysis_system_root)

# Imports diretos
from assets.asset import MarketAsset
from assets.provider import YahooProvider, BinanceProvider, CoinGeckoProvider
from indicators.indicators import (
    SimpleMovingAverage, ExponentialMovingAverage, Rsi, StochRsi,
    BollingerBands, Macd, SharpeRatio, SortinoRatio
)
from signals.signals import (
    RsiSignal, StochRsiSignal, BollingerBandsSignal,
    MacdSignal, SharpeSignal, SortinoSignal, CombinedSignal
)
from strategies.strategy import BtcStrategy
from plotting.charts import ChartPlotter
from utils.data_aggregator import DataAggregator

class FigureViewer:
    """Visualizador de Figures Compostos do Notebook"""
    
    def __init__(self):
        self.strategy = BtcStrategy()
        self._initialize_assets()
        self._initialize_figures()
    
    def _initialize_assets(self):
        """Inicializa todos os assets como no notebook"""
        # BTC assets (exatamente como no notebook)
        btc_daily_provider = YahooProvider(period="4y", interval="1d")
        self.btc_daily = MarketAsset("BTC-USD", provider=btc_daily_provider)
        
        btc_weekly_provider = YahooProvider(period="8y", interval="1wk")
        self.btc_weekly = MarketAsset("BTC-USD", provider=btc_weekly_provider)
        
        btc_monthly_provider = YahooProvider(period="8y", interval="1mo")
        self.btc_monthly = MarketAsset("BTC-USD", provider=btc_monthly_provider)
        
        # SPY assets
        spy_weekly_provider = YahooProvider(period="8y", interval="1wk")
        self.spy_weekly = MarketAsset("SPY", provider=spy_weekly_provider)
        
        spy_monthly_provider = YahooProvider(period="8y", interval="1mo")
        self.spy_monthly = MarketAsset("SPY", provider=spy_monthly_provider)
        
        # FOREX
        forex_daily_provider = YahooProvider(period="8y", interval="1d")
        self.forex_daily = MarketAsset("EURCHF=X", provider=forex_daily_provider)
        
        # VIX
        vix_provider = YahooProvider(period='7y', interval='1wk')
        self.vix_weekly = MarketAsset('^VIX', provider=vix_provider)
        
        vix_monthly_provider = YahooProvider(period='7y', interval='1mo')
        self.vix_monthly = MarketAsset('^VIX', provider=vix_monthly_provider)
    
    def _initialize_figures(self):
        """Inicializa catálogo de Figures Compostos"""
        self.available_figures = {
            "Figure BTC Daily": {
                "description": "Figure BTC Daily - 6 gráficos compostos (RSI, StochRSI, Bollinger Bands, MACD, Sharpe, Sortino)",
                "render_func": self.render_figure_btc_daily
            },
            "Figure BTC Weekly": {
                "description": "Figure BTC Weekly - 6 gráficos compostos (RSI, StochRSI, Bollinger Bands, MACD, Sharpe, Sortino)",
                "render_func": self.render_figure_btc_weekly
            },
            "Figure BTC Monthly": {
                "description": "Figure BTC Monthly - 6 gráficos compostos (RSI, StochRSI, Bollinger Bands, MACD, Sharpe, Sortino)",
                "render_func": self.render_figure_btc_monthly
            },
            "Figure SPY Weekly": {
                "description": "Figure SPY Weekly - 6 gráficos compostos (RSI, StochRSI, Bollinger Bands, MACD, Sharpe, Sortino)",
                "render_func": self.render_figure_spy_weekly
            },
            "Figure SPY Monthly": {
                "description": "Figure SPY Monthly - 6 gráficos compostos (RSI, StochRSI, Bollinger Bands, MACD, Sharpe, Sortino)",
                "render_func": self.render_figure_spy_monthly
            },
            "Figure FOREX Daily": {
                "description": "Figure FOREX Daily - 6 gráficos compostos (RSI, StochRSI, Bollinger Bands, MACD, Sharpe, Sortino)",
                "render_func": self.render_figure_forex_daily
            },
            "Figure VIX Weekly": {
                "description": "Figure VIX Weekly - 2 gráficos (VIX com EMA 7/14)",
                "render_func": self.render_figure_vix_weekly
            }
        }
    
    def render_figure_btc_daily(self):
        """Renderiza Figure BTC Daily com 6 gráficos compostos"""
        st.subheader("📊 Figure BTC Daily - 6 Gráficos Compostos")
        
        # Layout 2x3 para os 6 gráficos
        col1, col2, col3 = st.columns(3)
        
        # Gráfico 1: RSI Daily
        with col1:
            btc_rsi_daily = self.strategy
            btc_rsi_daily_values = btc_rsi_daily.get_indicator_default('daily', 'rsi').calculate(self.btc_daily)
            btc_rsi_daily_signals = btc_rsi_daily.get_signal('daily', 'rsi').generate_signals(self.btc_daily)
            btc_rsi_daily_sma_20 = SimpleMovingAverage(period=20).calculate(btc_rsi_daily_values)
            btc_rsi_daily_buy = btc_rsi_daily_signals == -1
            btc_rsi_daily_sell = btc_rsi_daily_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_daily.get_close_series(),
                indicator_data=btc_rsi_daily_values,
                title="BTC Daily RSI",
                buy_signals=btc_rsi_daily_buy,
                sell_signals=btc_rsi_daily_sell,
                indicator_name="RSI"
            )
        
        # Gráfico 2: StochRSI Daily
        with col2:
            btc_stochrsi_daily = self.strategy
            stochrsi_values = btc_stochrsi_daily.get_indicator_default('daily', 'stochrsi').calculate(self.btc_daily)
            stochrsi_signals = btc_stochrsi_daily.get_signal('daily', 'stochrsi').generate_signals(self.btc_daily)
            stochrsi_buy = stochrsi_signals == -1
            stochrsi_sell = stochrsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_daily.get_close_series(),
                indicator_data=stochrsi_values,
                title="BTC Daily StochRSI",
                buy_signals=stochrsi_buy,
                sell_signals=stochrsi_sell,
                indicator_name="StochRSI"
            )
        
        # Gráfico 3: Bollinger Bands Daily
        with col3:
            btc_bb_daily = self.strategy
            bb_values = btc_bb_daily.get_indicator_default('daily', 'bb').calculate(self.btc_daily)
            bb_strategy = btc_bb_daily.get_signal('daily', 'bb').generate_signals(self.btc_daily)
            bb_buy = bb_strategy == -1
            bb_sell = bb_strategy == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_daily.get_close_series(),
                indicator_data=bb_values,
                title="BTC Daily Bollinger Bands",
                buy_signals=bb_buy,
                sell_signals=bb_sell,
                indicator_name="BB"
            )
        
        # Segunda linha
        col4, col5, col6 = st.columns(3)
        
        # Gráfico 4: MACD Daily
        with col4:
            btc_macd_daily = self.strategy
            macd_value = btc_macd_daily.get_indicator_default('daily', 'macd').calculate(self.btc_daily)
            macd_signals = btc_macd_daily.get_signal('daily', 'macd').generate_signals(self.btc_daily)
            macd_buy = macd_signals == 1
            macd_sell = macd_signals == -1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_daily.get_close_series(),
                indicator_data=macd_value,
                title="BTC Daily MACD",
                buy_signals=macd_buy,
                sell_signals=macd_sell,
                indicator_name="MACD"
            )
        
        # Gráfico 5: Sharpe Daily
        with col5:
            btc_sharpe_daily = self.strategy
            sharpe_values = btc_sharpe_daily.get_indicator_default('daily', 'sharpe').calculate(self.btc_daily)
            sharpe_signals = btc_sharpe_daily.get_signal('daily', 'sharpe').generate_signals(self.btc_daily)
            sharpe_buy = sharpe_signals == -1
            sharpe_sell = sharpe_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_daily.get_close_series(),
                indicator_data=sharpe_values,
                title="BTC Daily Sharpe",
                buy_signals=sharpe_buy,
                sell_signals=sharpe_sell,
                indicator_name="Sharpe"
            )
        
        # Gráfico 6: Sortino Daily
        with col6:
            btc_sortino_daily = self.strategy
            sortino_values = btc_sortino_daily.get_indicator_default('daily', 'sortino').calculate(self.btc_daily)
            sortino_signals = btc_sortino_daily.get_signal('daily', 'sortino').generate_signals(self.btc_daily)
            sortino_buy = sortino_signals == -1
            sortino_sell = sortino_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_daily.get_close_series(),
                indicator_data=sortino_values,
                title="BTC Daily Sortino",
                buy_signals=sortino_buy,
                sell_signals=sortino_sell,
                indicator_name="Sortino"
            )
    
    def render_figure_btc_weekly(self):
        """Renderiza Figure BTC Weekly com 6 gráficos compostos"""
        st.subheader("📊 Figure BTC Weekly - 6 Gráficos Compostos")
        
        # Layout 2x3 para os 6 gráficos
        col1, col2, col3 = st.columns(3)
        
        # Gráfico 1: RSI Weekly
        with col1:
            btc_rsi_weekly = Rsi(period=14)
            btc_rsi_values_weekly = btc_rsi_weekly.calculate(self.btc_weekly)
            btc_rsi_signals_weekly = RsiSignal(rsi=btc_rsi_weekly, buy_threshold=20, sell_threshold=80)
            btc_rsi_signals_weekly_gen = btc_rsi_signals_weekly.generate_signals(self.btc_weekly)
            rsi_weekly_sma_20 = SimpleMovingAverage(period=20).calculate(btc_rsi_values_weekly)
            btc_rsi_buy = btc_rsi_signals_weekly_gen == -1
            btc_rsi_sell = btc_rsi_signals_weekly_gen == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_weekly.get_close_series(),
                indicator_data=btc_rsi_values_weekly,
                title="BTC Weekly RSI",
                buy_signals=btc_rsi_buy,
                sell_signals=btc_rsi_sell,
                indicator_name="RSI Weekly"
            )
        
        # Gráfico 2: StochRSI Weekly
        with col2:
            btc_stochrsi_weekly = self.strategy
            stochrsi_values = btc_stochrsi_weekly.get_indicator_default('weekly', 'stochrsi').calculate(self.btc_weekly)
            stochrsi_signals = btc_stochrsi_weekly.get_signal('weekly', 'stochrsi').generate_signals(self.btc_weekly)
            stochrsi_buy = stochrsi_signals == -1
            stochrsi_sell = stochrsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_weekly.get_close_series(),
                indicator_data=stochrsi_values,
                title="BTC Weekly StochRSI",
                buy_signals=stochrsi_buy,
                sell_signals=stochrsi_sell,
                indicator_name="StochRSI"
            )
        
        # Gráfico 3: Bollinger Bands Weekly
        with col3:
            btc_bb_weekly = self.strategy
            bb_values = btc_bb_weekly.get_indicator_default('weekly', 'bb').calculate(self.btc_weekly)
            bb_strategy = btc_bb_weekly.get_signal('weekly', 'bb').generate_signals(self.btc_weekly)
            bb_buy = bb_strategy == -1
            bb_sell = bb_strategy == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_weekly.get_close_series(),
                indicator_data=bb_values,
                title="BTC Weekly Bollinger Bands",
                buy_signals=bb_buy,
                sell_signals=bb_sell,
                indicator_name="BB"
            )
        
        # Segunda linha
        col4, col5, col6 = st.columns(3)
        
        # Gráfico 4: MACD Weekly
        with col4:
            btc_macd_weekly = self.strategy
            macd_value = btc_macd_weekly.get_indicator_default('weekly', 'macd').calculate(self.btc_weekly)
            macd_signals = btc_macd_weekly.get_signal('weekly', 'macd').generate_signals(self.btc_weekly)
            macd_buy = macd_signals == 1
            macd_sell = macd_signals == -1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_weekly.get_close_series(),
                indicator_data=macd_value,
                title="BTC Weekly MACD",
                buy_signals=macd_buy,
                sell_signals=macd_sell,
                indicator_name="MACD"
            )
        
        # Gráfico 5: Sharpe Weekly
        with col5:
            btc_sharpe_weekly = self.strategy
            sharpe_values = btc_sharpe_weekly.get_indicator_default('weekly', 'sharpe').calculate(self.btc_weekly)
            sharpe_signals = btc_sharpe_weekly.get_signal('weekly', 'sharpe').generate_signals(self.btc_weekly)
            sharpe_buy = sharpe_signals == -1
            sharpe_sell = sharpe_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_weekly.get_close_series(),
                indicator_data=sharpe_values,
                title="BTC Weekly Sharpe",
                buy_signals=sharpe_buy,
                sell_signals=sharpe_sell,
                indicator_name="Sharpe"
            )
        
        # Gráfico 6: Sortino Weekly
        with col6:
            btc_sortino_weekly = self.strategy
            sortino_values = btc_sortino_weekly.get_indicator_default('weekly', 'sortino').calculate(self.btc_weekly)
            sortino_signals = btc_sortino_weekly.get_signal('weekly', 'sortino').generate_ma_signals(self.btc_weekly, ma_fast=20, ma_slow=70)
            sortino_buy = sortino_signals == -1
            sortino_sell = sortino_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_weekly.get_close_series(),
                indicator_data=sortino_values,
                title="BTC Weekly Sortino",
                buy_signals=sortino_buy,
                sell_signals=sortino_sell,
                indicator_name="Sortino"
            )
    
    def render_figure_btc_monthly(self):
        """Renderiza Figure BTC Monthly com 6 gráficos compostos"""
        st.subheader("📊 Figure BTC Monthly - 6 Gráficos Compostos")
        
        # Layout 2x3 para os 6 gráficos
        col1, col2, col3 = st.columns(3)
        
        # Gráfico 1: RSI Monthly
        with col1:
            btc_rsi_monthly = Rsi(period=14)
            btc_rsi_values_monthly = btc_rsi_monthly.calculate(self.btc_monthly)
            btc_rsi_signals_monthly = RsiSignal(rsi=btc_rsi_monthly, buy_threshold=25, sell_threshold=80)
            btc_rsi_signals_monthly_gen = btc_rsi_signals_monthly.generate_signals(self.btc_monthly)
            rsi_sma_20_monthly = SimpleMovingAverage(period=16).calculate(btc_rsi_values_monthly)
            btc_rsi_buy_monthly = btc_rsi_signals_monthly_gen == -1
            btc_rsi_sell_monthly = btc_rsi_signals_monthly_gen == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_monthly.get_close_series(),
                indicator_data=btc_rsi_values_monthly,
                title="BTC Monthly RSI",
                buy_signals=btc_rsi_buy_monthly,
                sell_signals=btc_rsi_sell_monthly,
                indicator_name="RSI Monthly"
            )
        
        # Gráfico 2: StochRSI Monthly
        with col2:
            btc_stochrsi_monthly = self.strategy
            stochrsi_values = btc_stochrsi_monthly.get_indicator_default('monthly', 'stochrsi').calculate(self.btc_monthly)
            stochrsi_signals = btc_stochrsi_monthly.get_signal('monthly', 'stochrsi').generate_signals(self.btc_monthly)
            stochrsi_buy = stochrsi_signals == -1
            stochrsi_sell = stochrsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_monthly.get_close_series(),
                indicator_data=stochrsi_values,
                title="BTC Monthly StochRSI",
                buy_signals=stochrsi_buy,
                sell_signals=stochrsi_sell,
                indicator_name="StochRSI"
            )
        
        # Gráfico 3: Bollinger Bands Monthly
        with col3:
            btc_bb_monthly = self.strategy
            bb_values = btc_bb_monthly.get_indicator_default('monthly', 'bb').calculate(self.btc_monthly)
            bb_strategy = btc_bb_monthly.get_signal('monthly', 'bb').generate_signals(self.btc_monthly)
            bb_buy = bb_strategy == -1
            bb_sell = bb_strategy == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_monthly.get_close_series(),
                indicator_data=bb_values,
                title="BTC Monthly Bollinger Bands",
                buy_signals=bb_buy,
                sell_signals=bb_sell,
                indicator_name="BB"
            )
        
        # Segunda linha
        col4, col5, col6 = st.columns(3)
        
        # Gráfico 4: MACD Monthly
        with col4:
            btc_macd_monthly = self.strategy
            macd_value = btc_macd_monthly.get_indicator_default('monthly', 'macd').calculate(self.btc_monthly)
            macd_signals = btc_macd_monthly.get_signal('monthly', 'macd').generate_signals(self.btc_monthly)
            macd_buy = macd_signals == 1
            macd_sell = macd_signals == -1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_monthly.get_close_series(),
                indicator_data=macd_value,
                title="BTC Monthly MACD",
                buy_signals=macd_buy,
                sell_signals=macd_sell,
                indicator_name="MACD"
            )
        
        # Gráfico 5: Sharpe Monthly
        with col5:
            btc_sharpe_monthly = self.strategy
            sharpe_values = btc_sharpe_monthly.get_indicator_default('monthly', 'sharpe').calculate(self.btc_monthly)
            sharpe_signals = btc_sharpe_monthly.get_signal('monthly', 'sharpe').generate_signals(self.btc_monthly)
            sharpe_buy = sharpe_signals == -1
            sharpe_sell = sharpe_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_monthly.get_close_series(),
                indicator_data=sharpe_values,
                title="BTC Monthly Sharpe",
                buy_signals=sharpe_buy,
                sell_signals=sharpe_sell,
                indicator_name="Sharpe"
            )
        
        # Gráfico 6: Sortino Monthly
        with col6:
            btc_sortino_monthly = self.strategy
            sortino_values = btc_sortino_monthly.get_indicator_default('monthly', 'sortino').calculate(self.btc_monthly)
            sortino_signals = btc_sortino_monthly.get_signal('monthly', 'sortino').generate_ma_signals(self.btc_monthly, ma_fast=20, ma_slow=70)
            sortino_buy = sortino_signals == -1
            sortino_sell = sortino_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.btc_monthly.get_close_series(),
                indicator_data=sortino_values,
                title="BTC Monthly Sortino",
                buy_signals=sortino_buy,
                sell_signals=sortino_sell,
                indicator_name="Sortino"
            )
    
    def render_figure_spy_weekly(self):
        """Renderiza Figure SPY Weekly com 6 gráficos compostos"""
        st.subheader("📊 Figure SPY Weekly - 6 Gráficos Compostos")
        
        # Layout 2x3 para os 6 gráficos
        col1, col2, col3 = st.columns(3)
        
        # Gráfico 1: RSI Weekly
        with col1:
            spy_weekly_rsi = Rsi(period=14)
            spy_weekly_rsi_values = spy_weekly_rsi.calculate(self.spy_weekly)
            spy_weekly_rsi_signals = RsiSignal(rsi=spy_weekly_rsi, buy_threshold=28, sell_threshold=85)
            spy_weekly_rsi_signals_gen = spy_weekly_rsi_signals.generate_signals(self.spy_weekly)
            spy_weekly_rsi_sma_20 = SimpleMovingAverage(period=20).calculate(spy_weekly_rsi_values)
            spy_weekly_rsi_buy = spy_weekly_rsi_signals_gen == -1
            spy_weekly_rsi_sell = spy_weekly_rsi_signals_gen == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_weekly.get_close_series(),
                indicator_data=spy_weekly_rsi_values,
                title="SPY Weekly RSI",
                buy_signals=spy_weekly_rsi_buy,
                sell_signals=spy_weekly_rsi_sell,
                indicator_name="RSI"
            )
        
        # Gráfico 2: StochRSI Weekly
        with col2:
            spy_stochrsi_weekly = self.strategy
            stochrsi_values = spy_stochrsi_weekly.get_indicator_default('weekly', 'stochrsi').calculate(self.spy_weekly)
            stochrsi_signals = spy_stochrsi_weekly.get_signal('weekly', 'stochrsi').generate_signals(self.spy_weekly)
            stochrsi_buy = stochrsi_signals == -1
            stochrsi_sell = stochrsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_weekly.get_close_series(),
                indicator_data=stochrsi_values,
                title="SPY Weekly StochRSI",
                buy_signals=stochrsi_buy,
                sell_signals=stochrsi_sell,
                indicator_name="StochRSI"
            )
        
        # Gráfico 3: Bollinger Bands Weekly
        with col3:
            spy_bb_weekly = self.strategy
            bb_values = spy_bb_weekly.get_indicator_default('weekly', 'bb').calculate(self.spy_weekly)
            bb_strategy = spy_bb_weekly.get_signal('weekly', 'bb').generate_signals(self.spy_weekly)
            bb_buy = bb_strategy == -1
            bb_sell = bb_strategy == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_weekly.get_close_series(),
                indicator_data=bb_values,
                title="SPY Weekly Bollinger Bands",
                buy_signals=bb_buy,
                sell_signals=bb_sell,
                indicator_name="BB"
            )
        
        # Segunda linha
        col4, col5, col6 = st.columns(3)
        
        # Gráfico 4: MACD Weekly
        with col4:
            spy_macd_weekly = self.strategy
            macd_value = spy_macd_weekly.get_indicator_default('weekly', 'macd').calculate(self.spy_weekly)
            macd_signals = spy_macd_weekly.get_signal('weekly', 'macd').generate_signals(self.spy_weekly)
            macd_buy = macd_signals == 1
            macd_sell = macd_signals == -1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_weekly.get_close_series(),
                indicator_data=macd_value,
                title="SPY Weekly MACD",
                buy_signals=macd_buy,
                sell_signals=macd_sell,
                indicator_name="MACD"
            )
        
        # Gráfico 5: Sharpe Weekly
        with col5:
            spy_sharpe_weekly = self.strategy
            sharpe_values = spy_sharpe_weekly.get_indicator_default('weekly', 'sharpe').calculate(self.spy_weekly)
            sharpe_signals = spy_sharpe_weekly.get_signal('weekly', 'sharpe').generate_signals(self.spy_weekly)
            sharpe_buy = sharpe_signals == -1
            sharpe_sell = sharpe_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_weekly.get_close_series(),
                indicator_data=sharpe_values,
                title="SPY Weekly Sharpe",
                buy_signals=sharpe_buy,
                sell_signals=sharpe_sell,
                indicator_name="Sharpe"
            )
        
        # Gráfico 6: Sortino Weekly
        with col6:
            spy_sortino_weekly = self.strategy
            sortino_values = spy_sortino_weekly.get_indicator_default('weekly', 'sortino').calculate(self.spy_weekly)
            sortino_signals = spy_sortino_weekly.get_signal('weekly', 'sortino').generate_ma_signals(self.spy_weekly, ma_fast=20, ma_slow=70)
            sortino_buy = sortino_signals == -1
            sortino_sell = sortino_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_weekly.get_close_series(),
                indicator_data=sortino_values,
                title="SPY Weekly Sortino",
                buy_signals=sortino_buy,
                sell_signals=sortino_sell,
                indicator_name="Sortino"
            )
    
    def render_figure_spy_monthly(self):
        """Renderiza Figure SPY Monthly com 6 gráficos compostos"""
        st.subheader("📊 Figure SPY Monthly - 6 Gráficos Compostos")
        
        # Layout 2x3 para os 6 gráficos
        col1, col2, col3 = st.columns(3)
        
        # Gráfico 1: RSI Monthly
        with col1:
            spy_rsi_monthly = Rsi(period=14)
            spy_rsi_values_monthly = spy_rsi_monthly.calculate(self.spy_monthly)
            spy_rsi_signals_monthly = RsiSignal(rsi=spy_rsi_monthly, buy_threshold=25, sell_threshold=80)
            spy_rsi_signals_monthly_gen = spy_rsi_signals_monthly.generate_signals(self.spy_monthly)
            spy_rsi_sma_20_monthly = SimpleMovingAverage(period=9).calculate(spy_rsi_values_monthly)
            spy_rsi_buy_monthly = spy_rsi_signals_monthly_gen == -1
            spy_rsi_sell_monthly = spy_rsi_signals_monthly_gen == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_monthly.get_close_series(),
                indicator_data=spy_rsi_values_monthly,
                title="SPY Monthly RSI",
                buy_signals=spy_rsi_buy_monthly,
                sell_signals=spy_rsi_sell_monthly,
                indicator_name="RSI"
            )
        
        # Gráfico 2: StochRSI Monthly
        with col2:
            spy_stochrsi_monthly = self.strategy
            stochrsi_values = spy_stochrsi_monthly.get_indicator_default('monthly', 'stochrsi').calculate(self.spy_monthly)
            stochrsi_signals = spy_stochrsi_monthly.get_signal('monthly', 'stochrsi').generate_signals(self.spy_monthly)
            stochrsi_buy = stochrsi_signals == -1
            stochrsi_sell = stochrsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_monthly.get_close_series(),
                indicator_data=stochrsi_values,
                title="SPY Monthly StochRSI",
                buy_signals=stochrsi_buy,
                sell_signals=stochrsi_sell,
                indicator_name="StochRSI"
            )
        
        # Gráfico 3: Bollinger Bands Monthly
        with col3:
            spy_bb_monthly = self.strategy
            bb_values = spy_bb_monthly.get_indicator_default('monthly', 'bb').calculate(self.spy_monthly)
            bb_strategy = spy_bb_monthly.get_signal('monthly', 'bb').generate_signals(self.spy_monthly)
            bb_buy = bb_strategy == -1
            bb_sell = bb_strategy == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_monthly.get_close_series(),
                indicator_data=bb_values,
                title="SPY Monthly Bollinger Bands",
                buy_signals=bb_buy,
                sell_signals=bb_sell,
                indicator_name="BB"
            )
        
        # Segunda linha
        col4, col5, col6 = st.columns(3)
        
        # Gráfico 4: MACD Monthly
        with col4:
            spy_macd_monthly = self.strategy
            macd_value = spy_macd_monthly.get_indicator_default('monthly', 'macd').calculate(self.spy_monthly)
            macd_signals = spy_macd_monthly.get_signal('monthly', 'macd').generate_signals(self.spy_monthly)
            macd_buy = macd_signals == 1
            macd_sell = macd_signals == -1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_monthly.get_close_series(),
                indicator_data=macd_value,
                title="SPY Monthly MACD",
                buy_signals=macd_buy,
                sell_signals=macd_sell,
                indicator_name="MACD"
            )
        
        # Gráfico 5: Sharpe Monthly
        with col5:
            spy_sharpe_monthly = self.strategy
            sharpe_values = spy_sharpe_monthly.get_indicator_default('monthly', 'sharpe').calculate(self.spy_monthly)
            sharpe_signals = spy_sharpe_monthly.get_signal('monthly', 'sharpe').generate_signals(self.spy_monthly)
            sharpe_buy = sharpe_signals == -1
            sharpe_sell = sharpe_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_monthly.get_close_series(),
                indicator_data=sharpe_values,
                title="SPY Monthly Sharpe",
                buy_signals=sharpe_buy,
                sell_signals=sharpe_sell,
                indicator_name="Sharpe"
            )
        
        # Gráfico 6: Sortino Monthly
        with col6:
            spy_sortino_monthly = self.strategy
            sortino_values = spy_sortino_monthly.get_indicator_default('monthly', 'sortino').calculate(self.spy_monthly)
            sortino_signals = spy_sortino_monthly.get_signal('monthly', 'sortino').generate_ma_signals(self.spy_monthly, ma_fast=20, ma_slow=70)
            sortino_buy = sortino_signals == -1
            sortino_sell = sortino_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.spy_monthly.get_close_series(),
                indicator_data=sortino_values,
                title="SPY Monthly Sortino",
                buy_signals=sortino_buy,
                sell_signals=sortino_sell,
                indicator_name="Sortino"
            )
    
    def render_figure_forex_daily(self):
        """Renderiza Figure FOREX Daily com 6 gráficos compostos"""
        st.subheader("📊 Figure FOREX Daily - 6 Gráficos Compostos")
        
        # Layout 2x3 para os 6 gráficos
        col1, col2, col3 = st.columns(3)
        
        # Gráfico 1: RSI Daily
        with col1:
            forex_rsi_daily = self.strategy
            forex_rsi_values = forex_rsi_daily.get_indicator_default('daily', 'rsi').calculate(self.forex_daily)
            forex_rsi_signals = forex_rsi_daily.get_signal('daily', 'rsi').generate_signals(self.forex_daily)
            forex_rsi_sma_20 = SimpleMovingAverage(period=20).calculate(forex_rsi_values)
            forex_rsi_buy = forex_rsi_signals == -1
            forex_rsi_sell = forex_rsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.forex_daily.get_close_series(),
                indicator_data=forex_rsi_values,
                title="FOREX Daily RSI",
                buy_signals=forex_rsi_buy,
                sell_signals=forex_rsi_sell,
                indicator_name="RSI"
            )
        
        # Gráfico 2: StochRSI Daily
        with col2:
            forex_stochrsi_daily = self.strategy
            stochrsi_values = forex_stochrsi_daily.get_indicator_default('daily', 'stochrsi').calculate(self.forex_daily)
            stochrsi_signals = forex_stochrsi_daily.get_signal('daily', 'stochrsi').generate_signals(self.forex_daily)
            stochrsi_buy = stochrsi_signals == -1
            stochrsi_sell = stochrsi_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.forex_daily.get_close_series(),
                indicator_data=stochrsi_values,
                title="FOREX Daily StochRSI",
                buy_signals=stochrsi_buy,
                sell_signals=stochrsi_sell,
                indicator_name="StochRSI"
            )
        
        # Gráfico 3: Bollinger Bands Daily
        with col3:
            forex_bb_daily = self.strategy
            bb_values = forex_bb_daily.get_indicator_default('daily', 'bb').calculate(self.forex_daily)
            bb_strategy = forex_bb_daily.get_signal('daily', 'bb').generate_signals(self.forex_daily)
            bb_buy = bb_strategy == -1
            bb_sell = bb_strategy == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.forex_daily.get_close_series(),
                indicator_data=bb_values,
                title="FOREX Daily Bollinger Bands",
                buy_signals=bb_buy,
                sell_signals=bb_sell,
                indicator_name="BB"
            )
        
        # Segunda linha
        col4, col5, col6 = st.columns(3)
        
        # Gráfico 4: MACD Daily
        with col4:
            forex_macd_daily = self.strategy
            macd_value = forex_macd_daily.get_indicator_default('daily', 'macd').calculate(self.forex_daily)
            macd_signals = forex_macd_daily.get_signal('daily', 'macd').generate_signals(self.forex_daily)
            macd_buy = macd_signals == 1
            macd_sell = macd_signals == -1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.forex_daily.get_close_series(),
                indicator_data=macd_value,
                title="FOREX Daily MACD",
                buy_signals=macd_buy,
                sell_signals=macd_sell,
                indicator_name="MACD"
            )
        
        # Gráfico 5: Sharpe Daily
        with col5:
            forex_sharpe_daily = self.strategy
            sharpe_values = forex_sharpe_daily.get_indicator_default('daily', 'sharpe').calculate(self.forex_daily)
            sharpe_signals = forex_sharpe_daily.get_signal('daily', 'sharpe').generate_signals(self.forex_daily)
            sharpe_buy = sharpe_signals == -1
            sharpe_sell = sharpe_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.forex_daily.get_close_series(),
                indicator_data=sharpe_values,
                title="FOREX Daily Sharpe",
                buy_signals=sharpe_buy,
                sell_signals=sharpe_sell,
                indicator_name="Sharpe"
            )
        
        # Gráfico 6: Sortino Daily
        with col6:
            forex_sortino_daily = self.strategy
            sortino_values = forex_sortino_daily.get_indicator_default('daily', 'sortino').calculate(self.forex_daily)
            sortino_signals = forex_sortino_daily.get_signal('daily', 'sortino').generate_signals(self.forex_daily)
            sortino_buy = sortino_signals == -1
            sortino_sell = sortino_signals == 1
            
            ChartPlotter.plot_indicator_with_signals(
                price_data=self.forex_daily.get_close_series(),
                indicator_data=sortino_values,
                title="FOREX Daily Sortino",
                buy_signals=sortino_buy,
                sell_signals=sortino_sell,
                indicator_name="Sortino"
            )
    
    def render_figure_vix_weekly(self):
        """Renderiza Figure VIX Weekly com 2 gráficos"""
        st.subheader("📊 Figure VIX Weekly - 2 Gráficos")
        
        # Layout 2 colunas
        col1, col2 = st.columns(2)
        
        # Gráfico 1: VIX Weekly com EMA
        with col1:
            vix_series = self.vix_weekly.get_close_series()
            vix_sma_9 = ExponentialMovingAverage(period=7).calculate(vix_series)
            vix_sma_20 = ExponentialMovingAverage(period=14).calculate(vix_series)
            
            data = {
                "VIX": vix_series,
                "EMA 7": vix_sma_9,
                "EMA 14": vix_sma_20
            }
            
            ChartPlotter.plot_multiple_indicators(
                data=data,
                title="VIX Weekly Analysis"
            )
        
        # Gráfico 2: VIX Monthly com EMA
        with col2:
            vix_monthly_series = self.vix_monthly.get_close_series()
            vix_sma_7_monthly = ExponentialMovingAverage(period=7).calculate(vix_monthly_series)
            vix_sma_14_monthly = ExponentialMovingAverage(period=14).calculate(vix_monthly_series)
            
            data = {
                "VIX": vix_monthly_series,
                "EMA 7": vix_sma_7_monthly,
                "EMA 14": vix_sma_14_monthly
            }
            
            ChartPlotter.plot_multiple_indicators(
                data=data,
                title="VIX Monthly Analysis"
            )
    
    def run(self):
        """Executa o visualizador de Figures"""
        st.set_page_config(page_title="Market Analysis Figure Viewer", layout="wide")
        
        st.title("📊 Market Analysis Figure Viewer")
        st.markdown("Visualizador de **Figures Compostas** do notebook `market_analysis_oop.ipynb`")
        st.markdown("Cada Figure contém **múltiplos gráficos** com os mesmos indicadores e sinais")
        
        # Sidebar para seleção
        with st.sidebar:
            st.header("📈 Selecione as Figures")
            st.info("✅ Cada Figure = 6 gráficos compostos")
            st.info("✅ Mesmos indicadores e sinais do notebook")
            
            # Seleção múltipla (até 3 figures)
            selected_figures = []
            for i in range(3):
                figure_options = list(self.available_figures.keys())
                selected = st.selectbox(
                    f"Figure {i+1}",
                    options=figure_options,
                    key=f"figure_{i}"
                )
                if selected:
                    selected_figures.append(selected)
            
            render_button = st.button("🚀 Renderizar Figures Selecionadas", type="primary")
        
        # Área principal
        if selected_figures and render_button:
            st.header("📊 Figures Compostas do Notebook")
            
            for i, figure_name in enumerate(selected_figures, 1):
                if figure_name in self.available_figures:
                    figure_info = self.available_figures[figure_name]
                    
                    st.markdown(f"### {i}. {figure_name}")
                    st.markdown(f"**{figure_info['description']}**")
                    
                    # Renderiza a figure composta
                    try:
                        figure_info['render_func']()
                    except Exception as e:
                        st.error(f"Erro ao renderizar {figure_name}: {e}")
                    
                    st.divider()
        
        elif render_button and not selected_figures:
            st.warning("⚠️ Selecione pelo menos uma Figure para renderizar")
        
        else:
            st.info("👈 Selecione até 3 Figures na barra lateral e clique em 'Renderizar Figures Selecionadas'")
        
        # Catálogo completo
        st.markdown("---")
        st.header("📋 Catálogo Completo de Figures")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**🪙 BTC Figures:**")
            st.write("• Figure BTC Daily")
            st.write("• Figure BTC Weekly")
            st.write("• Figure BTC Monthly")
            
            st.write("**📈 SPY Figures:**")
            st.write("• Figure SPY Weekly")
            st.write("• Figure SPY Monthly")
        
        with col2:
            st.write("**💰 FOREX Figures:**")
            st.write("• Figure FOREX Daily")
            
            st.write("**📊 VIX Figures:**")
            st.write("• Figure VIX Weekly")
        
        st.markdown("---")
        st.markdown("**💡 Como funciona:**")
        st.markdown("1. **Selecione** até 3 Figures na barra lateral")
        st.markdown("2. **Clique** em 'Renderizar Figures Selecionadas'")
        st.markdown("3. **Veja** as Figures compostas com múltiplos gráficos")
        st.markdown("**🎯 Cada Figure contém 6 gráficos com indicadores e sinais idênticos ao notebook!**")

if __name__ == "__main__":
    app = FigureViewer()
    app.run()
