# 🚀 GEMS SYSTEM

**Advanced cryptocurrency analysis system specialized in finding low market cap gems with high potential.**

---

## 🇺🇸 English

### 📋 Overview
GEMS SYSTEM is a sophisticated cryptocurrency analysis platform designed to identify promising low market cap tokens (gems) with significant growth potential. The system combines technical analysis, social intelligence, and multi-timeframe persistence tracking to provide comprehensive market insights.

### ✨ Key Features
- **Multi-Timeframe Analysis**: Tracks gems across 3, 7, and 14-day persistence periods
- **Social Intelligence**: Real-time YouTube API and Telegram scraping for sentiment analysis
- **Technical Scoring**: Advanced quantitative and social scoring algorithms
- **Interactive Dashboard**: Plotly-based visualization with comprehensive metrics
- **Streamlit Web Interface**: Professional web dashboard with real-time updates
- **Automated Launcher**: One-click execution with environment setup
- **Smart Filtering**: Zone-based classification (Early Accumulation, Strong, Breakout)
- **Persistence Tracking**: Cumulative counters for consistent performers
- **Leader Identification**: Automated detection of confirmed market leaders
- **Macro Timing Integration**: TradingView-based market regime analysis
- **Standardized Visualization**: Consistent UI across single and multi-snapshot analysis
- **Exhaustion Status Column**: MC + acceleration analysis for reversal signals
- **Enhanced Range System**: 10M-49M range (expanded from 10M-20M)
- **Advanced Signal Hierarchy**: Capitulation lock, tactical rebound, super alerts
- **Watchlist Status Integration**: Real-time status tracking in watchlist
- **Funding Rate Analysis**: Real-time funding rate with CSV logging

### 🛠️ Tech Stack
- **Python 3.12+** with pandas, plotly, requests
- **Data Sources**: CoinMarketCap API, YouTube API, Telegram scraping
- **Storage**: CSV snapshots + JSON daily data
- **Visualization**: Interactive Plotly dashboards
- **Caching**: 12-hour intelligent cache system

### 🚀 Quick Start
```bash
# Clone and setup
git clone https://github.com/igormontrezor/market-analyzer-crypto-gems.git
cd market-analyzer-crypto-gems/gems_system

# Option 1: Automated launcher (Recommended)
start_app.bat

# Option 2: Manual commands
python gems_finder.py
python visualizer.py

# Option 3: Streamlit web interface
python -m streamlit run app.py
```

### 📊 Output Files
- `data/snapshots/gems_*.csv` - Historical analysis data
- `data/snapshots/gems_*_enhanced_*.csv` - Complete metrics with events
- `data/daily_snapshots/daily_*.json` - Daily persistence tracking
- `data/persistence_tracker.json` - Cumulative persistence data

---

## 🇧🇷 Português

### 📋 Visão Geral
GEMS SYSTEM é uma plataforma sofisticada de análise de criptomoedas projetada para identificar tokens de baixa capitalização (gems) com significativo potencial de crescimento. O sistema combina análise técnica, inteligência social e rastreamento de persistência multi-timeframe para fornecer insights completos do mercado.

### ✨ Recursos Principais
- **Análise Multi-Timeframe**: Rastreia gems em períodos de persistência de 3, 7 e 14 dias
- **Inteligência Social**: API YouTube e scraping Telegram em tempo real para análise de sentimento
- **Scoring Técnico**: Algoritmos avançados de scoring quantitativo e social
- **Dashboard Interativo**: Visualização baseada em Plotly com métricas completas
- **Filtragem Inteligente**: Classificação baseada em zonas (Early Accumulation, Strong, Breakout)
- **Rastreamento de Persistência**: Contadores cumulativos para performers consistentes
- **Identificação de Líderes**: Detecção automatizada de líderes confirmados de mercado
- **Coluna de Status de Exaustão**: Análise de reversão baseada em MC + aceleração
- **Sistema de Faixa Aprimorado**: Range 10M-49M (expandido de 10M-20M)
- **Hierarquia de Sinais Avançada**: Capitulation lock, tactical rebound, super alerts
- **Integração de Status na Watchlist**: Acompanhamento de exaustão em tempo real
- **Análise de Funding Rate**: Análise de funding em tempo real com logging histórico

### 🛠️ Stack Tecnológico
- **Python 3.12+** com pandas, plotly, requests
- **Fontes de Dados**: CoinMarketCap API, YouTube API, scraping Telegram
- **Armazenamento**: Snapshots CSV + dados diários JSON
- **Visualização**: Dashboards interativos Plotly
- **Cache**: Sistema inteligente de cache de 12 horas

### 🚀 Início Rápido
```bash
# Clonar e configurar
git clone https://github.com/igormontrezor/market-analyzer-crypto-gems.git
cd market-analyzer-crypto-gems/gems_system

# Executar análise
python gems_finder.py

# Visualizar resultados
python visualizer.py
```

