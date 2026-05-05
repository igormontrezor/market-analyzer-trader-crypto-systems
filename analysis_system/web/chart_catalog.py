from typing import List, Dict, Optional
import pandas as pd

class ChartCatalog:
    """Catálogo completo de gráficos baseado no notebook market_analysis_oop.ipynb"""
    
    def __init__(self):
        self.charts = [
            # RSI Charts
            {
                "id": "rsi_daily",
                "name": "RSI Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "rsi",
                "timeframe": "daily",
                "signal": "rsi",
                "description": "Índice de Força Relativa diário com sinais de compra/venda",
                "buy_threshold": 25,
                "sell_threshold": 80
            },
            {
                "id": "rsi_weekly",
                "name": "RSI Weekly",
                "symbol": "BTC-USD",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "rsi",
                "timeframe": "weekly",
                "signal": "rsi",
                "description": "Índice de Força Relativa semanal com sinais de longo prazo",
                "buy_threshold": 20,
                "sell_threshold": 80
            },
            
            # StochRSI Charts
            {
                "id": "stochrsi_daily",
                "name": "StochRSI Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "stochrsi",
                "timeframe": "daily",
                "signal": "stochrsi",
                "description": "Stochastic RSI diário com sinais de sobrecompra/sobrevenda",
                "buy_threshold": 5,
                "sell_threshold": 95
            },
            
            # Bollinger Bands Charts
            {
                "id": "bb_daily",
                "name": "Bollinger Bands Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "bb",
                "timeframe": "daily",
                "signal": "bb",
                "description": "Bandas de Bollinger diárias com sinais de rompimento",
                "buy_threshold": 0,
                "sell_threshold": 1
            },
            
            # MACD Charts
            {
                "id": "macd_daily",
                "name": "MACD Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "macd",
                "timeframe": "daily",
                "signal": "macd",
                "description": "Convergência/Divergência MACD diária com sinais de cruzamento",
                "buy_threshold": None,
                "sell_threshold": None
            },
            
            # Sharpe Ratio Charts
            {
                "id": "sharpe_weekly",
                "name": "Sharpe Ratio Weekly",
                "symbol": "BTC-USD",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "sharpe",
                "timeframe": "weekly",
                "signal": "sharpe",
                "description": "Índice de Sharpe semanal (risco ajustado) com sinais de entrada/saída",
                "buy_threshold": -1.5,
                "sell_threshold": 2.0
            },
            
            # Sortino Ratio Charts
            {
                "id": "sortino_weekly",
                "name": "Sortino Ratio Weekly",
                "symbol": "BTC-USD",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "sortino",
                "timeframe": "weekly",
                "signal": "sortino",
                "description": "Índice de Sortino semanal (risco assimétrico) com sinais de múltiplos períodos",
                "buy_threshold": -1.5,
                "sell_threshold": 4.5
            },
            
            # Combined Signal Charts
            {
                "id": "combined_daily",
                "name": "Combined Daily",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "combined",
                "timeframe": "daily",
                "signal": "combined",
                "description": "Combinação de RSI, StochRSI e Bollinger Bands com confirmação",
                "buy_threshold": 3.0,
                "sell_threshold": -3.0,
                "weights": [0.5, 0.5, 2.0]
            },
            
            # VIX Chart
            {
                "id": "vix_weekly",
                "name": "VIX Weekly",
                "symbol": "^VIX",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "ema",
                "timeframe": "weekly",
                "signal": None,
                "description": "Índice de Volatilidade com médias móveis exponenciais",
                "buy_threshold": None,
                "sell_threshold": None
            },
            
            # SPY Charts
            {
                "id": "spy_weekly_rsi",
                "name": "SPY Weekly RSI",
                "symbol": "SPY",
                "interval": "1wk",
                "provider": "yahoo",
                "indicator": "rsi",
                "timeframe": "weekly",
                "signal": "rsi",
                "description": "RSI semanal do S&P 500 para comparação com BTC",
                "buy_threshold": 28,
                "sell_threshold": 85
            },
            
            # FOREX Charts
            {
                "id": "forex_daily_rsi",
                "name": "EUR/CHF Daily RSI",
                "symbol": "EURCHF=X",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "rsi",
                "timeframe": "daily",
                "signal": "rsi",
                "description": "RSI diário do par EUR/CHF para análise de moedas",
                "buy_threshold": 25,
                "sell_threshold": 80
            },
            
            # BTC Multiple Timeframes
            {
                "id": "btc_multi_timeframe",
                "name": "BTC Multi-Timeframe",
                "symbol": "BTC-USD",
                "interval": "1d",
                "provider": "yahoo",
                "indicator": "multi",
                "timeframe": "multi",
                "signal": "multi",
                "description": "BTC em múltiplos timeframes (daily, weekly, monthly) com SMA",
                "buy_threshold": None,
                "sell_threshold": None
            }
        ]
    
    def get_all_charts(self) -> List[Dict]:
        """Retorna todos os gráficos disponíveis"""
        return self.charts
    
    def get_chart_by_id(self, chart_id: str) -> Optional[Dict]:
        """Retorna gráfico específico por ID"""
        for chart in self.charts:
            if chart["id"] == chart_id:
                return chart
        return None
    
    def get_charts_by_symbol(self, symbol: str) -> List[Dict]:
        """Retorna todos os gráficos para um símbolo específico"""
        return [chart for chart in self.charts if chart["symbol"] == symbol]
    
    def get_charts_by_indicator(self, indicator: str) -> List[Dict]:
        """Retorna todos os gráficos para um indicador específico"""
        return [chart for chart in self.charts if chart["indicator"] == indicator]
    
    def get_charts_by_timeframe(self, timeframe: str) -> List[Dict]:
        """Retorna todos os gráficos para um timeframe específico"""
        return [chart for chart in self.charts if chart["timeframe"] == timeframe]
