# 📊 Sistema de Sinais Macro + Funding Rate

## 🎯 Visão Geral

O sistema combina duas fontes de dados para gerar sinais de trading:
1. **USDT.D BB%B (Bollinger Bands Percent)** - Define o regime macro do mercado
2. **BTC Funding Rate** - Confirma ou refuta o regime com sentimento de capital

---

## 🔧 Função Principal: `_build_macro_timing()`

### 📡 Fonte de Dados

```python
# TradingView DataFeed
tv = TvDatafeed()
usdt_weekly = tv.get_hist(symbol='USDT.D', exchange='CRYPTOCAP', interval=Interval.in_weekly, n_bars=200)
usdt_monthly = tv.get_hist(symbol='USDT.D', exchange='CRYPTOCAP', interval=Interval.in_monthly, n_bars=100)
others_weekly = tv.get_hist(symbol='OTHERS', exchange='CRYPTOCAP', interval=Interval.in_weekly, n_bars=200)
```

### 📐 Cálculo do BB%B (Bollinger Bands Percent)

```python
def _bb_percent(series, period=20, std_mult=2.0):
    ma = series.rolling(period).mean()           # Média móvel
    sd = series.rolling(period).std(ddof=0)   # Desvio padrão
    # Fórmula: (Preço - Banda Inferior) / (Banda Superior - Banda Inferior)
    return (series - (ma - std_mult * sd)) / ((ma + std_mult * sd) - (ma - std_mult * sd))
```

**Interpretação do BB%B:**
- **0.0** = Preço na banda inferior (oversold/cheap)
- **0.5** = Preço no meio das bandas (neutral)
- **1.0** = Preço na banda superior (overbought/expensive)

---

## 🎭 Lógica do Regime Macro (USDT.D Mensal)

### 📊 Estados do Regime - Explicação Detalhada

```python
# Valores atuais
curr_m_usdt = m_usdt_bbp.iloc[-1]    # BB%B mensal atual (ex: 0.35)
prev_m_usdt = m_usdt_bbp.iloc[-2]    # BB%B mensal anterior (ex: 1.20)
```

#### 🟩 MODO COMPRA (Bear Market) - Como Funciona na Prática

**Condição 1: Cruzamento para Baixo**
```python
(prev_m_usdt >= 1.0 and curr_m_usdt < 1.0)
```
- **O que significa**: USDT.D estava ACIMA da banda superior (1.0) e CRUZOU para baixo
- **Exemplo real**: Mês passado BB%B era 1.20 (acima da banda) → Este mês é 0.35 (dentro das bandas)
- **Interpretação**: O dólar tether estava caro, agora está normalizando. **Bear market iniciando**.
- **Lógica**: Quando USDT.D sai do topo, o dinheiro foge das altcoins para stablecoins.

**Condição 2: Já está na Zona de Compra**
```python
(curr_m_usdt < 1.0 and curr_m_usdt > 0.2)
```
- **O que significa**: USDT.D já está dentro das bandas, mas não tão barato ainda
- **Exemplo real**: BB%B atual é 0.45 (meio das bandas)
- **Interpretação**: Bear market em andamento, mas ainda não é o momento ideal de compra.

#### 🟥 MODO VENDA (Bull Market) - Como Funciona na Prática

**Condição 1: Cruzamento para Cima**
```python
(prev_m_usdt <= 0.0 and curr_m_usdt > 0.0)
```
- **O que significa**: USDT.D estava ABAIXO da banda inferior (0.0) e CRUZOU para cima
- **Exemplo real**: Mês passado BB%B era -0.15 (abaixo da banda) → Este mês é 0.25 (dentro das bandas)
- **Interpretação**: O dólar tether estava barato, agora está subindo. **Bull market iniciando**.
- **Lógica**: Quando USDT.D sai do fundo, o dinheiro entra nas altcoins.

