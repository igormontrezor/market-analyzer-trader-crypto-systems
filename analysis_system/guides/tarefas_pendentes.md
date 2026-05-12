# Tarefas Pendentes - Market Analysis

## 📋 Tarefas em Andamento

### 📊 Análise de Métricas (Mensal)
- [x] **Lapidar Sharpe Ratio** - Revisar e otimizar cálculo do Sharpe no período mensal
- [x] **Lapidar Sortino Ratio** - Revisar e otimizar cálculo do Sortino no período mensal

### 🔗 Integração BTC + SPY (Versão 0.1 Concluída)
- [x] **Plotar RSI Stochastic do SPY** - Adicionar no gráfico geral
- [x] **Atualizar plot_top()** - Incluir pontos de comparação SPY no gráfico BTC
- [x] **Atualizar plot_bottom()** - Incluir pontos de comparação SPY no gráfico BTC
- [x] **Plotar topos/fundos RSI no BTC** - Integrar análise SPY para identificar pontos extremos

### 🚀 Evolução do Sistema (Versão 0.2)
- [ ] **Backtesting de Sinais** - Analisar performance histórica dos sinais gerados
- [ ] **Score de Confiança** - Criar indicador único combinando múltiplos fatores
- [ ] **Alertas Automáticos** - Sistema de notificação para convergência de indicadores
- [ ] **Análise de Correlação Rolling** - Calcular correlação dinâmica BTC-SPY
- [ ] **Dashboard Interativo** - Interface com filtros dinâmicos e drill-down
- [ ] **Adicionar Mais Ativos** - DXY, Ouro, Tesouros para análise completa
- [ ] **Zonas de Reversão** - Mapear áreas probáveis de reversão baseadas em histórico

---

## 📝 Notas Rápidas
*Data: 01/04/2026*
*Status: Versão 0.1 Concluída - MRTZ System pre-alpha*

### Observações:
- ✅ Versão 0.1 finalizada com integração completa BTC+SPY
- ✅ Sistema identifica topos/fundos do mercado geral sobre gráfico BTC
- ✅ Análise multidimensional com Sharpe/Sortino, BB %B, RSI, MACD
- 🎯 Próximo objetivo: Evoluir para Versão 0.2 com recursos avançados

### Conquistas da Versão 0.1:
- Sistema integrado semanal + mensal
- Detecção de pontos extremos em BTC e SPY
- Visualização com 10 camadas de indicadores
- Reconhecimento de correlação BTC-mercados tradicionais

---

## ✅ Tarefas Concluídas (Versão 0.1)
- [x] Lapidar Sharpe Ratio
- [x] Lapidar Sortino Ratio
- [x] Integração completa BTC + SPY
- [x] Sistema de visualização com 10 camadas
- [x] Detecção de topos/fundos multidimensional
- [x] Análise semanal e mensal integrada
---

## Novas Tarefas Prioritárias

### **Sistema de Visualização Dinâmica**
- [ ] **Implementar Sistema de Gráficos Padrão** - Criar módulo para visualização flexível
- [ ] **Opções de Visualização** - Permitir escolha entre gráficos juntos ou separados
- [ ] **Atualização Automática** - Manter sinais existentes + adicionar novos padrões
- [ ] **Manutenção Simplificada** - Facilitar modificação dos códigos de gráficos

### **Estratégias de Trading**
- [ ] **Implementar Entrada Semanal Compra** - Stoch > 50% + fundo duplo BB + RSI fundo + MACD cruzando
- [ ] **Confirmar Fundo Diário** - Aguardar confirmação no timeframe diário
- [ ] **Sistema de Cruzamento USDT Dominance** - Identificar cruzamento para baixo para compra de altcoins **(EM DESTAQUE)**
- [ ] **Fazer Sistema de Cruzamento Bollinger Bands 50%** - Ativar compra de altcoins quando BB cruzar 50% para cima **(EM DESTAQUE)**
---

## Roadmap Versão 0.2
### Validação e Performance

#### **Backtesting de Sinais**
Conceito: Para cada sinal (topo/fundo), verificar o que aconteceu nos próximos N dias
- **Topos:** Preço caiu X% após o sinal?
- **Fundos:** Preço subiu Y% após o sinal?
- **Métricas:** Calcular win rate, profit factor, drawdown

#### **Score de Confiança**
Conceito: Sistema de pontuação 0-100 baseado em pesos
- **Sharpe/Sortino:** 25% cada (mais importante)
- **BB %B e RSI:** 20% cada (momentum)
- **VIX:** 10% (contexto de mercado)
- **Regra:** Quanto mais extremos os valores, maior o score

#### **Métricas de Performance**
Conceito: Estatísticas básicas de trading
- **Win Rate:** % de sinais corretos
- **Profit Factor:** Ganhos totais ÷ Perdas totais
- **Análise:** Separar performance de topos vs fundos

### Inteligência e Automação

#### **Alertas Automáticos**
Conceito: Detectar quando múltiplos indicadores convergem
- **Regra:** 5+ de 8 indicadores alinhados = alerta
- **Topo:** BTC e SPY com indicadores extremos altos
- **Fundo:** BTC e SPY com indicadores extremos baixos
- **Força:** Número de indicadores alinhados (5-8)

#### **Sistema de Prioridade**
Conceito: Classificar sinais por probabilidade de sucesso
- **Fórmula:** Score Confiança (40%) + Convergência (60%)
- **Objetivo:** Focar nos sinais mais fortes primeiro
- **Output:** Lista ordenada de oportunidades

#### **Dashboard Interativo**
Conceito: Interface web para visualização e filtros
- **Filtros:** Timeframe, confiança mínima, tipo de sinal
- **Visual:** Gráficos interativos com drill-down
- **Seções:** Sinais atuais, performance histórica, alertas

### Expansão de Mercados

#### **Mais Ativos**
Conceito: Expandir universo para análise completa
- **Macroeconomia:** DXY (dólar), Tesouros (juros)
- **Commodities:** Ouro (safe haven)
- **Ações:** QQQ (tech), DIA (industrial), IWM (small caps)
- **Objetivo:** Ver correlações e divergências

#### **Correlação Rolling**
Conceito: Calcular correlação móvel entre ativos
- **Janela:** 60 períodos (adaptável)
- **Pares:** BTC-SPY, BTC-DXY, SPY-VIX
- **Aplicação:** Identificar quando correlações se quebram

#### **Zonas de Reversão**
Conceito: Mapear níveis de preço testados múltiplas vezes
- **Lógica:** Níveis com 3+ toques = zona importante
- **Tipos:** Suporte (fundos) e Resistência (topos)
- **Força:** Número de toques ÷ total de períodos

---

*Última atualização: 01/04/2026 - Versão 0.1 Concluída*


class MockProvider(PriceProvider):
    def get_price(self, symbol):
        return 100
