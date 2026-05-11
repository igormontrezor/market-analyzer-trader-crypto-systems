# ANALYSIS SYSTEM

**Advanced market analysis system for cryptocurrency trading.**

---

## 🇺🇸 English

### 📋 Overview
ANALYSIS SYSTEM is a comprehensive cryptocurrency trading analysis platform that combines technical indicators, trading strategies, and professional risk management tools for optimal market decision-making.

### ✨ Key Features
- **Advanced Technical Analysis**: RSI, MACD, Bollinger Bands, Moving Averages
- **Automated Trading Signals**: Customizable thresholds with real-time alerts
- **Interactive Charts**: Professional candlestick charts with technical overlays
- **Trading Strategies**: Multiple proven strategies including Hougaard Method
- **Risk Management**: Position sizing and stop-loss calculations
- **Backtesting Engine**: Historical strategy validation
- **Stoch RSI Analysis**: Advanced momentum indicators
- **Strategy Simulator**: Walk-through trading simulations
- **Professional Interface**: Streamlit-based web dashboard

### 🛠️ Technology Stack
- **Python 3.12+** with pandas, numpy, scipy
- **Data Sources**: Yahoo Finance, TradingView integration
- **Visualization**: Matplotlib, Plotly, Seaborn
- **Web Interface**: Streamlit for professional dashboard
- **Trading Analysis**: Advanced technical indicators

---

## 🇧🇷 Português

Sistema de análise de mercado para criptomoedas.

## 📁 Estrutura

```
analysis_system/
├── README.md                    (este arquivo)
├── run_analysis.py              (execução principal)
├── run.bat                      (execução Windows)
├── run.ps1                      (execução PowerShell)
├── market_analysis_config.md    (configurações)
├── market_analysis_diagrams.drawio (diagramas)
├── tarefas_pendentes.md         (tarefas)
├── main.py                      (módulo principal)
├── trading/                     (sistema de trading)
│   ├── trading_system.py        (interface Streamlit)
│   ├── run.ps1                  (execução PowerShell)
│   └── run.bat                  (execução Windows)
├── assets/                      (recursos)
├── data/                        (dados)
├── examples/                    (exemplos)
├── indicators/                  (indicadores técnicos)
├── notebooks/                   (notebooks de análise)
│   ├── market_analysis_month.ipynb
│   ├── market_analysis_oop.ipynb
│   └── market_analysis_week.ipynb
├── plotting/                    (gráficos)
├── signals/                     (sinais)
└── strategies/                  (estratégias)
```

## 🚀 Execução

### Análise de Mercado
#### Windows (Batch)
```bash
run.bat
```

#### Windows (PowerShell)
```powershell
.\run.ps1
```

#### Direto
```bash
python run_analysis.py
```

### Sistema de Trading
#### Windows (Batch)
```bash
cd trading
run.bat
```

#### Windows (PowerShell)
```powershell
cd trading
.\run.ps1
```

#### Streamlit Interface
```bash
cd trading
python -m streamlit run trading_system.py
```

#### Acesso via Browser
- Abre automaticamente em: http://localhost:8502
- Interface profissional com múltiplas abas de análise

## 🔧 Configuração

- Usa o config compartilhado: `../config/`
- Usa o venv compartilhado: `../.venv/`

## 📊 Features

- **Advanced Technical Analysis**: RSI, MACD, Bollinger Bands indicators
- **Automated Trading Signals**: Real-time buy/sell signal generation
- **Multiple Trading Strategies**: Proven strategies with backtesting
- **Interactive Visualizations**: Professional charts and dashboards
- **Hougaard Trading Method**: Complete trading system implementation
- **Stoch RSI Analysis**: Advanced momentum and reversal detection
- **Strategy Simulator**: Step-by-step trading walkthrough
- **Performance Backtesting**: Historical strategy validation
- **Risk Management**: Position sizing and stop-loss calculations

## 📊 Funcionalidades

- Análise técnica avançada
- Indicadores técnicos (RSI, MACD, Bollinger Bands)
- Sinais de trading automatizados
- Estratégias múltiplas
- Gráficos e visualizações interativas
- Sistema de Trading com método Hougaard
- Análise de Stoch RSI
- Simulador de estratégias
- Backtesting de performance
- Gestão de risco e posição

## 📝 Notas

Este sistema compartilha:
- Configurações com `gems_system`
- Ambiente virtual (`.venv`)
- Bibliotecas do projeto principal
