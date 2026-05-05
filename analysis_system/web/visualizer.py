import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
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

class MarketAnalysisWeb:
    """Visualizador web leve para análise de mercado com catálogo de gráficos"""

    def __init__(self):
        self.strategy = BtcStrategy()
        self.available_charts = [
            {
                "name": "RSI Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "rsi",
                "timeframe": "daily",
                "signal": "rsi"
            },
            {
                "name": "RSI Weekly",
                "symbol": "BTC-USD",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "rsi",
                "timeframe": "weekly",
                "signal": "rsi"
            },
            {
                "name": "StochRSI Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "stochrsi",
                "timeframe": "daily",
                "signal": "stochrsi"
            },
            {
                "name": "Bollinger Bands Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "bb",
                "timeframe": "daily",
                "signal": "bb"
            },
            {
                "name": "MACD Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "macd",
                "timeframe": "daily",
                "signal": "macd"
            },
            {
                "name": "Sharpe Ratio Weekly",
                "symbol": "BTC-USD",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "sharpe",
                "timeframe": "weekly",
                "signal": "sharpe"
            },
            {
                "name": "Sortino Ratio Weekly",
                "symbol": "BTC-USD",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "sortino",
                "timeframe": "weekly",
                "signal": "sortino"
            },
            {
                "name": "Combined Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "combined",
                "timeframe": "daily",
                "signal": "combined"
            }
        ]

    def _get_asset(self, symbol: str, provider: str):
        """Cria asset com provider específico"""
        if provider == "yahoo":
            return MarketAsset(symbol=symbol, provider=YahooProvider(period="4y", interval="1d"))
        elif provider == "binance":
            return MarketAsset(symbol=symbol, provider=BinanceProvider(period="10y", interval="1wk"))
        elif provider == "coingecko":
            return MarketAsset(symbol=symbol, provider=CoinGeckoProvider())
        else:
            return MarketAsset(symbol=symbol)

    def _get_indicator_data(self, chart_config: Dict):
        """Obtém dados do indicador e sinais"""
        asset = self._get_asset(chart_config["symbol"], chart_config["provider"])

        # Obtém dados brutos
        prices_df = asset.get_prices()

        # Obtém indicador
        indicator = self.strategy.get_indicator_default(chart_config["timeframe"], chart_config["indicator"])
        indicator_data = indicator.calculate(asset)

        # Obtém sinais
        signal = self.strategy.get_signal(chart_config["timeframe"], chart_config["signal"])
        signals_data = signal.generate_signals(asset)

        return prices_df, indicator_data, signals_data

    def render_chart(self, chart_config: Dict):
        """Renderiza gráfico específico"""
        try:
            prices_df, indicator_data, signals_data = self._get_indicator_data(chart_config)

            if chart_config["indicator"] == "combined":
                # Gráfico combinado com múltiplos sinais
                combined_signal = self.strategy.get_combined(
                    timeframe=chart_config["timeframe"],
                    indicators=['rsi', 'stochrsi', 'bb'],
                    weights=[0.5, 0.5, 2.0],
                    threshold=3.0,
                    min_periods=5,
                    window=2
                ).confirm_signals(prices_df.index[0].asset)

                ChartPlotter.plot_candlestick_with_signals(
                    df=prices_df,
                    title=f"{chart_config['name']} - Combined Signals",
                    buy_signals=combined_signal == -1,
                    sell_signals=combined_signal == 1,
                    show_volume=True
                )
            else:
                # Gráfico de indicador com sinais
                ChartPlotter.plot_indicator_with_signals(
                    price_data=prices_df['Close'],
                    indicator_data=indicator_data,
                    title=f"{chart_config['name']} - {chart_config['indicator'].upper()}",
                    buy_signals=signals_data == -1,
                    sell_signals=signals_data == 1,
                    indicator_name=chart_config["indicator"].upper()
                )

        except Exception as e:
            st.error(f"Erro ao renderizar gráfico: {e}")
            st.error("Tente novamente ou verifique os dados do ativo.")

    def run(self):
        """Executa o visualizador web"""
        st.set_page_config(page_title="Market Analysis System", layout="wide")

        st.title("📊 Market Analysis System")
        st.markdown("Visualizador profissional para análise técnica de ativos")

        # Sidebar para configurações
        with st.sidebar:
            st.header("⚙️ Configurações")

            # Seleção de gráficos (até 3)
            st.subheader("📈 Selecionar Gráficos")

            selected_charts = []
            for i in range(3):
                chart_options = [f"{chart['name']} ({chart['timeframe']})" for chart in self.available_charts]
                selected = st.selectbox(
                    f"Gráfico {i+1}",
                    options=chart_options,
                    key=f"chart_{i}"
                )
                if selected:
                    # Encontra o chart selecionado
                    chart_index = chart_options.index(selected)
                    selected_charts.append(self.available_charts[chart_index])

            # Botão para renderizar
            render_button = st.button("🚀 Renderizar Gráficos", type="primary")

        # Área principal
        if selected_charts and render_button:
            st.header("📊 Gráficos Selecionados")

            for i, chart_config in enumerate(selected_charts, 1):
                st.subheader(f"{i}. {chart_config['name']}")

                # Mostra informações do ativo
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Ativo", chart_config['symbol'])
                    st.metric("Timeframe", chart_config['timeframe'])
                    st.metric("Provider", chart_config['provider'])
                with col2:
                    st.metric("Indicador", chart_config['indicator'])
                    st.metric("Status", "✅ Pronto para renderizar")

                # Renderiza o gráfico
                self.render_chart(chart_config)

                st.divider()

        else:
            st.info("👈 Selecione até 3 gráficos na barra lateral e clique em 'Renderizar Gráficos'")

        # Rodapé
        st.markdown("---")
        st.markdown("**💡 Dica:** Os gráficos são renderizados usando as mesmas funções do notebook, mas de forma organizada e profissional.")
        st.markdown("**🔧 Tecnologias:** Streamlit + Plotly + Análise Técnica")

if __name__ == "__main__":
    app = MarketAnalysisWeb()
    app.run()