**Condição 2: Já está na Zona de Venda**
```python
(curr_m_usdt > 0.0 and curr_m_usdt < 0.8 and not buy_mode)
```
- **O que significa**: USDT.D já está dentro das bandas, mas não é modo de compra
- **Exemplo real**: BB%B atual é 0.60 (acima do meio)
- **Interpretação**: Bull market em andamento, momento de alerta para saídas.

#### 🔒 CADEADO DE CAPITULAÇÃO - Proteção Máxima

```python
capitulation_lock = bool(sell_mode and curr_m_usdt >= 0.8)
```

- **O que significa**: Estamos em modo VENDA E USDT.D está muito alto (próximo do topo)
- **Exemplo real**: BB%B atual é 0.85 (quase na banda superior)
- **Interpretação**: **PERIGO MÁXIMO!** O mercado está em euforia total.
- **Proteção**: BLOQUEIA TODAS as compras, mesmo que outros sinais apareçam.

---

### 🎯 Tabela Prática de Decisão

| Estado | Exemplo Real | O que está acontecendo no mercado | O que fazer |
|--------|-------------|--------------------------------|-------------|
| **🟩 COMPRA** | BB%B: 1.20 → 0.35 | USDT.D estava caro, agora está normalizando | ⚠️ **AGUARDAR** - Bear market começando |
| **🟩 COMPRA** | BB%B: 0.45 (estável) | Bear market em andamento | ⚠️ **AGUARDAR** - Ainda não é o fundo |
| **🟥 VENDA** | BB%B: -0.15 → 0.25 | USDT.D estava barato, agora subindo | ⚠️ **ALERTA** - Bull market começando |
| **🟥 VENDA** | BB%B: 0.60 (estável) | Bull market em andamento | ⚠️ **PREPARAR** - Momento de atenção |
| **🔒 CAPITULAÇÃO** | BB%B: 0.85 | Euforia total, USDT.D quase no topo | 🚫 **BLOQUEADO** - Nenhuma compra |

---

### 📈 Como Ler o BB%B na Prática

**Escala de 0 a 1:**
- **0.0** = Banda inferior (mais barato possível)
- **0.5** = Meio das bandas (preço justo)
- **1.0** = Banda superior (mais caro possível)

**Zonas de Operação:**
- **🟢 Zona de Oportunidade (0.0 - 0.3)**: USDT.D muito barato
- **🟡 Zona de Atenção (0.3 - 0.7)**: USDT.D normalizando
- **🔴 Zona de Perigo (0.7 - 1.0)**: USDT.D muito caro

**Exemplo do Ciclo Completo:**
1. **Início**: BB%B 1.20 → 0.85 (🔒 CAPITULAÇÃO ativa)
2. **Meio**: BB%B 0.85 → 0.60 (🟥 ALERTA DE VENDA)
3. **Fundo**: BB%B 0.60 → 0.25 (� MODO COMPRA ativado)
4. **Oportunidade**: BB%B 0.25 → 0.15 (🟩 ESPERAR GATILHO)
5. **Recuperação**: BB%B 0.15 → 0.45 (🟩 AGUARDAR MELHOR)
6. **Euforia**: BB%B 0.45 → 1.10 (🔒 CAPITULAÇÃO novamente)

---

## 📡 Lógica de Gatilhos Semanais - O Timing Perfeito

### 🎯 Por que Usar Gatilhos Semanais?

O regime mensal diz **O QUÊ** fazer (comprar/vender), mas os gatilhos semanais dizem **QUANDO** fazer.
É a diferença entre saber que vai chover e saber exatamente quando abrir o guarda-chuva!

```python
# Valores semanais (mais rápidos que o mensal)
curr_w_usdt = w_usdt_bbp.iloc[-1]      # BB%B semanal atual (ex: 0.85)
curr_w_others = w_others_bbp.iloc[-1]  # OTHERS BB%B semanal (ex: 0.15)
```

---

### 🟢 GATILHO DE COMPRA SEMANAL - O Momento Exato

```python
weekly_buy_trigger = bool(
    buy_mode and (
        weekly_state["others_touch_low"] or    # CONDIÇÃO 1
        weekly_state["usdt_touch_high"]       # CONDIÇÃO 2
    )
)
```

