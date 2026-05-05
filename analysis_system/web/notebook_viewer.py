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

class NotebookViewer:
    """Visualizador que reproduz exatamente os gráficos do notebook"""
    
    def __init__(self):
        self.strategy = BtcStrategy()
        self._initialize_assets()
        self._initialize_charts()
    
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
        
        # FOREX
        forex_daily_provider = YahooProvider(period="8y", interval="1d")
        self.forex_daily = MarketAsset("EURCHF=X", provider=forex_daily_provider)
        
        # VIX
        vix_provider = YahooProvider(period='7y', interval='1wk')
        self.vix_weekly = MarketAsset('^VIX', provider=vix_provider)
    
    def _initialize_charts(self):
        """Inicializa catálogo de gráficos baseado no notebook"""
        self.available_charts = {
            # RSI Charts (exatamente como no notebook)
            "BTC Daily RSI": {
                "description": "BTC Daily RSI com sinais buy/sell (thresholds: 25/80)",
                "render_func": self.render_btc_daily_rsi
            },
            "BTC Weekly RSI": {
                "description": "BTC Weekly RSI com sinais de longo prazo (thresholds: 20/80)",
                "render_func": self.render_btc_weekly_rsi
            },
            "BTC Monthly RSI": {
                "description": "BTC Monthly RSI com sinais (thresholds: 25/80)",
                "render_func": self.render_btc_monthly_rsi
            },
            "SPY Weekly RSI": {
                "description": "SPY Weekly RSI para comparação (thresholds: 28/85)",
                "render_func": self.render_spy_weekly_rsi
            },
            "FOREX Daily RSI": {
                "description": "EUR/CHF Daily RSI (thresholds: 25/80)",
                "render_func": self.render_forex_daily_rsi
            },
            
            # StochRSI Charts
            "BTC Daily StochRSI": {
                "description": "BTC Daily StochRSI com sinais (thresholds: 5/95)",
                "render_func": self.render_btc_daily_stochrsi
            },
            
            # Bollinger Bands Charts
            "BTC Daily Bollinger Bands": {
                "description": "BTC Daily Bollinger Bands com sinais de rompimento",
                "render_func": self.render_btc_daily_bollinger
            },
            
            # MACD Charts
            "BTC Daily MACD": {
                "description": "BTC Daily MACD com sinais de cruzamento",
                "render_func": self.render_btc_daily_macd
            },
            
            # Sharpe/Sortino Charts
            "BTC Weekly Sharpe": {
                "description": "BTC Weekly Sharpe Ratio (thresholds: -1.5/2.0)",
                "render_func": self.render_btc_weekly_sharpe
            },
            "BTC Weekly Sortino": {
                "description": "BTC Weekly Sortino Ratio (thresholds: -1.5/4.5)",
                "render_func": self.render_btc_weekly_sortino
            },
            
            # Combined Signal
            "BTC Daily Combined": {
                "description": "BTC Daily Combined Signals (RSI+StochRSI+BB)",
                "render_func": self.render_btc_daily_combined
            },
            
            # Multi-Timeframe
            "BTC Multi-Timeframe": {
                "description": "BTC em múltiplos timeframes com SMA/EMA",
                "render_func": self.render_btc_multi_timeframe
            },
            
            # VIX Charts
            "VIX Weekly": {
                "description": "VIX Weekly com EMA 7 e 14",
                "render_func": self.render_vix_weekly
            }
        }
    
    def render_btc_daily_rsi(self):
        """Renderiza BTC Daily RSI exatamente como no notebook"""
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
    
    def render_btc_weekly_rsi(self):
        """Renderiza BTC Weekly RSI exatamente como no notebook"""
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
    
    def render_btc_monthly_rsi(self):
        """Renderiza BTC Monthly RSI exatamente como no notebook"""
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
    
    def render_spy_weekly_rsi(self):
        """Renderiza SPY Weekly RSI exatamente como no notebook"""
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
    
    def render_forex_daily_rsi(self):
        """Renderiza FOREX Daily RSI exatamente como no notebook"""
        forex_rsi_daily = self.strategy
        forex_rsi_values = forex_rsi_daily.get_indicator_default('daily', 'rsi').calculate(self.forex_daily)
        forex_rsi_signals = forex_rsi_daily.get_signal('daily', 'rsi').generate_signals(self.forex_daily)
        forex_rsi_sma_20 = SimpleMovingAverage(period=20).calculate(forex_rsi_values)
        forex_rsi_buy = forex_rsi_signals == -1
        forex_rsi_sell = forex_rsi_signals == 1
        
        ChartPlotter.plot_indicator_with_signals(
            price_data=self.forex_daily.get_close_series(),
            indicator_data=forex_rsi_values,
            title="FOREX Daily RSI (EUR/CHF)",
            buy_signals=forex_rsi_buy,
            sell_signals=forex_rsi_sell,
            indicator_name="RSI"
        )
    
    def render_btc_daily_stochrsi(self):
        """Renderiza BTC Daily StochRSI exatamente como no notebook"""
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
    
    def render_btc_daily_bollinger(self):
        """Renderiza BTC Daily Bollinger Bands exatamente como no notebook"""
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
    
    def render_btc_daily_macd(self):
        """Renderiza BTC Daily MACD exatamente como no notebook"""
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
    
    def render_btc_weekly_sharpe(self):
        """Renderiza BTC Weekly Sharpe exatamente como no notebook"""
        btc_sharpe_daily = self.strategy
        sharpe_values = btc_sharpe_daily.get_indicator_default('weekly', 'sharpe').calculate(self.btc_weekly)
        sharpe_signals = btc_sharpe_daily.get_signal('weekly', 'sharpe').generate_signals(self.btc_weekly)
        sharpe_sma_slow = SimpleMovingAverage(period=35).calculate(sharpe_values)
        sharpe_sma_fast = SimpleMovingAverage(period=10).calculate(sharpe_values)
        sharpe_buy = sharpe_signals == -1
        sharpe_sell = sharpe_signals == 1
        
        ChartPlotter.plot_indicator_with_signals(
            price_data=self.btc_weekly.get_close_series(),
            indicator_data=sharpe_values,
            title="BTC Weekly Sharpe Ratio",
            buy_signals=sharpe_buy,
            sell_signals=sharpe_sell,
            indicator_name="Sharpe"
        )
    
    def render_btc_weekly_sortino(self):
        """Renderiza BTC Weekly Sortino exatamente como no notebook"""
        btc_sortino_daily = self.strategy
        sortino_values = btc_sortino_daily.get_indicator_default('weekly', 'sortino').calculate(self.btc_weekly)
        sortino_signals = btc_sortino_daily.get_signal('weekly', 'sortino').generate_ma_signals(self.btc_weekly, ma_fast=20, ma_slow=70)
        sortino_sma_14 = SimpleMovingAverage(period=70).calculate(sortino_values)
        sortino_sma_7 = SimpleMovingAverage(period=20).calculate(sortino_values)
        sortino_buy = sortino_signals == -1
        sortino_sell = sortino_signals == 1
        
        ChartPlotter.plot_indicator_with_signals(
            price_data=self.btc_weekly.get_close_series(),
            indicator_data=sortino_values,
            title="BTC Weekly Sortino Ratio",
            buy_signals=sortino_buy,
            sell_signals=sortino_sell,
            indicator_name="Sortino"
        )
    
    def render_btc_daily_combined(self):
        """Renderiza BTC Daily Combined exatamente como no notebook"""
        daily_df = self.btc_daily.get_prices()
        
        combined_signal = self.strategy.get_combined(
            timeframe='daily',
            indicators=['rsi', 'stochrsi', 'bb'],
            weights=[0.5, 0.5, 2.0],
            threshold=3.0,
            min_periods=5,
            window=2
        ).confirm_signals(self.btc_daily)
        
        combined_signal = combined_signal.reindex(daily_df.index).fillna(0)
        combined_buy = combined_signal == -1
        
        ChartPlotter.plot_candlestick_with_signals(
            df=daily_df,
            title="BTC Daily Combined Signals",
            buy_signals=combined_buy,
            sell_signals=None,
            show_volume=True
        )
    
    def render_btc_multi_timeframe(self):
        """Renderiza BTC Multi-Timeframe exatamente como no notebook"""
        # Calcular SMAs como no notebook
        sma_200 = SimpleMovingAverage(period=200)
        sma_100 = SimpleMovingAverage(period=100)
        sma_50 = SimpleMovingAverage(period=50)
        sma_20 = SimpleMovingAverage(period=20)
        
        btc_sma_200 = sma_200.calculate(self.btc_weekly)
        btc_sma_100 = sma_100.calculate(self.btc_weekly)
        btc_sma_50 = sma_50.calculate(self.btc_weekly)
        btc_sma_20 = sma_20.calculate(self.btc_weekly)
        
        ema_200 = ExponentialMovingAverage(period=200)
        ema_100 = ExponentialMovingAverage(period=100)
        ema_50 = ExponentialMovingAverage(period=50)
        ema_20 = ExponentialMovingAverage(period=20)
        
        btc_ema_200 = ema_200.calculate(self.btc_weekly)
        btc_ema_100 = ema_100.calculate(self.btc_weekly)
        btc_ema_50 = ema_50.calculate(self.btc_weekly)
        btc_ema_20 = ema_20.calculate(self.btc_weekly)
        
        # Preparar dados para plotagem múltipla
        data = {
            "Price": self.btc_weekly.get_close_series(),
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
            title="BTC Multi-Timeframe Analysis"
        )
    
    def render_vix_weekly(self):
        """Renderiza VIX Weekly exatamente como no notebook"""
        vix_series = self.vix_weekly.get_close_series()
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
            title="VIX Weekly Analysis"
        )
    
    def run(self):
        """Executa o visualizador de notebook"""
        st.set_page_config(page_title="Market Analysis Notebook Viewer", layout="wide")
        
        st.title("📊 Market Analysis Notebook Viewer")
        st.markdown("Visualizador que reproduz **EXATAMENTE** os gráficos do notebook `market_analysis_oop.ipynb`")
        
        # Sidebar para seleção
        with st.sidebar:
            st.header("📈 Selecione os Gráficos")
            st.info("✅ Todos os gráficos são idênticos ao notebook")
            st.info("✅ Mesmos parâmetros e cálculos")
            
            # Seleção múltipla (até 3 gráficos)
            selected_charts = []
            for i in range(3):
                chart_options = list(self.available_charts.keys())
                selected = st.selectbox(
                    f"Gráfico {i+1}",
                    options=chart_options,
                    key=f"chart_{i}"
                )
                if selected:
                    selected_charts.append(selected)
            
            render_button = st.button("🚀 Renderizar Gráficos Selecionados", type="primary")
        
        # Área principal
        if selected_charts and render_button:
            st.header("📊 Gráficos do Notebook")
            
            for i, chart_name in enumerate(selected_charts, 1):
                if chart_name in self.available_charts:
                    chart_info = self.available_charts[chart_name]
                    
                    st.subheader(f"{i}. {chart_name}")
                    st.markdown(f"**{chart_info['description']}**")
                    
                    # Renderiza o gráfico
                    try:
                        chart_info['render_func']()
                    except Exception as e:
                        st.error(f"Erro ao renderizar {chart_name}: {e}")
                    
                    st.divider()
        
        elif render_button and not selected_charts:
            st.warning("⚠️ Selecione pelo menos um gráfico para renderizar")
        
        else:
            st.info("👈 Selecione até 3 gráficos na barra lateral e clique em 'Renderizar Gráficos Selecionados'")
        
        # Catálogo completo
        st.markdown("---")
        st.header("📋 Catálogo Completo de Gráficos")
        
        # Organizar por categoria
        rsi_charts = [name for name in self.available_charts.keys() if "RSI" in name]
        stoch_charts = [name for name in self.available_charts.keys() if "StochRSI" in name]
        bb_charts = [name for name in self.available_charts.keys() if "Bollinger" in name]
        macd_charts = [name for name in self.available_charts.keys() if "MACD" in name]
        sharpe_charts = [name for name in self.available_charts.keys() if "Sharpe" in name]
        sortino_charts = [name for name in self.available_charts.keys() if "Sortino" in name]
        combined_charts = [name for name in self.available_charts.keys() if "Combined" in name]
        multi_charts = [name for name in self.available_charts.keys() if "Multi-Timeframe" in name]
        vix_charts = [name for name in self.available_charts.keys() if "VIX" in name]
        forex_charts = [name for name in self.available_charts.keys() if "FOREX" in name]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**📈 RSI Charts:**")
            for chart in rsi_charts:
                st.write(f"• {chart}")
            
            st.write("**📊 StochRSI Charts:**")
            for chart in stoch_charts:
                st.write(f"• {chart}")
            
            st.write("**📈 Bollinger Bands:**")
            for chart in bb_charts:
                st.write(f"• {chart}")
        
        with col2:
            st.write("**📊 MACD Charts:**")
            for chart in macd_charts:
                st.write(f"• {chart}")
            
            st.write("**📈 Risk Charts:**")
            st.write("**Sharpe:**")
            for chart in sharpe_charts:
                st.write(f"• {chart}")
            st.write("**Sortino:**")
            for chart in sortino_charts:
                st.write(f"• {chart}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**🔄 Combined & Multi:**")
            for chart in combined_charts:
                st.write(f"• {chart}")
            for chart in multi_charts:
                st.write(f"• {chart}")
            
            st.write("**📊 VIX Charts:**")
            for chart in vix_charts:
                st.write(f"• {chart}")
        
        with col2:
            st.write("**💰 FOREX Charts:**")
            for chart in forex_charts:
                st.write(f"• {chart}")
        
        st.markdown("---")
        st.markdown("**💡 Como funciona:**")
        st.markdown("1. **Selecione** até 3 gráficos na barra lateral")
        st.markdown("2. **Clique** em 'Renderizar Gráficos Selecionados'")
        st.markdown("3. **Veja** os gráficos **EXATAMENTE** como no notebook")
        st.markdown("**🎯 Todos os parâmetros, cálculos e sinais são idênticos ao notebook!**")

if __name__ == "__main__":
    app = NotebookViewer()
    app.run()
