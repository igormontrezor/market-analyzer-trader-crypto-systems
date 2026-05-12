# 📱 TELEGRAM ALERTS - Guia Completo

## O que é?

Sistema de notificações em tempo real via Telegram que avisa quando novos sinais são detectados no Trading System e Gems System, permitindo que você acompanhe os mercados de qualquer lugar.

---

## 🔧 Configuração Rápida (5 minutos)

### Passo 1: Criar um Bot no Telegram

1. **Abra o Telegram** e procure por: **@BotFather**
2. **Envie**: `/start`
3. **Envie**: `/newbot`
4. Escolha um **nome para o bot** (ex: "Montrezor Trader")
5. Escolha um **username único** (ex: "montrezor_trader_bot")
6. **Copie e guarde o TOKEN** que aparecerá:
   ```
   Done! Congratulations on your new bot. You will find it at t.me/montrezor_trader_bot.
   You can now add a description, about section and profile picture for your bot, see /help for a list of commands.

   Use this token to access the HTTP API:
   123456789:ABCdefGHIjklmnOpqrstUVWxyz1234567890
   ⚠️ COPIE ESTE TOKEN
   ```

### Passo 2: Obter seu Chat ID

1. **Abra o Telegram** e procure por: **@userinfobot**
2. **Envie** qualquer mensagem
3. Ele retornará seu **User ID**:
   ```
   Id: 987654321
   First name: Seu Nome
   Username: @seu_usuario
   ⚠️ COPIE O NÚMERO (987654321)
   ```

### Passo 3: Configurar no Montrezor

1. **Abra o Trading System**: `streamlit run trading_system.py`
2. Vá para a aba: **⚙️ Configurações**
3. Digite o **TOKEN** que você copiou do BotFather
4. Digite o **Chat ID** que você copiou do userinfobot
5. Clique em: **💾 Salvar Configuração**
6. Clique em: **📤 Enviar Teste**

Se receber uma mensagem no Telegram, tudo está funcionando! ✅

---

## 📋 O que você vai receber?

### Trading System - Sinal COMPRA
```
📈 SINAL SUPER ⭐
━━━━━━━━━━━━━━━━━━
Par: EURUSD#
Direção: COMPRA
Preço: 1.08765
Hora: 2026-05-12 14:32:58

🎯 Montrezor Trading System
```

### Trading System - Sinal VENDA
```
📉 SINAL COMUM •
━━━━━━━━━━━━━━━━━━
Par: CHFJPY#
Direção: VENDA
Preço: 162.345
Hora: 2026-05-12 15:45:23

🎯 Montrezor Trading System
```

### Gems System - Super Alert
```
⚡🟢 GEMS ALERT - SUPER_BUY
━━━━━━━━━━━━━━━━━━
Ativo: BTC
Status: SUPER_BUY
Hora: 2026-05-12 16:20:10
Market Cap: $45,000,000
Funding Rate: 2.300%

💎 Gems Finder System
```

---

## 🔐 Segurança

- **Nunca compartilhe seu TOKEN** com ninguém
- O TOKEN é como a senha do seu bot
- Arquivo de config: `~/.montrezor_telegram.json`
- Dados armazenados **localmente no seu PC**
- Recomendado: Bloqueie seu PC com PIN/Senha

---

## 🆘 Troubleshooting

### "Erro ao enviar. Verifique TOKEN e Chat ID"

- [ ] Copiei exatamente o TOKEN (sem espaços)?
- [ ] Copiei exatamente o Chat ID (número)?
- [ ] Confirmi no BotFather que o bot está ativo?
- [ ] O bot está em um grupo ou chat individual?

**Solução**: Teste com `@userinfobot` + `@BotFather` novamente

### "Não estou recebendo notificações"

- [ ] Ative notificações do Telegram no seu telefone
- [ ] Verificar em: Telegram → Configurações → Notificações
- [ ] Cheque se o chat está mutado (🔕 vs 🔔)

### "Como enviar para múltiplos chats?"

Crie múltiplos bots com `@BotFather`:
- Bot 1: Seu PC
- Bot 2: Seu Telegram pessoal
- Bot 3: Grupo de traders

Cada um terá seu próprio TOKEN.

---

## 💡 Dicas Avançadas

### Integrar Gems System (app.py)

1. **Abra**: `gems_system/app.py`
2. **Adicione ao topo**:
   ```python
   import sys
   sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
   from montrezor_alerts_integration import send_gems_alert, log_signal
   ```

3. **Quando detectar sinal**, adicione:
   ```python
   # Após detectar SUPER_BUY
   send_gems_alert("BTC", "SUPER_BUY", market_cap=50000000, funding_rate=0.023)
   log_signal("GEMS", "BTC", {"type": "SUPER_BUY", "market_cap": 50000000})
   ```

### Exportar Histórico Unificado

No Trading System, aba ⚙️ Configurações → Botão **📥 Exportar Histórico**

Gera CSV com todos os sinais para análise em pandas/Excel:

```
timestamp,system,symbol,direction,type,price
2026-05-12 16:20:10,GEMS,BTC,BUY,SUPER_BUY,45000.50
2026-05-12 15:45:23,TRADING,CHFJPY#,VENDA,COMUM,162.345
2026-05-12 14:32:58,TRADING,EURUSD#,COMPRA,SUPER,1.08765
```

---

## 📊 Integração com Análise

### Analisar Assertividade do Método

```python
import pandas as pd

df = pd.read_csv("montrezor_sinais_20260512_143258.csv")

# Por sistema
print(df['system'].value_counts())
# TRADING    24
# GEMS       8

# Por direção (Trading)
trading = df[df['system'] == 'TRADING']
print(trading['direction'].value_counts())
# COMPRA    15
# VENDA     9

# Por tipo de sinal
print(df['type'].value_counts())
# COMUM    18
# SUPER    14

# Sinais por ativo (Gems)
gems = df[df['system'] == 'GEMS']
print(gems.groupby('symbol').size())
# BTC    5
# ETH    3
```

---

## 🚀 Próximos Passos

1. **✅ Completar Setup Telegram** (este guia)
2. **Configure os ativos** que deseja acompanhar
3. **Defina os níveis Neuro Athena** para seus pares
4. **Deixe rodando** durante o perído de trading
5. **Exporte histórico** periodicamente para análise

---

## 📞 Suporte

- **Dúvidas sobre Telegram?** → Veja a aba "Guia de Configuração" no Trading System
- **Erro técnico?** → Tente clicar em "Enviar Teste" na aba ⚙️ Configurações
- **Dados não salvando?** → Verifique permissão na pasta `C:\Users\seu_usuario`

---

**🎯 Sistema sempre vigilante. Você, sempre informado. 24/7 em qualquer lugar.**