#### **CONDIÇÃO 1: OTHERS tocou a banda inferior**
- **O que significa**: As altcoins chegaram ao fundo do poço
- **Exemplo prático**: OTHERS BB%B era 0.30 → caiu para -0.05 (abaixo da banda)
- **Interpretação**: **FOGA DE CAPITAL!** Todo mundo vendeu altcoins desesperadamente.
- **Oportunidade**: Quando todo mundo vende, é a melhor hora de comprar barato.

#### **CONDIÇÃO 2: USDT.D tocou a banda superior**
- **O que significa**: O dólar tether chegou no topo
- **Exemplo prático**: USDT.D BB%B era 0.70 → subiu para 1.05 (acima da banda)
- **Interpretação**: **REFÚGIO MÁXIMO!** Todo mundo correu para USDT.D.
- **Oportunidade**: Quando o dinheiro se concentra em USDT.D, as altcoins ficam baratas.

**🎯 Lógica do Gatilho**:
Em regime de COMPRA (bear market), esperamos um desses dois eventos:
1. **Pânico geral** (altcoins no fundo) OU
2. **Refúgio máximo** (dinheiro em USDT.D)

Qualquer um dos dois indica **EXTREMO DO MERCADO** = ponto de entrada!

---

### 🔵 REPIQUE TÁTICO - A Segunda Chance

```python
tactical_rebound = bool(
    sell_mode and                    # Estamos em modo VENDA (bull market)
    weekly_state["usdt_touch_high"] and  # USDT.D tocou o topo
    not capitulation_lock              # E não estamos em capitulação
)
```

#### **Como Funciona na Prática:**
- **Cenário**: Estamos em bull market (modo VENDA)
- **Evento**: USDT.D tocou a banda superior (ex: BB%B 1.10)
- **O que acontece**: O dinheiro estava em USDT.D (refúgio) e começa a voltar para altcoins
- **Oportunidade**: **REPIQUE!** As altcoins sobem rapidamente nesse momento
- **Proteção**: Só funciona se não for capitulação (evita comprar no topo verdadeiro)

**🎯 Exemplo Real**:
- Bull market em andamento
- USDT.D toca 1.15 (muito caro)
- Dinheiro sai do USDT.D e entra nas altcoins
- Resultado: Altcoins sobem 20-50% em poucos dias

---

### 🔴 GATILHO DE VENDA SEMANAL - Proteger Lucros

```python
weekly_sell_trigger = bool(
    sell_mode and (
        weekly_state["usdt_touch_low"] or    # CONDIÇÃO 1
        curr_w_others >= 1                  # CONDIÇÃO 2
    )
)
```

#### **CONDIÇÃO 1: USDT.D tocou a banda inferior**
- **O que significa**: O refúgio barateou
- **Exemplo prático**: USDT.D BB%B era 0.60 → caiu para -0.10 (abaixo da banda)
- **Interpretação**: O dinheiro está saindo do refúgio e entrando nas altcoins
- **Ação**: **HORA DE VENDER!** As altcoins estão eufóricas.

#### **CONDIÇÃO 2: OTHERS acima da banda superior**
- **O que significa**: As altcoins estão eufóricas
- **Exemplo prático**: OTHERS BB%B era 0.80 → subiu para 1.20 (acima da banda)
- **Interpretação**: **EUFORIA MÁXIMA!** Todo mundo quer altcoins
- **Ação**: **VENDER AGORA!** Quando todo mundo quer comprar, é hora de vender.

---

### 📊 Tabela Prática dos Toques de Banda

| Toque | Exemplo Real | O que o mercado está fazendo | O que fazer |
|--------|-------------|----------------------------|-------------|
| **USDT.D High** | BB%B: 0.75 → 1.05 | Dinheiro correndo para refúgio | 🟢 **COMPRAR** se em modo COMPRA |
| **USDT.D Low** | BB%B: 0.40 → -0.08 | Dinheiro saindo do refúgio | 🔴 **VENDER** se em modo VENDA |
| **OTHERS Low** | BB%B: 0.25 → -0.12 | Pânico geral nas altcoins | 🟢 **COMPRAR** se em modo COMPRA |
| **OTHERS High** | BB%B: 0.85 → 1.15 | Euforia total nas altcoins | 🔴 **VENDER** se em modo VENDA |

