# 🎯 Sistema Macro + Funding - RESUMO ESSENCIAL

## 📊 Lógica Principal

### 🎭 Condição Macro (USDT.D BB%B Mensal)

```
🟩 MODO COMPRA (buy_mode):
- USDT.D cruzou de cima para baixo a banda superior (1.0)
- OU USDT.D está entre 0.2 e 1.0
- Significado: Bear market iniciando/em andamento

🟥 MODO VENDA (sell_mode):
- USDT.D cruzou de baixo para cima a banda inferior (0.0)
- OU USDT.D está entre 0.0 e 0.8 (sem ser modo compra)
- Significado: Bull market iniciando/em andamento

🔒 CAPITULAÇÃO (capitulation_lock):
- MODO VENDA + USDT.D ≥ 0.8
- Significado: Euforia total - COMPRAS BLOQUEADAS
```

---

## 🎯 Matriz de Decisão (O que importa)

| Condição Macro | Condição de Mercado (Funding Rate) | Gatilho Semanal (Outros / USDT) | Sinal Gerado |
|----------------|-----------------------------------|-----------------------------------|----------------|
| **Modo Compra** | funding_rate < 0 | Neutro / Outros / Semanal | **Compra** |
| **Modo Compra** | funding_rate < 0 | Semanal + Outros indicam Compra | **Super Sinal de Compra** (Pisca no painel) |
| **Modo Venda** | funding_rate > 0.08 | Neutro / Outros / Semanal | **Venda** |
| **Modo Venda** | funding_rate > 0.08 | Semanal + Outros indicam Venda | **Super Sinal de Venda** (Pisca no painel) |

---

## 📡 Gatilhos Semanais (Timing)

### 🟢 GATILHO DE COMPRA
```python
weekly_buy_trigger = buy_mode and (
    others_touch_low or    # Altcoins no fundo (pânico)
    usdt_touch_high       # USDT.D no topo (refúgio)
)
```

### 🔴 GATILHO DE VENDA
```python
weekly_sell_trigger = sell_mode and (
    usdt_touch_low or    # USDT.D no fundo (saída de refúgio)
    others_high >= 1     # Altcoins eufóricas
)
```

### 🔵 REPIQUE TÁTICO
```python
tactical_rebound = sell_mode and usdt_touch_high and not capitulation_lock
```

---

## 🎯 Fluxo Simplificado

```
1. 📊 Verificar BB%B mensal → Define Modo (COMPRA/VENDA)
2. 💰 Verificar Funding Rate → Confirma ou refuta o modo
3. 👀 Verificar Gatilhos Semanais → Define o TIMING exato
4. 🚨 Gerar Sinal Final → Compra/Venda/Super Sinal
```

---

## 🚨 Super Sinais (Pisca no Painel)

### 🟢 SUPER BUY
- **Condições**: Modo Compra + Funding < 0% + Gatilho Semanal
- **Significado**: Confirmação máxima de entrada
- **Confiança**: 95%

### 🔴 SUPER SELL  
- **Condições**: Modo Venda + Funding > 0.08% + Gatilho Semanal
- **Significado**: Confirmação máxima de saída
- **Confiança**: 95%

---

## 📈 BB%B - A Lógica Complexa

### 🎯 Como Funciona o BB%B
```
BB%B = (Preço - Banda Inferior) / (Banda Superior - Banda Inferior)

0.0 = Banda inferior (mais barato)
0.5 = Meio das bandas (preço justo)
1.0 = Banda superior (mais caro)
```

### 🔄 O Repique Tático
- **Quando**: Modo Venda + USDT.D toca topo + Não está em capitulação
- **O que é**: Dinheiro volta do refúgio (USDT.D) para as altcoins
- **Resultado**: Altcoins sobem rapidamente (repique)

### 🎭 Ciclo Típico
```
1. Euforia: USDT.D 1.20 → Capitulação ativa 🚫
2. Correção: USDT.D 0.85 → Alerta de venda ⚠️
3. Oportunidade: USDT.D 0.25 → Modo compra ativado 🟩
4. Pânico: Altcoins fundo → Gatilho de compra 🟢
5. Recuperação: Dinheiro volta → Replique tático 🔵
6. Nova euforia: USDT.D 1.10 → Ciclo recomeça 🔄
```

---

## 🎯 Resumo Final

**O sistema faz 3 perguntas:**
1. **Qual o regime?** (BB%B mensal)
2. **O funding confirma?** (Taxa de juros)
3. **É o momento certo?** (Gatilhos semanais)

**Resposta só vem quando as 3 concordam!**

---
*Essência do sistema em 1 página*