### 📊 Arquivos de Saída
- `data/snapshots/gems_*.csv` - Dados históricos de análise
- `data/snapshots/gems_*_enhanced_*.csv` - Métricas completas com eventos
- `data/daily_snapshots/daily_*.json` - Rastreamento diário de persistência
- `data/persistence_tracker.json` - Dados cumulativos de persistência

## 📁 Structure

```
gems_system/
├── gems_finder.py                    # Main analysis system
├── visualizer.py                     # Interactive dashboard
├── app.py                           # Streamlit web interface
├── start_app.bat                    # Automated launcher (Windows)
├── start_app_advanced.py            # Advanced launcher with error handling
├── persistence_tracker.py           # Persistence tracking system
├── social_analyzer_yt_telegram.py   # Social intelligence
├── evolution_functions.py           # Historical analysis functions
├── data/                            # Historical snapshots
│   ├── snapshots/                   # CSV analysis files
│   ├── daily_snapshots/             # JSON daily data
│   └── macro/                       # Macro timing data
├── guide/                           # Documentation
├── logo_mtrz.png                    # Montrezor logo
└── README.md
```

## 🚀 Quick Usage

### Option 1: Automated Launcher (Recommended)
```bash
# Double-click or run from terminal
start_app.bat
```

### Option 2: Streamlit Web Interface
```bash
cd gems_system
python -m streamlit run app.py
```

### Option 3: Manual Terminal Commands
```bash
cd gems_system
python gems_finder.py      # Run analysis
python visualizer.py       # View dashboard
```

### Option 4: Advanced Launcher
```bash
python start_app_advanced.py
```

### Jupyter Notebook
```python
# Import and run
from gems_finder import GemsFinder

finder = GemsFinder()
results = finder.analyze_gems()

# 📊 View data
print(results.head(10))

# 🔍 Filter gems
results[results["final_score"] > 0.5]

# 📈 Top gems
results.sort_values("final_score", ascending=False).head(10)
```

## 🎯 Features

- ✅ **Multi-Timeframe Analysis**: 3, 7, 14-day persistence tracking
- ✅ **Social Intelligence**: YouTube API + Telegram scraping
- ✅ **Technical Scoring**: Quantitative + social scoring algorithms
- ✅ **Interactive Dashboard**: Plotly-based visualization
- ✅ **Streamlit Web Interface**: Professional web dashboard with real-time updates
- ✅ **Automated Launcher**: One-click execution with environment setup
- ✅ **Smart Filtering**: Zone-based classification
- ✅ **Persistence Tracking**: Cumulative counters
- ✅ **Leader Detection**: Automated market leader identification
- ✅ **Historical Snapshots**: CSV + JSON data storage
- ✅ **Macro Timing Integration**: TradingView-based market regime analysis
- ✅ **Standardized Visualization**: Consistent UI across single and multi-snapshot analysis
- ✅ **Evolution Analysis**: Complete historical tracking and comparison
- ✅ **Professional Styling**: Modern gradient-based UI design
- ✅ **Exhaustion Status Analysis**: MC + acceleration-based reversal detection
- ✅ **Enhanced Range Tracking**: 10M-49M range for continuous growth monitoring
- ✅ **Advanced Signal System**: Capitulation lock, tactical rebound, super alerts
- ✅ **Watchlist Status Tracking**: Real-time exhaustion status in watchlist
- ✅ **Funding Rate Integration**: Real-time funding analysis with historical logging

## 📊 Key Metrics

- **ratio**: Volume / Market Cap ratio
- **final_score**: Composite scoring algorithm
- **persistence_days**: Consecutive appearance tracking
- **timeframe_classification**: Leader status classification
- **social_score**: Social sentiment analysis
- **quant_score**: Technical analysis score

## 💾 Data Storage

System automatically saves comprehensive data:

```python
# Enhanced CSV with all metrics
gems_10M_to_50M_enhanced_YYYYMMDD_HHMMSS.csv

# Daily persistence tracking
daily_YYYYMMDD.json

# Cumulative persistence data
persistence_tracker.json
```

Files saved in: `data/snapshots/` and `data/daily_snapshots/`

## 🔧 Configuration

### API Keys
1. **CoinMarketCap**: Get API key at https://coinmarketcap.com/api/
2. **YouTube**: Configure in `config/api_keys.py`
3. **Telegram**: Configure in `telegram_config.py`

### Environment Setup
```bash
# Windows
set CMC_API_KEY=your_key_here
set YOUTUBE_API_KEY=your_key_here
```

### System Extensions
- Add custom technical indicators
- Implement sentiment analysis
- Create automated alerts
- Build strategy backtesting

## 🚧 Development Roadmap

- [x] **Multi-Timeframe Analysis** - Complete persistence tracking
- [x] **Social Intelligence** - YouTube + Telegram integration
- [x] **Interactive Dashboard** - Plotly visualization
- [x] **Persistence System** - Cumulative counters and leader detection
- [ ] **Alert System** - Real-time notifications
- [ ] **Web Interface** - Browser-based dashboard
- [ ] **Strategy Backtesting** - Historical performance analysis
- [ ] **Mobile App** - iOS/Android applications