---

### 🎯 Fluxo Completo de Decisão Semanal

```
1. 📊 Verificar regime mensal (COMPRA/VENDA)
   ↓
2. 👀 Monitorar toques de bandas semanais
   ↓
3. 🎯 Se regime = COMPRA:
   - Esperar OTHERS tocar banda inferior (PÂNICO) OU
   - Esperar USDT.D tocar banda superior (REFÚGIO)
   ↓
4. 🎯 Se regime = VENDA:
   - Esperar USDT.D tocar banda inferior (SAÍDA DE REFÚGIO) OU
   - Esperar OTHERS tocar banda superior (EUFORIA)
   ↓
5. ⚡ EXECUTAR AÇÃO no momento exato do toque
```

### 🚨 Regras de Ouro dos Gatilhos

1. **NUNCA compre sem gatilho** - O regime diz a direção, o gatilho diz o timing
2. **SEMPRE confirme o toque** - Espere o candle fechar na banda
3. **JAMAIS ignore o regime** - Gatilho só funciona no regime certo
4. **CUIDADO com falsos** - Em mercados voláteis, espere confirmação
5. **RESPEITE o cadeado** - Capitulação bloqueia TODOS os gatilhos de compra

---

## 💰 Lógica do Funding Rate

### 📡 Obtenção do Dados

```python
# API Binance Futures
url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
response = requests.get(url, timeout=5)
funding_rate = float(response.json().get('lastFundingRate', 0)) * 100
```

### 💸 Interpretação do Funding Rate

| Valor | Interpretação | Sentimento |
|--------|---------------|-------------|
| **< 0%** | Negativo | Vendedores pagam compradores | **ALTA PRESSÃO DE COMPRA** |
| **0% a 0.08%** | Neutro | Equilíbrio | **NEUTRO** |
| **> 0.08%** | Positivo | Compradores pagam vendedores | **ALTA PRESSÃO DE VENDA** |

---

## 🎯 LÓGICA DE CONFLUÊNCIA (Regime + Funding)

### 🧠 Fórmula Final

```python
# Se o regime é COMPRA:
if buy_mode:
    if funding_rate < 0:
        funding_signal = "BUY"           # Confirmação forte
        if weekly_buy_trigger:
            super_alert = "SUPER_BUY"    # Sinal máximo
    else:
        funding_signal = "NEUTRAL"       # Sem confirmação
        super_alert = "OFF"

# Se o regime é VENDA:
elif sell_mode:
    if funding_rate > 0.08:
        funding_signal = "SELL"          # Confirmação forte
        if weekly_sell_trigger:
            super_alert = "SUPER_SELL"   # Sinal máximo
    else:
        funding_signal = "NEUTRAL"       # Sem confirmação
        super_alert = "OFF"
```

### 🎭 Matriz de Decisão

| Regime | Funding Rate | Sinal Final | Ação Sugerida |
|---------|---------------|-------------|-----------------|
| **🟩 COMPRA** | **< 0%** | **BUY** | ✅ FORTE COMPRA CONFIRMADA |
| **🟩 COMPRA** | **0% a 0.08%** | **NEUTRAL** | ⚠️ AGUARDAR MELHOR CONFLUÊNCIA |
| **🟥 VENDA** | **> 0.08%** | **SELL** | ⚠️ FORTE VENDA CONFIRMADA |
| **🟥 VENDA** | **0% a 0.08%** | **NEUTRAL** | ⚠️ AGUARDAR MELHOR CONFLUÊNCIA |
| **🔒 CAPITULAÇÃO** | **QUALQUER** | **NEUTRAL** | 🚫 COMPRAS BLOQUEADAS |

---

## 🚨 Sistema de Super Alerta

### 🎯 Condições para Super Alerta

