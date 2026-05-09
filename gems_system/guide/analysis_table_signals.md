# 📊 Guia de Colunas da Tabela - Sistema GEMS

## 🎯 Visão Geral
As colunas da tabela representam diferentes camadas de análise, desde a classificação básica até sinais avançados de exaustão. Cada métrica adiciona uma camada de informação para tomada de decisão.

---

## 📈 **Classificação** (Nível Básico)
### **O que mede:**
- Categoria temporal da moeda baseada em persistência de performance
- Classificação automática segundo timeframe de consistência

### **Como funciona:**
```python
# Baseado em contagem de dias positivos consecutivos
- 3D+   → Consistência de curto prazo
- 7D+   → Consistência de médio prazo  
- 14D+  → Consistência de longo prazo
- MIXED → Performance mista/instável
```

### **Interpretação:**
- **3D+/7D+/14D+**: Moedas em tendência de alta consistente
- **MIXED**: Moedas voláteis sem direção clara

---

## 👑 **Leader** (Nível Intermediário)
### **O que mede:**
- Status de liderança vs BTC (força relativa)
- Indica se a moeda está superando o Bitcoin

### **Como funciona:**
```python
# Comparação de performance vs BTC nas últimas 24h
if performance_vs_btc > 5%:  Leader = 👑 YES
else:                         Leader = ❌ NO
```

### **Interpretação:**
- **👑 YES**: Superando BTC (potencial de alpha)
- **❌ NO**: Performance inferior a BTC (seguindo mercado)

---

## 🎯 **Zone** (Nível Intermediário)
### **O que mede:**
- Regime de mercado baseado em estrutura de preço
- Identifica fase do ciclo (acumulação/distribuição)

### **Como funciona:**
```python
# Análise de estrutura de mercado
- ACCUMULATION: Preço abaixo de médias, volume baixo
- DISTRIBUTION: Preço acima de médias, volume alto
- EXPANSION: Rompimento de resistências
- CORRECTION: Retração após alta
```

### **Interpretação:**
- **ACCUMULATION**: Boa zona para entrada gradual
- **DISTRIBUTION**: Atenção para possível reversão
- **EXPANSION**: Momentum forte de alta
- **CORRECTION**: Oportunidade de recompra

---

## 🚀 **Momentum** (Nível Avançado)
### **O que mede:**
- Força e direção do movimento atual
- Combina preço, volume e velocidade

### **Como funciona:**
```python
# Cálculo baseado em:
- Variação percentual ponderada por volume
- Taxa de aceleração/desaceleração
- Comparação com médias móveis
```

### **Interpretação:**
- **STRONG**: Movimento robusto e sustentado
- **MODERATE**: Movimento moderado e estável
- **WEAK**: Movimento fraco ou perdendo força

---

## 🏆 **Gold** (Nível Avançado)
### **O que mede:**
- Status premium da moeda (qualidade institucional)
- Combina múltiplas métricas de qualidade

### **Como funciona:**
```python
# Critérios para status Gold:
- Market Cap > $50M
- Volume/MC Ratio > 0.05
- Performance vs BTC > 10%
- Score final > 0.7
- Persistência > 7 dias
```

### **Interpretação:**
- **🥇 GOLD**: Ativo de alta qualidade, institucional
- **Regular**: Ativo padrão, sem destaque especial

---

## ⚡ **Status** (Nível Especialista)
### **O que mede:**
- Sinal de exaustão baseado em MC + aceleração
- Alerta precoce de reversão ou continuação

### **Como funciona:**
```python
# Lógica de exaustão:
if MC > 35M AND trend == 'decelerating':
    Status = "⚠️ ESTICADA (Exaustão)"
elif trend == 'accelerating':
    Status = "🚀 ACELERANDO"
elif trend == 'decelerating':
    Status = "📉 DESACELERANDO"
else:
    Status = "➡️ ESTÁVEL"
```

### **Interpretação:**
- **⚠️ ESTICADA**: Cuidado! MC alto + perdendo força
- **🚀 ACELERANDO**: Bom momento! Ganhando força
- **📉 DESACELERANDO**: Atenção! Perdendo momento
- **➡️ ESTÁVEL**: Neutro, sem mudança significativa

---

## 🎯 **Hierarquia de Decisão (Crescente)**

### **1. Classificação** 📊
- **"Onde estou?"** - Identifica o timeframe

### **2. Leader** 👑  
- **"Estou superando BTC?"** - Força relativa

### **3. Zone** 🎯
- **"Em que fase do ciclo?"** - Estrutura de mercado

### **4. Momentum** 🚀
- **"Qual a força do movimento?"** - Intensidade atual

### **5. Gold** 🏆
- **"É um ativo premium?"** - Qualidade institucional

### **6. Status** ⚡
- **"Está exausto ou acelerando?"** - Sinal de exaustão

---

## 🔍 **Como Usar na Prática**

### **Para COMPRA:**
```
✅ Classificação: 7D+ ou 14D+
✅ Leader: 👑 YES (superando BTC)
✅ Zone: ACCUMULATION ou EXPANSION
✅ Momentum: STRONG ou MODERATE
✅ Gold: 🥇 GOLD (se disponível)
✅ Status: 🚀 ACELERANDO ou ➡️ ESTÁVEL
```

### **Para VENDA:**
```
⚠️ Classification: MIXED ou 3D-
⚠️ Leader: ❌ NO (perdendo para BTC)
⚠️ Zone: DISTRIBUTION
⚠️ Momentum: WEAK
⚠️ Status: ⚠️ ESTICADA (Exaustão)
```

---

## 📚 **Resumo Rápido**

| Coluna | Nível | Pergunta-Chave | Sinal Verde |
|--------|-------|----------------|-------------|
| **Classification** | Básico | Qual meu timeframe? | 7D+, 14D+ |
| **Leader** | Intermediário | Superando BTC? | 👑 YES |
| **Zone** | Intermediário | Que fase do ciclo? | ACCUMULATION |
| **Momentum** | Avançado | Qual a força? | STRONG |
| **Gold** | Avançado | É premium? | 🥇 GOLD |
| **Status** | Especialista | Exausto? | 🚀 ACELERANDO |

---

*Última atualização: 09/05/2026*  
*Versão: 1.0*
