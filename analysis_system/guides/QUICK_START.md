# 🚀 QUICK START - Notificações Telegram + CSV Export

## O que foi adicionado?

### ✅ 3 Melhorias Principais

#### 1. **Persistência** 💾
- Ativos salvos em `~/.montrezor_data.json`
- Níveis Neuro Athena conservados
- Carrega automaticamente ao abrir

#### 2. **Alertas via Telegram** 📱
- Receba sinais no celular
- Funciona 24/7
- Configurável em segundos
- Som + Piscada no PC
- Sincronizado com ambos sistemas (Trading + Gems)

#### 3. **Exportação CSV** 📊
- Histórico de sinais em arquivo
- Abrir em Excel/Pandas
- Analisar assertividade do método
- Log temporal de cada sinal

---

## ⚡ 5 Minutos de Setup

### Passo 1: Criar Bot no Telegram (2 min)
1. Abra Telegram → procure **@BotFather**
2. `/newbot` → escolha nome e username
3. **Copie o TOKEN** que aparece

### Passo 2: Obter Chat ID (1 min)
1. Procure **@userinfobot**
2. Envie qualquer mensagem
3. **Copie seu ID** (número)

### Passo 3: Configurar no Montrezor (2 min)
1. Abra Trading System
2. Aba: **⚙️ Configurações**
3. Cole TOKEN + Chat ID
4. Clique: **📤 Enviar Teste**
5. ✅ Pronto!

**Guia detalhado**: Ver arquivo `TELEGRAM_SETUP.md`

---

## 📁 Arquivos Novos/Modificados

### Criados:
```
montrezor_alerts_integration.py  ← Funções centralizadas de alertas
analysis_system/trading/TELEGRAM_SETUP.md  ← Tutorial completo
ALERTS_INTEGRATION_GUIDE.md  ← Integração Trading + Gems
```

### Modificados:
```
analysis_system/trading/trading_system.py
 ✓ Imports: +requests, StringIO
 ✓ Funções: +Telegram, +CSV Export
 ✓ Session States: +Telegram config
 ✓ Tab 0: +Botões export, +Alerta Telegram
 ✓ Tab 5 (nova): ⚙️ Configurações + Tutorial
```

---

## 🎯 Como Usar

### Receber Alertas

```
1. Trading System detecta sinal
   ↓
2. Toca som + Pisca título do PC
   ↓
3. Envia mensagem via Telegram (se ativado)
   ↓
4. Registra em histórico (CSV)
```

### Exportar Histórico

```
Tab "⚙️ Configurações" → Botão "📥 Exportar Histórico"
↓
arquivo.csv baixa automaticamente
↓
Abrir em Excel ou Pandas para análise
```

---

## 🔍 Exemplo: Analisar Sinais em Python

```python
import pandas as pd

# Carregar arquivo CSV exportado
df = pd.read_csv("montrezor_sinais_20260512_143258.csv")

# Ver quantos sinais cada tipo
print(df['type'].value_counts())
# COMUM    18
# SUPER    14

# Ver por direção
print(df['direction'].value_counts())
# COMPRA    20
# VENDA     12

# Ver ativos mais sinalizados
print(df['symbol'].value_counts())
# EURUSD#     8
# CHFJPY#     6
# BTCUSD#     4
```

---

## 📱 Integrar Gems System (app.py)

Arquivo: `ALERTS_INTEGRATION_GUIDE.md` → Seção "Integrar com Gems System"

Em resumo:
```python
# Adicione no app.py:
from montrezor_alerts_integration import send_gems_alert, log_signal

# Quando detectar SUPER_BUY:
send_gems_alert("BTC", "SUPER_BUY", market_cap=50000000)
log_signal("GEMS", "BTC", {"type": "SUPER_BUY"})
```

---

## ✨ Recursos Principais

| Recurso | Status | Descrição |
|---------|--------|-----------|
| Alerta Som | ✅ | Toca ao detectar sinal |
| Piscada Título | ✅ | Pisca nome do ativo |
| Telegram | ✅ | Envia no celular |
| CSV Export | ✅ | Baixar histórico |
| Persistência | ✅ | Salva configurações |
| Multi-Sistema | ✅ | Trading + Gems |
| Tutorial | ✅ | Guia passo a passo |

---

## 🧪 Testes

```python
# Teste 1: Verificar config
streamlit run trading_system.py
→ Aba ⚙️ Configurações → Botão "📤 Enviar Teste"

# Teste 2: Exportar CSV
→ Aba ⚙️ Configurações → Botão "📥 Exportar Histórico"
→ Arquivo baixa em seu PC

# Teste 3: Integração Gems
→ Veja ALERTS_INTEGRATION_GUIDE.md
```

---

## 🎓 O Que Aprender Depois

1. **Análise de Sinais**: `pandas.read_csv()` + estatísticas
2. **Backtesting**: Usar histórico para testar regras
3. **Webhook**: Integrar com APIs de brokers
4. **Banco de Dados**: Salvar histórico em SQL
5. **Dashboard**: Unify todos os dados em 1 página

---

## 📞 FAQ

**P: Telegrama é seguro?**
R: Sim! O token é local, mensagens criptografadas end-to-end.

**P: Preciso do trading ativo todo tempo?**
R: Não! Configure auto-refresh a cada 1 min (⏱ Auto)

**P: Funciona sem internet?**
R: Não para Telegram, mas o histórico local funciona.

**P: Posso mudar o token depois?**
R: Sim! Aba ⚙️ → Digite novo → Salvar

---

## 🚀 Próximos Passos

1. ✅ Seguir este guia (5 min)
2. ▶️ Configurar Telegram (1 min)
3. ▶️ Testar com botão "Enviar Teste" (1 min)
4. ▶️ Deixar rodando durante trading
5. ▶️ Exportar e analisar depois

---

**Tudo pronto? Comece agora! 🎯**

Abra a aba **⚙️ Configurações** e configure seu Telegram em 2 minutos.