```python
# SUPER BUY (Máxima Confiança)
super_buy = (
    buy_mode and                    # Regime de compra
    funding_rate < 0 and            # Funding negativo
    weekly_buy_trigger              # Gatilho semanal confirmado
)

# SUPER SELL (Máxima Confiança)
super_sell = (
    sell_mode and                   # Regime de venda
    funding_rate > 0.08 and         # Funding positivo alto
    weekly_sell_trigger             # Gatilho semanal confirmado
)
```

### 📊 Níveis de Alerta

| Nível | Condição | Confiança | Ação Imediata |
|--------|-----------|------------|----------------|
| **🟢 SUPER BUY** | Regime COMPRA + Funding < 0% + Gatilho BUY | **95%** | 🚀 ENTRAR AGORA |
| **🟢 BUY** | Regime COMPRA + Funding < 0% | **80%** | ✅ Considerar entrada |
| **🟡 NEUTRAL** | Conflitância ou sem confirmação | **50%** | ⏳ AGUARDAR |
| **🔴 SELL** | Regime VENDA + Funding > 0.08% | **80%** | ⚠️ Considerar saída |
| **🔴 SUPER SELL** | Regime VENDA + Funding > 0.08% + Gatilho SELL | **95%** | 🚪 SAIR AGORA |

---

## 📝 Fluxo Completo de Decisão

```
1. 📊 Calcular BB%B Mensal (USDT.D)
   ↓
2. 🎭 Determinar Regime (COMPRA/VENDA/CAPITULAÇÃO)
   ↓
3. 📡 Obter Funding Rate (BTC/USDT)
   ↓
4. 🎯 Verificar Gatilhos Semanais
   ↓
5. 🧠 Aplicar Lógica de Confluência
   ↓
6. 🚨 Gerar Super Alerta (se aplicável)
   ↓
7. 📈 Exibir Sinal Final
```

---

## 🔧 Parâmetros Configuráveis

```python
# Parâmetros do Sistema
BB_PERIOD = 20        # Período das Bandas de Bollinger
BB_STD = 2.0          # Multiplicador do desvio padrão
CACHE_EXPIRE = 3600    # Cache de 1 hora
FUNDING_NEGATIVE = 0.0    # Limite para funding negativo
FUNDING_POSITIVE = 0.08   # Limite para funding positivo
```

---

## 🎯 Resumo da Estratégia

### 🟩 Em Regime de Compra (Bear Market)
- **Buscar**: Funding negativo + gatilhos semanais
- **Ideal**: USDT.D barato com altcoins oversold
- **Sinal**: SUPER BUY quando tudo alinhar

### 🟥 Em Regime de Venda (Bull Market)
- **Buscar**: Funding positivo + gatilhos semanais
- **Ideal**: USDT.D caro com altcoins overbought
- **Sinal**: SUPER SELL quando tudo alinhar

### 🔒 Em Capitulação
- **Regra**: Nenhuma compra, independentemente do funding
- **Motivo**: Risco máximo de reversão violenta
- **Ação**: Apenas aguardar ou vender

---

## 📊 Histórico e Logs

O sistema mantém dois arquivos de histórico:
1. **macro_timing.json** - Cache dos dados macro (1 hora)
2. **funding_rate_history.csv** - Histórico do funding rate (1 hora)

Ambos permitem análise retrospectiva e backtesting da estratégia.

---

## ⚠️ Considerações Importantes

1. **Lag de Dados**: USDT.D mensal tem mais peso que semanal
2. **Falsos Positivos**: Sempre confirmar com múltiplos timeframes
3. **Volatilidade**: Em mercados extremos, os sinais podem falhar
4. **Cache**: Dados são cacheados por 1 hora para performance

---

## 🎯 Melhorias Futuras

- [ ] Adicionar mais exchanges para funding rate
- [ ] Implementar machine learning para previsão
- [ ] Adicionar alertas por push notification
- [ ] Backtesting automático da estratégia
- [ ] Otimização de parâmetros por mercado

---

*Última atualização: 06/05/2026*
*Versão: 2.0*
