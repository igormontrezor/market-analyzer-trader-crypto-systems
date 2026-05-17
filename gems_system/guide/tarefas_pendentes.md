# 🚀 Checklist Implementações - Montrezor System

## 📋 Funcionalidades Essenciais

### 📊 **BUGS(URGENTE)**
- [ ] Verificar bug no chart do evolução temporal (esta com as mesmas cryptos desde o começo).

### 🔥 **1. Confirmação e Sinal de Múltiplas Entradas na Tendência**
- [ ] Verificar se preço ultrapassou `BuyEntry` (tendência BUY) ou `SellEntry` (tendência SELL)
- [ ] Permitir múltiplas entradas na mesma tendência após confirmação
- [ ] Validação técnica do movimento
- [ ] Gestão de risco centralizada por tendência

### 🎯 **2. Campo de Entrada Dinâmico com Alertas**
- [ ] Implementar algo: Ativo, Valor Entrada, Direção (BUY/SELL), Stop Loss, Take Profits com atualizações no grafico do streamlit.
- [ ] Alertas inteligentes para proximidades de Stop e Takes
- [ ] Ajuste dinâmico do Stop durante operação
- [ ] Múltiplos Takes por timeframe (1H, 4H, 1D)

### 📊 **3. RSI Oportunidade (URGENTE)**
- [x] RSI no timeframe menor (4H ou D1 fechado)
- [x] Tocando ou próximo (3%) do fundo do Canal Linear
- [x] **ON TIME** - Não pode esperar fechamento
- [x] Alerta imediato via Telegram


Módulo de Backtesting: O sistema atual é excelente para o agora, mas não sabemos a taxa de acerto histórica desses sinais "Super" vs "Comum". Você poderia criar uma nova aba "📊 Backtest" que roda o check_signals em dados passados e plota um gráfico de curva de capital ou Win Rate da estratégia.

3. Performance de Interface e UX
Fim do "Pisca-Pisca" na Tela: Você está usando st_autorefresh(interval=120000) no app.py para atualizar o terminal. O problema é que isso recarrega a página inteira, interrompendo o usuário se ele estiver clicando em um gráfico ou lendo uma tabela.

Solução (Streamlit Fragments): Use o decorador nativo @st.fragment (lançado recentemente no Streamlit). Você isola apenas a área do terminal em uma função e coloca o st_autorefresh ou um time.sleep dentro dela. Assim, só a caixinha do terminal atualiza, sem piscar o resto do seu HUD.
---

## 🔄 **Arquitetura Produção 24/7**

### ⚡ **Daemon de Alertas Independente**
- [x] Script Python rodando 24/7 independente da interface
- [x] Verificação a cada 30 segundos
- [x] Serviço Windows/Linux (não depende do Streamlit)
- [x] Telegram como canal principal de alertas

### 🏗️ **Estrutura:**
```
Streamlit (Interface) ←→ Daemon 24/7 ←→ Telegram (Alertas)
```

---

## 🎯 **Prioridades**

### **IMEDIATO (Resolver Agora)**
1. **RSI Oportunidade** - Sistema ON TIME para fundo do canal
2. **Daemon 24/7** - Base para todos os alertas
3. **Campo de Entrada** - Gestão manual de operações

### **CURTO PRAZO**
1. **Múltiplas Entradas** - Otimização de tendências
2. **Dashboard Operações** - Visão geral ativas
3. **Histórico Performance** - Análise de resultados

---

## 💡 **Tecnologias Necessárias**

- **Daemon:** Python + schedule/threading
- **Alertas:** Telegram API
- **Interface:** Streamlit (apenas visual)
- **Serviço:** win32service (Windows) / systemd (Linux)

---

## 📊 **Deploy Produção**

```bash
# 1. Ambiente
python -m venv venv
source venv/bin/activate

# 2. Dependências
pip install schedule yfinance python-telegram-bot

# 3. Variáveis
export TELEGRAM_TOKEN="token"
export CHAT_ID="chat_id"

# 4. Iniciar serviço
python daemon_alerts.py start
```

---

## 🔔 **Tipos de Alertas**

- **🚨 STOP LOSS ATINGIDO** - Fechar operação
- **🎯 TAKE PROFIT** - Parcial ou total
- **⚠️ PROXIMIDADE** - 2% do alvo
- **📈 RSI OPORTUNIDADE** - Fundo canal linear
- **🔄 ENTRADA CONFIRMADA** - Múltiplas entradas

---

*Status: Planejamento Focado*
*Prioridade: RSI ON TIME + Daemon 24/7*
