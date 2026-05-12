# 📊 Integração de Alertas - Trading System + Gems System

## Visão Geral

O Montrezor agora tem sistema centralizado de alertas que coordena:
- **Trading System**: Sinais de confluência (COMPRA/VENDA)
- **Gems System**: Alerts de Funding Rate e análise macroeconômica
- **Telegram**: Notificações em tempo real no celular
- **CSV Export**: Histórico unificado para análise

---

## 📁 Arquivos da Integração

### 1. **trading_system.py** (modificado)
```
✅ Alerta com Som + Piscada de Título
✅ Persistência em JSON (.montrezor_data.json)
✅ Histórico de Sinais
✅ Exportação CSV
✅ Integração Telegram
✅ Aba de Configurações
```

### 2. **montrezor_alerts_integration.py** (novo)
```
🔹 Função: send_trading_alert()
   └─ Envia sinais do trading system via Telegram

🔹 Função: send_gems_alert()
   └─ Envia sinais do gems system via Telegram

🔹 Função: log_signal()
   └─ Registra sinais em log unificado

🔹 Função: export_all_signals_csv()
   └─ Exporta CSV com todos os sinais

🔹 Função: get_signal_stats()
   └─ Retorna estatísticas dos sinais
```

### 3. **TELEGRAM_SETUP.md** (novo)
```
Tutorial completo de setup do Telegram
Passo a passo com imagens mentais
Troubleshooting
Dicas avançadas
```

---

## 🔌 Integrar com Gems System (app.py)

### Opção A: Integração Simples (Recomendado)

**Editar**: `gems_system/app.py`

**Encontre a seção onde monitora sinais** (linhas ~550-560):

```python
# ANTES:
if m['super_alert'] == "SUPER_BUY":
    super_html = '<div class="super-buy-alert">⚡ SUPER ALERTA: COMPRA</div>'

# DEPOIS - Adicione:
if m['super_alert'] == "SUPER_BUY":
    # Alerta Telegram
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from montrezor_alerts_integration import send_gems_alert, log_signal

        send_gems_alert(
            symbol=m['symbol'],
            signal_type="SUPER_BUY",
            market_cap=m.get('market_cap', 0),
            funding_rate=m.get('funding_rate', 0)
        )
        log_signal("GEMS", m['symbol'], {
            "type": "SUPER_BUY",
            "market_cap": m.get('market_cap'),
            "funding_rate": m.get('funding_rate')
        })
    except:
        pass  # Se não conseguir, apenas continua

    super_html = '<div class="super-buy-alert">⚡ SUPER ALERTA: COMPRA</div>'
```

### Opção B: Integração Completa

Substitua todas as ocorrências de alertas:

```python
# SUPER_BUY
if m['super_alert'] == "SUPER_BUY":
    _send_gems_telegram_alert(m['symbol'], "SUPER_BUY", m)
    log_signal("GEMS", m['symbol'], {"type": "SUPER_BUY"})

# SUPER_SELL
elif m['super_alert'] == "SUPER_SELL":
    _send_gems_telegram_alert(m['symbol'], "SUPER_SELL", m)
    log_signal("GEMS", m['symbol'], {"type": "SUPER_SELL"})

# BUY (Funding)
elif m['funding_signal'] == "BUY":
    _send_gems_telegram_alert(m['symbol'], "BUY", m)
    log_signal("GEMS", m['symbol'], {"type": "BUY"})

# SELL (Funding)
elif m['funding_signal'] == "SELL":
    _send_gems_telegram_alert(m['symbol'], "SELL", m)
    log_signal("GEMS", m['symbol'], {"type": "SELL"})
```

---

## 📥 Adicionar Botão de Export no Gems System

**No gems_system/app.py**, seção de controle (sidebar):

```python
import streamlit as st
import sys, os

# Adicione ao final do sidebar:

st.markdown("---")
st.markdown("### 📊 Exportar Dados")

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from montrezor_alerts_integration import export_all_signals_csv, get_signal_stats

    # Estatísticas
    stats = get_signal_stats()
    st.metric("Total de Sinais", stats['total'])

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Trading System", stats['trading'])
    with col2:
        st.metric("Gems System", stats['gems'])

    # Botão de export
    csv_data = export_all_signals_csv()
    st.download_button(
        label="📥 Exportar Todos os Sinais (CSV)",
        data=csv_data,
        file_name=f"montrezor_sinais_unificados_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )
except Exception as e:
    st.info(f"💭 Sistema de alertas não configurado. Erro: {str(e)[:50]}")
```

