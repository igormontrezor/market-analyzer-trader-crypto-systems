import streamlit as st
import plotly.graph_objects as go
import numpy as np

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="MONTREZOR - Trading System", layout="wide", page_icon="💎")

# Inicialização de Session States para interatividade
if 'step_active' not in st.session_state:
    st.session_state.step_active = 0
if 'entrada_active' not in st.session_state:
    st.session_state.entrada_active = "A+"
if 'simular_stoch' not in st.session_state:
    st.session_state.simular_stoch = False

# 2. CSS CUSTOMIZADO (Baseado no app.py e no HTML original)
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 95%; }
    [data-testid="stAppViewContainer"] { background-color: #0b0e11; }

    /* Cards e Containers */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #30363d; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px; color: #8b949e; border-radius: 4px 4px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; background-color: #161b22;
    }

    .rule-card {
        background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 15px;
    }
    .rule-title { color: #c9d1d9; font-size: 16px; font-weight: bold; margin-bottom: 10px; display: flex; align-items: center; gap: 10px;}
    .rule-badge { background: #da3633; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
    .rule-body { color: #8b949e; font-size: 14px; line-height: 1.6; }

    .info-box {
        background-color: #1c2128; border-left: 4px solid #3B8BD4; padding: 15px; border-radius: 4px; color: #c9d1d9; font-size: 14px; margin-bottom: 20px;
    }

    .tf-card { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }
    .tf-label { color: #8b949e; font-size: 12px; font-weight: bold; }
    .tf-val { font-size: 20px; font-weight: bold; margin: 5px 0; }
    .tf-desc { color: #484f58; font-size: 11px; }

    /* Edge Signal Bars */
    .signal-row { display: flex; align-items: center; gap: 15px; margin-bottom: 12px; }
    .signal-tf { color: #8b949e; font-weight: bold; width: 40px; }
    .signal-bar-wrap { flex: 1; height: 10px; background: #30363d; border-radius: 5px; overflow: hidden; }
    .signal-bar { height: 100%; border-radius: 5px; }
    .signal-val { width: 80px; text-align: right; font-size: 13px; font-weight: bold; }

    /* Checklists Especiais */
    .static-check { display: flex; align-items: center; gap: 10px; padding: 8px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; margin-bottom: 8px; color: #c9d1d9; font-size: 14px;}
    .static-check.checked { border-color: #1D9E75; }
    .static-check.warning { border-color: #EF9F27; }
    </style>
""", unsafe_allow_html=True)

st.title("💎 Sistema de Trading - Igor Montrezor")
st.markdown("<p style='color: #8b949e; margin-top: -15px; margin-bottom: 30px;'>Método interativo passo a passo para execução de alta performance.</p>", unsafe_allow_html=True)

# 3. NAVEGAÇÃO PRINCIPAL (TABS)
tab_visao, tab_rsi, tab_stoch, tab_entradas, tab_checklist, tab_edge = st.tabs([
    "👁️ Visão Geral", "📈 Canal RSI", "📉 Stoch RSI", "🎯 Entradas", "✅ Checklist", "⚡ Edge do Sistema"
])

# --- TAB 1: VISÃO GERAL ---
with tab_visao:
    st.markdown('<div class="info-box">O método opera no alinhamento de timeframes maiores com execução refinada nos menores. Siga a ordem rigorosamente.</div>', unsafe_allow_html=True)

    steps = [
        {"title": "1. Identificar tendência", "desc": "Supertrend + direção no timeframe maior. Nunca operar contra a tendência.", "detail": "Identifique a tendência principal usando o Supertrend no timeframe maior (semanal/mensal). A tendência é o maior peso do sistema — nunca opere contra ela."},
        {"title": "2. Canal RSI no TF maior", "desc": "RSI no suporte/resistência do canal. Peso maior para semanal e mensal.", "detail": "Aguarde o RSI atingir o suporte ou resistência do canal de tendência no semanal/mensal. Peso maior para timeframes maiores. Não entre no meio do canal."},
        {"title": "3. Stoch RSI no TF menor", "desc": "Stochastic RSI no contra-fundo/topo — inverso da tendência nos TFs menores.", "detail": "Com o RSI no canal do TF maior, aguarde o Stochastic RSI no fundo (para compras) ou no topo (para vendas) no timeframe menor (4H ou D1). É a confirmação do pullback."},
        {"title": "4. Fibo + R:R mín 1:5", "desc": "0.5–0.618 tocado. Take profit na extensão 0.618 (A+) ou 0.328 (A/B).", "detail": "Verifique se o Fibonacci 0.5–0.618 foi tocado. O take profit alvo é a extensão 0.618 (entrada A+) ou 0.328 (entrada A/B). R:R mínimo obrigatório de 1:5."},
        {"title": "5. Executar entrada", "desc": "Inversão do Supertrend. Stop no extremo do canal RSI. Máx 3% risco.", "detail": "Com todos os filtros alinhados, execute a entrada na inversão do Supertrend. Stop loss no extremo do canal RSI, nas médias móveis 50/100/200 ou na extensão Fibonacci."},
        {"title": "6. Gerenciar saída", "desc": "Take profits via Fibo/Neuro Athena. Alerta RSI + Stoch em direções opostas.", "detail": "Use o Método Hougaard para saídas parciais. Alertas de saída: RSI seguindo a tendência em uma direção e Stochastic na direção oposta nos TFs maiores (W/MN)."}
    ]

    # Criar botões estilo Cards
    cols = st.columns(3)
    for i, step in enumerate(steps):
        col_idx = i % 3
        with cols[col_idx]:
            # Usando botões do Streamlit para simular os cards interativos
            btn_type = "primary" if st.session_state.step_active == i else "secondary"
            if st.button(f"{step['title']}\n\n{step['desc']}", key=f"step_{i}", use_container_width=True, type=btn_type):
                st.session_state.step_active = i
                st.rerun()

    st.markdown("---")
    st.markdown(f"### Detalhe do Passo {st.session_state.step_active + 1}")
    st.info(steps[st.session_state.step_active]['detail'])

# --- TAB 2: CANAL RSI ---
with tab_rsi:
    st.markdown('<div class="info-box">O canal do RSI é a base do sistema. O preço precisa estar no suporte ou resistência do canal para acionar uma entrada válida.</div>', unsafe_allow_html=True)

    # Gerar dados falsos para o gráfico de RSI
    np.random.seed(42)
    x_rsi = list(range(50))
    y_rsi = np.cumsum(np.random.randn(50) * 3) + 50
    y_rsi = np.clip(y_rsi, 20, 80)

    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=x_rsi, y=y_rsi, name="RSI", line=dict(color="#3B8BD4", width=2)))
    fig_rsi.add_trace(go.Scatter(x=x_rsi, y=[72]*50, name="Resistência", line=dict(color="#1D9E75", width=1, dash="dash")))
    fig_rsi.add_trace(go.Scatter(x=x_rsi, y=[28]*50, name="Suporte", line=dict(color="#E8593C", width=1, dash="dash")))

    fig_rsi.update_layout(
        template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0),
        title="CANAL RSI — SEMANAL (Simulado)",
        yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.1)"),
        xaxis=dict(showgrid=False, showticklabels=False)
    )
    st.plotly_chart(fig_rsi, use_container_width=True)

    st.markdown("""
    <div class="rule-card">
        <div class="rule-title"><span class="rule-badge">REGRA PRINCIPAL</span> Exemplo tendência global COMPRA </div>
        <div class="rule-body">
            Quando o RSI toca o <b>fundo do canal de tendência</b> (no semanal/diario/4hs), aguarde o Stochastic RSI confirmar nos timeframes menores (Reversao para a tendencia principal no 4hs).<br><br>
            <b style="color: #f85149;">Nunca operar contra a tendência.</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown('<div class="tf-card"><div class="tf-label">MN</div><div class="tf-val" style="color:#1D9E75">+ 65</div><div class="tf-desc">forte — acima 50</div></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="tf-card"><div class="tf-label">W1</div><div class="tf-val" style="color:#1D9E75">+ 52</div><div class="tf-desc">pullback no fundo</div></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="tf-card"><div class="tf-label">D1</div><div class="tf-val" style="color:#EF9F27">≈ 35</div><div class="tf-desc">fundo do canal</div></div>', unsafe_allow_html=True)
    with c4: st.markdown('<div class="tf-card"><div class="tf-label">H4</div><div class="tf-val" style="color:#3B8BD4">RSI tocando canal + STCRSI ↑ virando</div><div class="tf-desc">execução</div></div>', unsafe_allow_html=True)

# --- TAB 3: STOCH RSI ---
with tab_stoch:
    st.markdown('<div class="info-box">O Stochastic RSI confirma a entrada nos timeframes menores, sempre na direção <i>inversa</i> à tendência (fundo/topo do Stoch no TF menor).</div>', unsafe_allow_html=True)

    # Lógica de simulação Stoch
    np.random.seed(10)
    x_stoch = list(range(60))
    k_line = np.cumsum(np.random.randn(60) * 8) + 50
    k_line = np.clip(k_line, 5, 95)

    # Se simular entrada, joga a ponta pro fundo e cruza pra cima
    if st.session_state.simular_stoch:
        k_line[-5:] = [30, 20, 10, 8, 25] # Mergulha e vira forte

    # %D é uma média móvel suave de %K
    d_line = [k_line[0]]
    for i in range(1, len(k_line)):
        d_line.append(d_line[-1] * 0.7 + k_line[i] * 0.3)

    fig_stoch = go.Figure()
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=k_line, name="%K", line=dict(color="#9F77DD", width=2)))
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=d_line, name="%D", line=dict(color="#5DCAA5", width=2)))
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=[80]*60, name="Overbought", line=dict(color="#E8593C", width=1, dash="dash")))
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=[20]*60, name="Oversold", line=dict(color="#3B8BD4", width=1, dash="dash")))

    fig_stoch.update_layout(
        template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0),
        title="STOCHASTIC RSI — 4H (Simulado)",
        yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.1)"),
        xaxis=dict(showgrid=False, showticklabels=False)
    )
    st.plotly_chart(fig_stoch, use_container_width=True)

    col_btn, col_msg = st.columns([1, 3])
    with col_btn:
        if st.button("🚀 Simular Sinal", type="primary"):
            st.session_state.simular_stoch = not st.session_state.simular_stoch
            st.rerun()
    with col_msg:
        if st.session_state.simular_stoch:
            st.success("↑ Sinal de compra detectado — Stoch saindo do oversold cruzando %K sobre %D.")

    st.markdown("""
    <div class="rule-card" style="margin-top: 15px;">
        <div class="rule-title">Lógica de confirmação</div>
        <div class="rule-body">
            <b>Compra:</b> Tendência mensal/semanal de alta → RSI tocar fundo do canal 1W/D1/4H no (oversold) → entrada quando stochastico RSI 4H virar para cima.<br><br>
            <b>Venda:</b> Tendência mensal/semanal de baixa → RSI tocar topo do canal 1W/D1/4H no (overbought) → entrada quando stochastico RSI 4H virar para baixo.<br><br>
            VERIFICAR OUTROS PARAMETROS COMO NEURO ATHENA, MEDIA MOVEL EXPONENCIAL SUPERTREND PARA CONFLUENCIAS
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- TAB 4: ENTRADAS ---
with tab_entradas:
    st.markdown('<div class="info-box">Existem três tipos de entrada, ordenadas por qualidade. Selecione para ver os critérios.</div>', unsafe_allow_html=True)

    tipo_entrada = st.radio("Selecione o Setup:", ["A+ (Melhor Setup)", "A (Principal)", "B (Proteção)"], horizontal=True)

    if "A+" in tipo_entrada:
        st.markdown("""
        <div class="static-check checked">✅ Supertrend na mesma direção do TF maior</div>
        <div class="static-check checked">✅ Tendência semanal alinhada</div>
        <div class="static-check checked">✅ RSI no canal de resistência/suporte — TFs maiores</div>
        <div class="static-check checked">✅ Stoch RSI no contra fundo/topo no TF menor (inverso)</div>
        <div class="static-check checked">✅ Fibonacci 0.5–0.618 tocado</div>
        <div class="static-check checked">✅ Indicadores do market_analisis confirmam (W + D)</div>
        <div class="static-check checked">✅ R:R mínimo 1:5 — TP na extensão Fibo 0.618</div>
        """, unsafe_allow_html=True)
        st.success("Todos os filtros alinhados. Take profit na extensão Fibonacci 0.618 (Neuro Athena). Maior probabilidade de sucesso.")

    elif "A (" in tipo_entrada:
        st.markdown("""
        <div class="static-check checked">✅ Supertrend na mesma direção do TF maior</div>
        <div class="static-check checked">✅ Tendência semanal alinhada</div>
        <div class="static-check checked">✅ RSI no canal de resistência/suporte — TFs maiores</div>
        <div class="static-check checked">✅ Stoch RSI no contra fundo/topo no TF menor (inverso)</div>
        <div class="static-check warning">⚠️ Fibonacci 0.5–0.618 tocado (não obrigatório)</div>
        <div class="static-check checked">✅ R:R mínimo 1:5 — TP na extensão Fibo 0.328</div>
        """, unsafe_allow_html=True)
        st.info("Entrada principal do sistema. Take profit mais conservador na extensão 0.328. Sem necessidade de Fibonacci confirmado.")

    else:
        st.markdown("""
        <div class="static-check checked">✅ Neuro Athena: linha Buy/Sell Entry INVERTIDA na tendência</div>
        <div class="static-check checked">✅ Supertrend na mesma direção do TF maior</div>
        <div class="static-check checked">✅ Tendência semanal alinhada</div>
        <div class="static-check checked">✅ RSI no canal — TFs maiores</div>
        <div class="static-check checked">✅ Stoch RSI no contra fundo/topo no TF menor</div>
        <div class="static-check checked">✅ R:R mínimo 1:5 — TP na extensão Fibo 0.328</div>
        """, unsafe_allow_html=True)
        st.warning("Entrada de proteção. Usa a linha invertida do Neuro Athena como gatilho. Mesmos filtros da Entrada A com TP 0.328.")

# --- TAB 5: CHECKLIST ---
with tab_checklist:
    st.markdown('<div class="info-box">Marque cada critério antes de entrar. O score mostra a qualidade do setup em tempo real.</div>', unsafe_allow_html=True)

    crit = [
        "Supertrend alinhado com tendência maior (Verificar no semanal/mensal)",
        "Tendência semanal confirmada (MN + W1 na mesma direção)",
        "RSI no canal — suporte ou resistência (Peso maior para W1/MN)",
        "Stoch RSI no fundo/topo no TF menor (inverso no 4H ou D1)",
        "Fibonacci 0.5–0.618 tocado (Neuro Athena ou manual)",
        "R:R mínimo 1:5 calculado (Stop técnico posicionado)",
        "Risco máx 3% da conta definido (Tamanho da posição calculado)"
    ]

    score = 0
    for c in crit:
        if st.checkbox(c, key=f"chk_{c[:10]}"):
            score += 1

    pct = score / len(crit)

    st.markdown("---")
    c1, c2 = st.columns([4, 1])
    with c1:
        st.progress(pct)
        if score == len(crit):
            st.success("Setup A+ — Todos os critérios alinhados. Pode entrar!")
        elif score >= 5:
            st.info("Setup Bom — Quase pronto para entrar.")
        else:
            st.warning("Setup Incompleto — Faltam critérios importantes.")
    with c2:
        st.markdown(f"<h3 style='text-align: right; margin-top: -10px; color: #58a6ff;'>{score} / 7</h3>", unsafe_allow_html=True)

# --- TAB 6: EDGE DO SISTEMA ---
with tab_edge:
    st.markdown('<div class="info-box">O sistema funciona pela hierarquia de timeframes: o maior manda, o menor executa.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="rule-card">
            <div class="rule-title" style="color:#1D9E75">🟢 Configuração de COMPRA</div>
            <div class="signal-row">
                <div class="signal-tf">MN</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:75%;background:#1D9E75"></div></div>
                <div class="signal-val" style="color:#1D9E75">Forte (>55)</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">W1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:30%;background:#EF9F27"></div></div>
                <div class="signal-val" style="color:#EF9F27">Pullback ↓</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">D1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:25%;background:#E8593C"></div></div>
                <div class="signal-val" style="color:#E8593C">Fundo canal</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">H4</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:45%;background:#3B8BD4"></div></div>
                <div class="signal-val" style="color:#3B8BD4">↑ virando</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="rule-card">
            <div class="rule-title" style="color:#E8593C">🔴 Configuração de VENDA</div>
            <div class="signal-row">
                <div class="signal-tf">MN</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:30%;background:#E8593C"></div></div>
                <div class="signal-val" style="color:#E8593C">Fraco (<40)</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">W1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:70%;background:#EF9F27"></div></div>
                <div class="signal-val" style="color:#EF9F27">Pullback ↑</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">D1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:78%;background:#EF9F27"></div></div>
                <div class="signal-val" style="color:#EF9F27">Topo canal</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">H4</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:55%;background:#3B8BD4"></div></div>
                <div class="signal-val" style="color:#3B8BD4">↓ virando</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="rule-card" style="border-color: #da3633;">
        <div class="rule-title"><span class="rule-badge">REGRAS ABSOLUTAS</span></div>
        <div class="rule-body">
            • <b>NUNCA</b> operar contra a tendência do timeframe maior.<br>
            • <b>NUNCA</b> operar se o RSI estiver no meio do canal (aguarde os extremos).<br>
            • <b>NUNCA</b> arriscar mais de 3% da sua banca em uma única operação.<br>
            • <b>NUNCA</b> entrar em uma operação que não ofereça um R:R mínimo de 1:5.
        </div>
    </div>
    """, unsafe_allow_html=True)
