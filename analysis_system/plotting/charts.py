import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import seaborn as sns
import pandas as pd
from typing import Optional, List, Dict, Any


class ChartPlotter:
    """Classe para criar visualizações de dados financeiros"""

    @staticmethod
    def plot_candlestick_with_signals(
        df: pd.DataFrame,
        title: str,
        buy_signals: Optional[pd.Series] = None,
        sell_signals: Optional[pd.Series] = None,
        show_volume: bool = False,
        show: bool = True,
    ):
        """Cria gráfico de candlestick com sinais de compra/venda"""

        fig = make_subplots(
            rows=2 if show_volume else 1,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(title, 'Volume') if show_volume else (title,),
            row_width=[0.2, 0.7] if show_volume else [0.2]
        )

        # Lidar com MultiIndex columns do Yahoo Finance
        if isinstance(df.columns, pd.MultiIndex):
            # Extrair o primeiro símbolo disponível
            symbol = df.columns.get_level_values(1)[0]
            open_col = ('Open', symbol)
            high_col = ('High', symbol)
            low_col = ('Low', symbol)
            close_col = ('Close', symbol)
            volume_col = ('Volume', symbol)
        else:
            open_col = 'Open'
            high_col = 'High'
            low_col = 'Low'
            close_col = 'Close'
            volume_col = 'Volume'

        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df[open_col],
                high=df[high_col],
                low=df[low_col],
                close=df[close_col],
                name='Price'
            ),
            row=1, col=1
        )

        # Sinais de compra
        if buy_signals is not None:
            buy_dates = buy_signals[buy_signals].index if len(buy_signals[buy_signals]) > 0 else []
            if len(buy_dates) > 0:
                buy_prices = df.loc[buy_dates, close_col]
                # Se for Series, extrair os valores
                if isinstance(buy_prices, pd.Series):
                    buy_prices = buy_prices.values
                fig.add_trace(
                    go.Scatter(
                        x=buy_dates,
                        y=buy_prices,
                        mode='markers',
                        marker=dict(symbol='triangle-up', size=10, color='green'),
                        name='Buy Signal'
                    ),
                    row=1, col=1
                )

        # Sinais de venda
        if sell_signals is not None:
            sell_dates = sell_signals[sell_signals].index if len(sell_signals[sell_signals]) > 0 else []
            if len(sell_dates) > 0:
                sell_prices = df.loc[sell_dates, close_col]
                # Se for Series, extrair os valores
                if isinstance(sell_prices, pd.Series):
                    sell_prices = sell_prices.values
                fig.add_trace(
                    go.Scatter(
                        x=sell_dates,
                        y=sell_prices,
                        mode='markers',
                        marker=dict(symbol='triangle-down', size=10, color='red'),
                        name='Sell Signal'
                    ),
                    row=1, col=1
                )

        # Volume
        if show_volume and volume_col in df.columns:
            fig.add_trace(
                go.Bar(x=df.index, y=df[volume_col], name='Volume'),
                row=2, col=1
            )

        fig.update_layout(
            title=title,
            yaxis_title='Price',
            xaxis_rangeslider_visible=False,
            height=600 if show_volume else 400
        )

        if show:
            fig.show()

        return fig

    @staticmethod
    def plot_indicator_with_signals(
        price_data: pd.Series,
        indicator_data: pd.Series,
        title: str,
        buy_signals: Optional[pd.Series] = None,
        sell_signals: Optional[pd.Series] = None,
        indicator_name: str = "Indicator"
        ,
        show: bool = True,
    ):
        """Plota indicador com sinais"""

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(title, indicator_name),
            row_heights=[0.7, 0.3]
        )

        # Preço
        fig.add_trace(
            go.Scatter(x=price_data.index, y=price_data, name='Price'),
            row=1, col=1
        )

        # Indicador
        fig.add_trace(
            go.Scatter(x=indicator_data.index, y=indicator_data, name=indicator_name),
            row=2, col=1
        )

        # Sinais no indicador
        if buy_signals is not None:
            buy_dates = indicator_data[buy_signals].index
            buy_values = indicator_data.loc[buy_dates]
            fig.add_trace(
                go.Scatter(
                    x=buy_dates,
                    y=buy_values,
                    mode='markers',
                    marker=dict(symbol='triangle-up', size=8, color='green'),
                    name='Buy'
                ),
                row=2, col=1
            )

        if sell_signals is not None:
            sell_dates = indicator_data[sell_signals].index
            sell_values = indicator_data.loc[sell_dates]
            fig.add_trace(
                go.Scatter(
                    x=sell_dates,
                    y=sell_values,
                    mode='markers',
                    marker=dict(symbol='triangle-down', size=8, color='red'),
                    name='Sell'
                ),
                row=2, col=1
            )

        fig.update_layout(
            title=title,
            height=600
        )

        if show:
            fig.show()

        return fig

    @staticmethod
    def plot_multiple_indicators(
        data: Dict[str, pd.Series],
        title: str,
        subplot_titles: Optional[List[str]] = None
        ,
        show: bool = True,
    ):
        """Plota múltiplos indicadores em subplots"""

        n_indicators = len(data)
        if subplot_titles is None:
            subplot_titles = list(data.keys())

        fig = make_subplots(
            rows=n_indicators, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=subplot_titles
        )

        for i, (name, series) in enumerate(data.items(), 1):
            fig.add_trace(
                go.Scatter(x=series.index, y=series, name=name),
                row=i, col=1
            )

        fig.update_layout(
            title=title,
            height=200 * n_indicators
        )

        if show:
            fig.show()

        return fig
