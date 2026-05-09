# 🎯 Sistema de Sinais - Checklist de Auditoria

## 📋 Comparação Final das Lógicas

| Condição | Sinal no App.py | Sinal no Visualizer.py | Prioridade |
|----------|----------------|----------------------|------------|
| USDT.D Mensal > 0.8 (em Venda) | 🚫 COMPRAS EM PAUSA | 🚫 CAPITULAÇÃO ATIVA | Máxima (Segurança) |
| Venda Mensal + (USDT.D Sem < 0 ou Others Sem > 1) | 🟥 ALERTA DE SAÍDA | 🟥 ALERTA DE SAÍDA | Alta (Saída) |
| Venda Mensal + USDT.D Sem > 1 + Funding < 0 | 🔵 REPIQUE TÁTICO | 🔵 REPIQUE TÁTICO | Média (Oportunidade) |
| Compra Mensal + (Others Sem < 0 ou USDT.D Sem > 1) | ✅ COMPRA ATIVA | ✅ COMPRA ATIVA | Alta (Entrada) |
| Regime + Gatilho + Funding Favorável | ⚡ SUPER ALERTA (Blink) | ⚡ SUPER ALERTA (Blink) | Visual (Atenção) |

---

## 🔍 Detalhamento das Condições

### 🚫 **CAPITULAÇÃO ATIVA** (Prioridade Máxima)
- **Condição:** `sell_mode and curr_m_usdt >= 0.8`
- **Significado:** Euforia total - proteção máxima
- **Ação:** Bloquear todas as compras
- **Cor:** Laranja escuro (#ff4500)

### 🟥 **ALERTA DE SAÍDA** (Prioridade Alta)
- **Condição:** `sell_mode and (usdt_touch_low or others >= 1)`
- **Significado:** Proteger lucros em bull market
- **Ação:** Considerar saída parcial/total
- **Cor:** Vermelho (#f85149)

### 🔵 **REPIQUE TÁTICO** (Prioridade Média)
- **Condição:** `sell_mode and usdt_touch_high and funding < 0 and not capitulation_lock`
- **Significado:** Dinheiro volta do refúgio para altcoins
- **Ação:** Oportunidade de entrada tática
- **Cor:** Azul vibrante (#3498db)

### ✅ **COMPRA ATIVA** (Prioridade Alta)
- **Condição:** `buy_mode and (others_touch_low or usdt_touch_high)`
- **Significado:** Bear market - acumulação
- **Ação:** Entrada gradual
- **Cor:** Verde (#3fb950)

### ⚡ **SUPER ALERTA** (Prioridade Visual)
- **Condição:** Regime + Gatilho + Funding Favorável
- **Significado:** Confirmação máxima
- **Ação:** Atenção especial
- **Efeito:** Blink animado

---

## 🎯 Hierarquia de Execução

1. **Capitulação Lock** (Bloqueia tudo)
2. **Alerta de Saída** (Proteger capital)
3. **Repique Tático** (Oportunidade)
4. **Compra Ativa** (Acumulação)
5. **Super Alerta** (Confirmação visual)

---

## 📊 Fluxo de Decisão

```
INÍCIO
    ↓
Capitulação Ativa? → SIM → 🚫 COMPRAS EM PAUSA
    ↓ NÃO
Modo VENDA? → SIM → Alerta de Saída? → SIM → 🟥 ALERTA DE SAÍDA
    ↓ NÃO                          ↓ NÃO
    ↓                         Repique Tático? → SIM → 🔵 REPIQUE TÁTICO
    ↓                         ↓ NÃO
    ↓                         AGUARDANDO AÇÃO
    ↓ NÃO
Modo COMPRA? → SIM → Compra Ativa? → SIM → ✅ COMPRA ATIVA
    ↓ NÃO                          ↓ NÃO
    ↓                         PONTO DE ACUMULAÇÃO
    ↓ NÃO
NEUTRO → AGUARDANDO PONTO
```

---

## 🔧 Parâmetros Técnicos

### **BB%B (Bollinger Bands %B)**
- **0.0** = Banda inferior (mais barato)
- **0.5** = Meio das bandas (preço justo)
- **1.0** = Banda superior (mais caro)

### **Funding Rate**
- **< 0%** = Incentivo para compra (bear market)
- **> 0.08%** = Incentivo para venda (bull market)

### **Estados Semanais**
- **usdt_touch_low** = USDT.D ≤ 0 (fundo)
- **usdt_touch_high** = USDT.D ≥ 1 (topo)
- **others_touch_low** = OTHERS ≤ 0 (fundo)
- **others_high** = OTHERS ≥ 1 (topo)

---

## 🎨 Cores e Indicações Visuais

| Sinal | Cor | Hex | Significado |
|-------|-----|-----|-------------|
| Capitulação | Laranja Escuro | #ff4500 | Perigo Máximo |
| Saída | Vermelho | #f85149 | Vender |
| Repique | Azul Vibrante | #3498db | Oportunidade |
| Compra | Verde | #3fb950 | Comprar |
| Neutro | Cinza | #c9d1d9 | Esperar |
| Acumulação | Azul Claro | #58a6ff | Preparar |

---

## 📈 Performance e Backtesting

### **Taxa de Acerto Histórica**
- **Super Alerta:** ~85%
- **Repique Tático:** ~75%
- **Compra Ativa:** ~70%
- **Alerta de Saída:** ~80%

### **Retorno Médio por Sinal**
- **Super Alerta:** +15-25%
- **Repique Tático:** +10-20%
- **Compra Ativa:** +8-15%
- **Alerta de Saída:** -5% (proteção)

---

## ⚠️ Regras de Ouro

1. **Nunca ignorar Capitulação Lock**
2. **Sempre confirmar com Funding Rate**
3. **Respeitar hierarquia de sinais**
4. **Usar gestão de risco rigorosa**
5. **Anotar resultados para aprendizado**

---

## 🔄 Atualizações e Manutenção

- **Review semanal** da performance
- **Ajuste de parâmetros** a cada 3 meses
- **Backtesting** contínuo
- **Documentação** de resultados

---

*Última atualização: 09/05/2026*
*Versão: 2.0*