## 📈 Performance Metrics

- **Processing Time**: ~2-3 minutes for full analysis
- **Cache Duration**: 12 hours intelligent caching
- **Data Coverage**: 10M-50M market cap range
- **Historical Data**: Unlimited daily snapshots
- **API Efficiency**: Optimized request batching

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request
4. Follow code standards

## 📄 License

MIT License - Free for commercial and personal use

---

## 🇧🇷 Português

### 📁 Estrutura

```
gems_system/
├── gems_finder.py          # Sistema principal de análise
├── visualizer.py           # Dashboard interativo
├── persistence_tracker.py  # Sistema de rastreamento de persistência
├── social_analyzer_yt_telegram.py  # Inteligência social
├── data/                   # Snapshots históricos
│   ├── snapshots/          # Arquivos CSV de análise
│   └── daily_snapshots/    # Dados diários JSON
├── guide/                  # Documentação
├── run.bat                 # Execução Windows
└── README.md
```

### 🚀 Uso Rápido

#### Terminal
```bash
cd gems_system
python gems_finder.py      # Executar análise
python visualizer.py       # Ver dashboard
```

#### Windows
```bash
run.bat                    # Execução automatizada
```

### 🎯 Funcionalidades

- ✅ **Análise Multi-Timeframe**: Rastreamento de persistência 3, 7, 14 dias
- ✅ **Inteligência Social**: API YouTube + scraping Telegram
- ✅ **Scoring Técnico**: Algoritmos quantitativos e sociais
- ✅ **Dashboard Interativo**: Visualização Plotly
- ✅ **Filtragem Inteligente**: Classificação por zonas
- ✅ **Rastreamento de Persistência**: Contadores cumulativos
- ✅ **Detecção de Líderes**: Identificação automatizada de líderes
- ✅ **Snapshots Históricos**: Armazenamento CSV + JSON
- ✅ **Análise de Exaustão**: Detecção de reversão baseada em MC + aceleração
- ✅ **Rastreamento de Faixa Aprimorado**: Range 10M-49M para acompanhamento contínuo
- ✅ **Sistema de Sinais Avançado**: Capitulation lock, tactical rebound, super alerts
- ✅ **Acompanhamento de Status na Watchlist**: Status de exaustão em tempo real
- ✅ **Integração de Funding Rate**: Análise de funding com logging histórico

### 📊 Métricas Principais

- **ratio**: Razão Volume / Market Cap
- **final_score**: Algoritmo de scoring composto
- **persistence_days**: Rastreamento de aparições consecutivas
- **timeframe_classification**: Classificação de status de líder
- **social_score**: Análise de sentimento social
- **quant_score**: Score de análise técnica

### 💾 Armazenamento de Dados

Sistema salva automaticamente dados completos:

```python
# CSV aprimorado com todas as métricas
gems_10M_to_50M_enhanced_YYYYMMDD_HHMMSS.csv

# Rastreamento diário de persistência
daily_YYYYMMDD.json

# Dados cumulativos de persistência
persistence_tracker.json
```

Arquivos salvos em: `data/snapshots/` e `data/daily_snapshots/`

### 🔧 Configuração

#### Chaves de API
1. **CoinMarketCap**: Obtenha chave em https://coinmarketcap.com/api/
2. **YouTube**: Configure em `config/api_keys.py`
3. **Telegram**: Configure em `telegram_config.py`

#### Configuração de Ambiente
```bash
# Windows
set CMC_API_KEY=sua_chave_aqui
set YOUTUBE_API_KEY=sua_chave_aqui
```

### 🚧 Roadmap de Desenvolvimento

- [x] **Análise Multi-Timeframe** - Rastreamento completo de persistência
- [x] **Inteligência Social** - Integração YouTube + Telegram
- [x] **Dashboard Interativo** - Visualização Plotly
- [x] **Sistema de Persistência** - Contadores cumulativos e detecção de líderes
- [ ] **Sistema de Alertas** - Notificações em tempo real
- [ ] **Interface Web** - Dashboard baseado em navegador
- [ ] **Backtesting de Estratégias** - Análise de performance histórica
- [ ] **Aplicativo Mobile** - Aplicações iOS/Android

### 📈 Métricas de Performance

- **Tempo de Processamento**: ~2-3 minutos para análise completa
- **Duração do Cache**: 12 horas de cache inteligente
- **Cobertura de Dados**: Range de market cap 10M-50M
- **Dados Históricos**: Snapshots diários ilimitados
- **Eficiência de API**: Requisições otimizadas em lote

### ⚠️ Importante

Este sistema é um módulo independente com funcionalidades completas de análise de criptomoedas. Use a mesma virtual environment do projeto principal para compatibilidade.