---

## 🧪 Testar Integração

### Teste 1: Verificar Config
```python
from montrezor_alerts_integration import load_telegram_config

token, chat_id = load_telegram_config()
print(f"Token: {token[:20]}..." if token else "❌ Não configurado")
print(f"Chat ID: {chat_id}" if chat_id else "❌ Não configurado")
```

### Teste 2: Enviar Sinal Teste
```python
from montrezor_alerts_integration import send_trading_alert

success = send_trading_alert("BTC-USD", "COMPRA", "SUPER", 45000.50)
print("✅ Enviado com sucesso!" if success else "❌ Erro ao enviar")
```

### Teste 3: Consultar Histórico
```python
from montrezor_alerts_integration import get_signal_stats
import pandas as pd

stats = get_signal_stats()
print(f"Total: {stats['total']}")
print(f"Trading: {stats['trading']}")
print(f"Gems: {stats['gems']}")
print(f"Último: {stats['last_signal']}")
```

---

## 📊 Analisar Assertividade

### Script Python para Análise

```python
import pandas as pd
from montrezor_alerts_integration import export_all_signals_csv
from io import StringIO

# Carregar dados
csv_data = export_all_signals_csv()
df = pd.read_csv(StringIO(csv_data))

# Análise por Sistema
print("═" * 50)
print("SINAIS POR SISTEMA")
print("═" * 50)
print(df['system'].value_counts())

# Análise por Direção (Trading)
print("\n═" * 50)
print("SINAIS TRADING - DIREÇÃO")
print("═" * 50)
trading = df[df['system'] == 'TRADING']
print(trading['direction'].value_counts())

# Análise por Tipo
print("\n═" * 50)
print("SINAIS POR TIPO (SUPER vs COMUM)")
print("═" * 50)
print(df['type'].value_counts())

# Sinais por Ativo (Top 10)
print("\n═" * 50)
print("TOP 10 ATIVOS COM MAIS SINAIS")
print("═" * 50)
print(df['symbol'].value_counts().head(10))

# Last 5 signals
print("\n═" * 50)
print("ÚLTIMOS 5 SINAIS")
print("═" * 50)
print(df.head(5).to_string())

# Estatísticas
print("\n═" * 50)
print("ESTATÍSTICAS GERAIS")
print("═" * 50)
print(f"Total de sinais: {len(df)}")
print(f"Primeiro sinal: {df['timestamp'].iloc[-1] if len(df) > 0 else 'N/A'}")
print(f"Último sinal: {df['timestamp'].iloc[0] if len(df) > 0 else 'N/A'}")
print(f"Ativos únicos: {df['symbol'].nunique()}")
print(f"Período: {len(df)} dias" if len(df) > 0 else "N/A")
```

---

## 🔍 Arquivos de Config/Log

```
~/.montrezor_telegram.json  ← Config Telegram (TOKEN + Chat ID)
~/.montrezor_data.json      ← Dados do Trading System
~/.montrezor_signals_unified.json  ← Log unificado de sinais
```

---

## ⚠️ Checklist de Implementação

Trading System:
- [x] Alerta com som + piscada
- [x] Persistência JSON
- [x] Histórico de sinais
- [x] Exportação CSV
- [x] Integração Telegram
- [x] Aba de configuração + tutorial

Gems System (TODO):
- [ ] Importar `montrezor_alerts_integration`
- [ ] Adicionar `send_gems_alert()` nos pontos de sinal
- [ ] Adicionar `log_signal()` nos pontos de sinal
- [ ] Botão de exportar CSV no sidebar
- [ ] Testado e validado

---

## 💡 Próximas Ideias

- [ ] Alertas via WhatsApp (usando messenger)
- [ ] Alertas via Email
- [ ] Dashboard unificado (uma única página com todos os dados)
- [ ] Análise de correlação entre sinais (quando ambos sistemas concordam)
- [ ] Backtesting automático com histórico
- [ ] Notificações por prioridade (Super vs Comum)

---

**✅ Integração Completa: Sempre vigilante, sempre informado!**
