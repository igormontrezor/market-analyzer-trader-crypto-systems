# Market Analysis Web Visualizer

Visualizador web leve para análise técnica de mercados, baseado nas funções do notebook `market_analysis_oop.ipynb`.

## 🚀 Como Executar

```bash
cd analysis_system
pip install -r requirements.txt
streamlit run web/visualizer.py
```

## 📊 Funcionalidades

### Catálogo de Gráficos
- **RSI Daily/Weekly** - Índice de Força Relativa com sinais de compra/venda
- **StochRSI Daily** - Stochastic RSI com sobrecompra/sobrevenda
- **Bollinger Bands Daily** - Bandas de Bollinger com sinais de rompimento
- **MACD Daily** - Convergência/Divergência com sinais de cruzamento
- **Sharpe Ratio Weekly** - Risco ajustado com sinais de entrada/saída
- **Sortino Ratio Weekly** - Risco assimétrico com sinais de múltiplos períodos
- **Combined Daily** - Combinação de múltiplos indicadores com confirmação

### Características
- ✅ **Até 3 gráficos simultâneos** por renderização
- ✅ **Seleção por nome + timeframe** (ex: "RSI Daily", "RSI Weekly")
- ✅ **Sinais plotados automaticamente** (buy/sell markers)
- ✅ **Integração total** com `analysis_system` (reaproveita todas as classes)
- ✅ **Interface profissional** com Streamlit + Plotly
- ✅ **Multi-provider** (Yahoo Finance, Binance, CoinGecko)

## 🏗️ Arquitetura

```
analysis_system/
├── web/
│   ├── visualizer.py          # Interface Streamlit
│   └── README.md             # Este arquivo
├── assets/                    # Classes de ativos e providers
├── indicators/                 # Indicadores técnicos
├── signals/                    # Sinais de trading
├── strategies/                 # Estratégias (BtcStrategy)
├── utils/                      # DataAggregator (extraído do notebook)
├── trading/                    # Arbitration (extraído do notebook)
└── plotting/                   # ChartPlotter (já existente)
```

## 📝 Uso

1. Execute o visualizador web
2. Selecione até 3 gráficos na barra lateral
3. Escolha entre opções como "RSI Daily", "MACD Weekly", etc.
4. Clique em "Renderizar Gráficos"
5. Visualize os gráficos profissionais com sinais já plotados

## 🎯 Vantagens vs Notebook

- ✅ **Sem peso** - Interface web leve vs Jupyter notebook
- ✅ **Produtivo** - Seleção rápida e renderização em lote
- ✅ **Profissional** - Layout organizado com métricas e informações
- ✅ **Extensível** - Fácil adicionar novos gráficos/indicadores
- ✅ **Compatível** - 100% compatível com as classes do `analysis_system`

## 🔧 Dependências

- `streamlit` - Interface web
- `plotly` - Gráficos interativos
- `analysis_system` - Classes de análise (já separadas)

**Pronto para uso profissional!** 🚀
