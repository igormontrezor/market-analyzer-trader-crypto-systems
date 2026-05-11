import streamlit as st
import plotly.graph_objects as go
import numpy as np

# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="MONTREZOR - Trading System",
    layout="wide",
    page_icon="📊"
)

# ============================================================
# 2. SESSION STATES
# ============================================================
if 'step_active' not in st.session_state:
    st.session_state.step_active = 0
if 'entrada_active' not in st.session_state:
    st.session_state.entrada_active = "A+"
if 'simular_stoch' not in st.session_state:
    st.session_state.simular_stoch = False
if 'hougaard_step' not in st.session_state:
    st.session_state.hougaard_step = -1
if 'checklist_vals' not in st.session_state:
    st.session_state.checklist_vals = [False] * 7

# ============================================================
# 3. CSS CUSTOMIZADO
# ============================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');

    .block-container { padding-top: 2rem; max-width: 95%; }
    [data-testid="stAppViewContainer"] { background-color: #0b0e11; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #30363d; }
    .stTabs [data-baseweb="tab"] { padding: 10px 20px; color: #8b949e; border-radius: 4px 4px 0 0; }
    .stTabs [aria-selected="true"] {
        color: #58a6ff !important;
        border-bottom: 2px solid #58a6ff !important;
        background-color: #161b22;
    }

    /* Cards gerais */
    .rule-card {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 16px; margin-bottom: 15px;
    }
    .rule-title {
        color: #c9d1d9; font-size: 16px; font-weight: bold;
        margin-bottom: 10px; display: flex; align-items: center; gap: 10px;
    }
    .rule-badge { background: #da3633; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
    .rule-body { color: #8b949e; font-size: 14px; line-height: 1.6; }

    .info-box {
        background-color: #1c2128; border-left: 4px solid #3B8BD4;
        padding: 15px; border-radius: 4px; color: #c9d1d9;
        font-size: 14px; margin-bottom: 20px;
    }

    /* TF Cards */
    .tf-card {
        background: #0d1117; border: 1px solid #30363d;
        border-radius: 8px; padding: 15px; text-align: center;
    }
    .tf-label { color: #8b949e; font-size: 12px; font-weight: bold; }
    .tf-val { font-size: 20px; font-weight: bold; margin: 5px 0; }
    .tf-desc { color: #484f58; font-size: 11px; }

    /* Edge signal bars */
    .signal-row { display: flex; align-items: center; gap: 15px; margin-bottom: 12px; }
    .signal-tf { color: #8b949e; font-weight: bold; width: 40px; }
    .signal-bar-wrap { flex: 1; height: 10px; background: #30363d; border-radius: 5px; overflow: hidden; }
    .signal-bar { height: 100%; border-radius: 5px; }
    .signal-val { width: 80px; text-align: right; font-size: 13px; font-weight: bold; }

    /* Checklists */
    .static-check {
        display: flex; align-items: center; gap: 10px; padding: 8px;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 6px; margin-bottom: 8px; color: #c9d1d9; font-size: 14px;
    }
    .static-check.checked { border-color: #1D9E75; }
    .static-check.warning { border-color: #EF9F27; }

    /* ── MÉTODO HOUGAARD ── */
    .dark-wrap {
        background: #0E0E0E; border-radius: 12px; padding: 2rem;
        font-family: 'IBM Plex Mono', monospace;
        border: 1px solid #1e1e1e;
    }
    .titulo-doc {
        font-family: 'Libre Baskerville', serif; font-size: 22px;
        font-weight: 700; color: #F0EDE6; margin-bottom: 4px; letter-spacing: -0.5px;
    }
    .subtitulo-doc {
        font-size: 10px; color: #555; letter-spacing: 3px;
        text-transform: uppercase; margin-bottom: 2rem;
    }
    .secao { margin-bottom: 2rem; }
    .secao-label {
        font-size: 10px; letter-spacing: 3px; text-transform: uppercase;
        color: #555; margin-bottom: 1rem; padding-bottom: 6px; border-bottom: 0.5px solid #222;
    }
    .passo {
        display: grid; grid-template-columns: 28px 1fr; gap: 12px;
        align-items: start; padding: 12px 0; border-bottom: 0.5px solid #1C1C1C;
    }
    .passo:last-child { border-bottom: none; }
    .num { font-size: 11px; font-weight: 500; color: #444; padding-top: 2px; }
    .passo-etapa { font-size: 13px; font-weight: 500; color: #D4CFC7; margin-bottom: 3px; }
    .passo-pensamento { font-size: 12px; color: #666; font-style: italic; margin-bottom: 5px; }
    .passo-acao { font-size: 12px; color: #7A7570; line-height: 1.7; }
    .tag {
        display: inline-block; font-size: 10px; padding: 2px 7px;
        border-radius: 3px; margin-right: 6px; margin-top: 6px; letter-spacing: 0.5px;
    }
    .tag-risco { background: #2A1E0A; color: #C98A2A; }
    .tag-psico { background: #1A1730; color: #8B7FD4; }
    .tag-acao { background: #0C1F18; color: #3D9E75; }
    .tag-sair { background: #1F0C0C; color: #C04040; }

    .pilar-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
    .pilar-card {
        background: #141414; border: 0.5px solid #222;
        border-radius: 8px; padding: 14px;
    }
    .pilar-icon { font-size: 18px; margin-bottom: 8px; color: #444; }
    .pilar-titulo {
        font-size: 11px; font-weight: 500; color: #C0BBB3;
        margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px;
    }
    .pilar-desc { font-size: 11px; color: #666; line-height: 1.6; }

    .alerta {
        background: #141414; border-left: 2px solid #333;
        padding: 12px 16px; border-radius: 0 8px 8px 0;
    }
    .alerta-texto {
        font-size: 12px; color: #888; line-height: 1.8;
        font-family: 'Libre Baskerville', serif; font-style: italic;
    }

    /* Simulador Hougaard */
    .sim { background: #0E0E0E; padding: 1.5rem 0; font-family: 'IBM Plex Mono', monospace; }
    .info-box-sim {
        background: #141414; border: 0.5px solid #222;
        border-radius: 8px; padding: 14px 16px;
        display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;
        margin-top: 1rem;
    }
    .info-item-sim { }
    .info-label-sim {
        font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
        color: #444; margin-bottom: 4px; font-family: 'IBM Plex Mono', monospace;
    }
    .info-val-sim { font-size: 14px; font-weight: 500; color: #D4CFC7; font-family: 'IBM Plex Mono', monospace; }
    .info-val-sim.green { color: #3D9E75; }
    .info-val-sim.red { color: #C04040; }
    .info-val-sim.amber { color: #C98A2A; }

    .narrative-sim {
        margin-top: 1rem; background: #141414;
        border-left: 2px solid #333; padding: 10px 14px; border-radius: 0 6px 6px 0;
    }
    .nar-step-sim {
        font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
        color: #555; margin-bottom: 4px; font-family: 'IBM Plex Mono', monospace;
    }
    .nar-text-sim {
        font-size: 12px; color: #888; line-height: 1.7;
        font-style: italic; font-family: 'IBM Plex Mono', monospace;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 4. ESTILO CSS PADRÃO
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
[data-testid="stAppViewContainer"]  { background:#070B0F; }
[data-testid="stSidebar"]           { background:#0D1117; border-right:1px solid #21262D; }
[data-testid="stSidebar"] *         { font-family:'JetBrains Mono',monospace !important; font-size:12px; }
h1,h2,h3                            { font-family:'JetBrains Mono',monospace !important; }
.sec { font-size:10px; letter-spacing:2px; color:#484F58; text-transform:uppercase;
       border-bottom:1px solid #21262D; padding-bottom:4px; margin:12px 0 8px; }
.stButton>button { background:#161B22 !important; border:1px solid #30363D !important;
  color:#C9D1D9 !important; border-radius:6px !important; }
.stButton>button:hover { border-color:#58A6FF !important; color:#58A6FF !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 5. CABEÇALHO
# ============================================================
st.title("Montrezor Trading System")
st.markdown(
    "<p style='color:#8b949e;margin-top:-15px;margin-bottom:30px;'>"
    "Método interativo passo a passo para execução de alta performance.</p>",
    unsafe_allow_html=True
)

# ============================================================
# 5. NAVEGAÇÃO PRINCIPAL (TABS)
# ============================================================
(tab_visao, tab_rsi, tab_stoch, tab_entradas,
 tab_checklist, tab_edge, tab_hougaard, tab_sim) = st.tabs([
    "👁️ Visão Geral",
    "📈 Canal RSI",
    "📉 Stoch RSI",
    "🎯 Entradas",
    "✅ Checklist",
    "⚡ Edge do Sistema",
    "📋 Método Hougaard",
    "🔬 Simulador Hougaard",
])

# ============================================================
# TAB 1 — VISÃO GERAL
# ============================================================
with tab_visao:
    st.markdown(
        '<div class="info-box">O método opera no alinhamento de timeframes maiores com execução refinada '
        'nos menores. Siga a ordem rigorosamente.</div>',
        unsafe_allow_html=True
    )

    steps = [
        {
            "title": "1. Identificar tendência",
            "desc": "Supertrend + direção no timeframe maior. Nunca operar contra a tendência.",
            "detail": (
                "Identifique a tendência principal usando o Supertrend no timeframe maior (semanal/mensal). "
                "A tendência é o maior peso do sistema — nunca opere contra ela."
            ),
        },
        {
            "title": "2. Canal RSI no TF maior",
            "desc": "RSI no suporte/resistência do canal. Peso maior para semanal e mensal.",
            "detail": (
                "Aguarde o RSI atingir o suporte ou resistência do canal de tendência no semanal/mensal. "
                "Peso maior para timeframes maiores. Não entre no meio do canal."
            ),
        },
        {
            "title": "3. Stoch RSI no TF menor",
            "desc": "Stochastic RSI no contra-fundo/topo — inverso da tendência nos TFs menores.",
            "detail": (
                "Com o RSI no canal do TF maior, aguarde o Stochastic RSI no fundo (para compras) ou "
                "no topo (para vendas) no timeframe menor (4H ou D1). É a confirmação do pullback."
            ),
        },
        {
            "title": "4. Fibo + R:R mín 1:5",
            "desc": "0.5–0.618 tocado. Take profit na extensão 0.618 (A+) ou 0.328 (A/B).",
            "detail": (
                "Verifique se o Fibonacci 0.5–0.618 foi tocado. O take profit alvo é a extensão "
                "0.618 (entrada A+) ou 0.328 (entrada A/B). R:R mínimo obrigatório de 1:5."
            ),
        },
        {
            "title": "5. Executar entrada",
            "desc": "Inversão do Supertrend. Stop no extremo do canal RSI. Máx 3% risco.",
            "detail": (
                "Com todos os filtros alinhados, execute a entrada na inversão do Supertrend. "
                "Stop loss no extremo do canal RSI, nas médias móveis 50/100/200 ou na extensão Fibonacci."
            ),
        },
        {
            "title": "6. Gerenciar saída",
            "desc": "Take profits via Fibo/Neuro Athena. Alerta RSI + Stoch em direções opostas.",
            "detail": (
                "Use o Método Hougaard para saídas parciais. Alertas de saída: RSI seguindo a tendência "
                "em uma direção e Stochastic na direção oposta nos TFs maiores (W/MN)."
            ),
        },
    ]

    cols = st.columns(3)
    for i, step in enumerate(steps):
        with cols[i % 3]:
            btn_type = "primary" if st.session_state.step_active == i else "secondary"
            if st.button(
                f"{step['title']}\n\n{step['desc']}",
                key=f"step_{i}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state.step_active = i
                st.rerun()

    st.markdown("---")
    st.markdown(f"### Detalhe do Passo {st.session_state.step_active + 1}")
    st.info(steps[st.session_state.step_active]["detail"])

# ============================================================
# TAB 2 — CANAL RSI
# ============================================================
with tab_rsi:
    st.markdown(
        '<div class="info-box">O canal do RSI é a base do sistema. O preço precisa estar no suporte '
        'ou resistência do canal para acionar uma entrada válida.</div>',
        unsafe_allow_html=True
    )

    np.random.seed(42)
    x_rsi = list(range(50))
    y_rsi = np.cumsum(np.random.randn(50) * 3) + 50
    y_rsi = np.clip(y_rsi, 20, 80)

    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=x_rsi, y=y_rsi, name="RSI", line=dict(color="#3B8BD4", width=2)))
    fig_rsi.add_trace(go.Scatter(x=x_rsi, y=[72] * 50, name="Resistência", line=dict(color="#1D9E75", width=1, dash="dash")))
    fig_rsi.add_trace(go.Scatter(x=x_rsi, y=[28] * 50, name="Suporte", line=dict(color="#E8593C", width=1, dash="dash")))
    fig_rsi.update_layout(
        template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0),
        title="CANAL RSI — SEMANAL (Simulado)",
        yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.1)"),
        xaxis=dict(showgrid=False, showticklabels=False),
    )
    st.plotly_chart(fig_rsi, use_container_width=True)

    st.markdown("""
    <div class="rule-card">
        <div class="rule-title"><span class="rule-badge">REGRA PRINCIPAL</span> Exemplo tendência global COMPRA</div>
        <div class="rule-body">
            Quando o RSI toca o <b>fundo do canal de tendência</b> (no semanal/diario/4hs), aguarde o
            Stochastic RSI confirmar nos timeframes menores (Reversao para a tendencia principal no 4hs).<br><br>
            <b style="color:#f85149;">Nunca operar contra a tendência.</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="tf-card"><div class="tf-label">MN</div><div class="tf-val" style="color:#1D9E75">+ 65</div><div class="tf-desc">forte — acima 50</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="tf-card"><div class="tf-label">W1</div><div class="tf-val" style="color:#1D9E75">+ 52</div><div class="tf-desc">pullback no fundo</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="tf-card"><div class="tf-label">D1</div><div class="tf-val" style="color:#EF9F27">≈ 35</div><div class="tf-desc">fundo do canal</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="tf-card"><div class="tf-label">H4</div><div class="tf-val" style="color:#3B8BD4">RSI tocando canal + STCRSI ↑ virando</div><div class="tf-desc">execução</div></div>', unsafe_allow_html=True)

# ============================================================
# TAB 3 — STOCH RSI
# ============================================================
with tab_stoch:
    st.markdown(
        '<div class="info-box">O Stochastic RSI confirma a entrada nos timeframes menores, sempre na direção '
        '<i>inversa</i> à tendência (fundo/topo do Stoch no TF menor).</div>',
        unsafe_allow_html=True
    )

    np.random.seed(10)
    x_stoch = list(range(60))
    k_line = np.cumsum(np.random.randn(60) * 8) + 50
    k_line = np.clip(k_line, 5, 95)

    if st.session_state.simular_stoch:
        k_line[-5:] = [30, 20, 10, 8, 25]

    d_line = [k_line[0]]
    for i in range(1, len(k_line)):
        d_line.append(d_line[-1] * 0.7 + k_line[i] * 0.3)

    fig_stoch = go.Figure()
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=k_line, name="%K", line=dict(color="#9F77DD", width=2)))
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=d_line, name="%D", line=dict(color="#5DCAA5", width=2)))
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=[80] * 60, name="Overbought", line=dict(color="#E8593C", width=1, dash="dash")))
    fig_stoch.add_trace(go.Scatter(x=x_stoch, y=[20] * 60, name="Oversold", line=dict(color="#3B8BD4", width=1, dash="dash")))
    fig_stoch.update_layout(
        template="plotly_dark", height=300, margin=dict(l=0, r=0, t=30, b=0),
        title="STOCHASTIC RSI — 4H (Simulado)",
        yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.1)"),
        xaxis=dict(showgrid=False, showticklabels=False),
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
    <div class="rule-card" style="margin-top:15px;">
        <div class="rule-title">Lógica de confirmação</div>
        <div class="rule-body">
            <b>Compra:</b> Tendência mensal/semanal de alta → RSI tocar fundo do canal 1W/D1/4H no (oversold)
            → entrada quando stochastico RSI 4H virar para cima.<br><br>
            <b>Venda:</b> Tendência mensal/semanal de baixa → RSI tocar topo do canal 1W/D1/4H no (overbought)
            → entrada quando stochastico RSI 4H virar para baixo.<br><br>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# TAB 4 — ENTRADAS
# ============================================================
with tab_entradas:
    st.markdown(
        '<div class="info-box">Existem três tipos de entrada, ordenadas por qualidade. Selecione para ver os critérios.</div>',
        unsafe_allow_html=True
    )

    tipo_entrada = st.radio(
        "Selecione o Setup:",
        ["A+ (Melhor Setup)", "A (Principal)", "B (Proteção)"],
        horizontal=True,
    )

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

# ============================================================
# TAB 5 — CHECKLIST
# ============================================================
with tab_checklist:
    st.markdown(
        '<div class="info-box">Marque cada critério antes de entrar. O score mostra a qualidade do setup em tempo real.</div>',
        unsafe_allow_html=True
    )

    crit = [
        "Supertrend alinhado com tendência maior (Verificar no semanal/mensal)",
        "Tendência semanal confirmada (MN + W1 na mesma direção)",
        "RSI no canal — suporte ou resistência (Peso maior para W1/MN)",
        "Stoch RSI no fundo/topo no TF menor (inverso no 4H ou D1)",
        "Fibonacci 0.5–0.618 tocado (Neuro Athena ou manual)",
        "R:R mínimo 1:5 calculado (Stop técnico posicionado)",
        "Risco máx 3% da conta definido (Tamanho da posição calculado)",
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
        st.markdown(
            f"<h3 style='text-align:right;margin-top:-10px;color:#58a6ff;'>{score} / 7</h3>",
            unsafe_allow_html=True,
        )

# ============================================================
# TAB 6 — EDGE DO SISTEMA
# ============================================================
with tab_edge:
    st.markdown(
        '<div class="info-box">O sistema funciona pela hierarquia de timeframes: o maior manda, o menor executa.</div>',
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="rule-card">
            <div class="rule-title" style="color:#1D9E75">🟢 Configuração de COMPRA</div>
            <div class="signal-row">
                <div class="signal-tf">MN</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:75%;background:#1D9E75"></div></div>
                <div class="signal-val" style="color:#1D9E75">Forte (&gt;55)</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">W1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:52%;background:#1D9E75"></div></div>
                <div class="signal-val" style="color:#1D9E75">Fundo canal</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">D1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:35%;background:#E8593C"></div></div>
                <div class="signal-val" style="color:#E8593C">Fundo canal</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">H4</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:30%;background:#E8593C"></div></div>
                <div class="signal-val" style="color:#E8593C">↑ virando</div>
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
                <div class="signal-val" style="color:#E8593C">Fraco (&lt;40)</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">W1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:48%;background:#E8593C"></div></div>
                <div class="signal-val" style="color:#E8593C">Topo canal</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">D1</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:60%;background:#1D9E75"></div></div>
                <div class="signal-val" style="color:#1D9E75">Topo canal</div>
            </div>
            <div class="signal-row">
                <div class="signal-tf">H4</div>
                <div class="signal-bar-wrap"><div class="signal-bar" style="width:70%;background:#1D9E75"></div></div>
                <div class="signal-val" style="color:#1D9E75">↓ virando</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="rule-card" style="border-color:#da3633;">
        <div class="rule-title"><span class="rule-badge">REGRAS ABSOLUTAS</span></div>
        <div class="rule-body">
            • <b>NUNCA</b> operar contra a tendência do timeframe maior.<br>
            • <b>NUNCA</b> operar se o RSI estiver no meio do canal (aguarde os extremos).<br>
            • <b>NUNCA</b> arriscar mais de 3% da sua banca em uma única operação.<br>
            • <b>NUNCA</b> entrar em uma operação que não ofereça um R:R mínimo de 1:5.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# TAB 7 — MÉTODO HOUGAARD (referência completa)
# ============================================================
with tab_hougaard:
    st.markdown("""
<div class="dark-wrap">
<div class="titulo-doc">Método Hougaard</div>
<div class="subtitulo-doc">Breakeven + Pirâmide · Checklist operacional</div>

<div class="secao">
<div class="secao-label">Os três pilares</div>
<div class="pilar-grid">
<div class="pilar-card">
<div class="pilar-icon">🛡️</div>
<div class="pilar-titulo">Proteção</div>
<div class="pilar-desc">Mover para BE elimina risco financeiro da unidade inicial.</div>
</div>
<div class="pilar-card">
<div class="pilar-icon">📈</div>
<div class="pilar-titulo">Pirâmide</div>
<div class="pilar-desc">Com a base protegida, adiciona contratos ao que já funciona.</div>
</div>
<div class="pilar-card">
<div class="pilar-icon">✂️</div>
<div class="pilar-titulo">Corte rápido</div>
<div class="pilar-desc">Se o mercado volta ao BE, sai sem hesitar. Tese falhou no timing.</div>
</div>
</div>
</div>

<div class="secao">
<div class="secao-label">Passo a passo</div>

<div class="passo">
<div class="num">01</div>
<div>
<div class="passo-etapa">Entrada inicial</div>
<div class="passo-pensamento">'Estou testando uma ideia.'</div>
<div class="passo-acao">Tamanho de posição controlado. Risco definido antes de entrar. Esta é apenas a sonda — não o bet principal.</div>
<span class="tag tag-risco">risco fixo</span>
</div>
</div>

<div class="passo">
<div class="num">02</div>
<div>
<div class="passo-etapa">Mercado anda a favor</div>
<div class="passo-pensamento">'Talvez eu esteja certo.'</div>
<div class="passo-acao">Observar confirmação de momentum. Aguardar distância suficiente baseada em volatilidade ou nível técnico próximo. Não agir ainda.</div>
<span class="tag tag-psico">paciência</span>
</div>
</div>

<div class="passo">
<div class="num">03</div>
<div>
<div class="passo-etapa">Mover stop para breakeven</div>
<div class="passo-pensamento">'Agora posso pressionar.'</div>
<div class="passo-acao">Stop da posição 1 vai para o preço de entrada. A operação agora é de risco zero. Este é o gatilho que libera o próximo passo — não apenas proteção de ego.</div>
<span class="tag tag-acao">stop → entrada</span><span class="tag tag-psico">risco liberado</span>
</div>
</div>

<div class="passo">
<div class="num">04</div>
<div>
<div class="passo-etapa">Adicionar posição (piramidagem)</div>
<div class="passo-pensamento">'Vou aumentar no que funciona.'</div>
<div class="passo-acao">Abre posição 2. O stop combinado é gerenciado de forma que, se o mercado reverter, o lucro da P1 no BE compensa a perda da P2. Nunca adicionar em operação perdendo.</div>
<span class="tag tag-acao">posição 2 aberta</span><span class="tag tag-risco">stop combinado</span>
</div>
</div>

<div class="passo">
<div class="num">05</div>
<div>
<div class="passo-etapa">Mercado continua — maximizar assimetria</div>
<div class="passo-pensamento">'Maximizar assimetria.'</div>
<div class="passo-acao">Deixar os vencedores correr. Subir stops progressivamente conforme o mercado avança. Repetir o ciclo para posição 3 se as condições permitirem.</div>
<span class="tag tag-acao">trailing stop</span><span class="tag tag-psico">desconforto produtivo</span>
</div>
</div>

<div class="passo">
<div class="num">06</div>
<div>
<div class="passo-etapa">Reversão ao breakeven — sair</div>
<div class="passo-pensamento">'A tese falhou no timing.'</div>
<div class="passo-acao">Sem hesitação, sem esperança. O retorno ao BE é sinal de que o setup não se desenvolveu como esperado. Fechar tudo. Preservar capital mental para a próxima.</div>
<span class="tag tag-sair">saída imediata</span><span class="tag tag-psico">zero ego</span>
</div>
</div>
</div>

<div class="secao">
<div class="secao-label">A frase</div>
<div class="alerta">
<div class="alerta-texto">'Pessoas normais buscam conforto. Traders de sucesso buscam desconforto. Mover para o breakeven é o primeiro passo para poder dobrar a aposta.'</div>
<div style="font-size:11px;color:#444;margin-top:8px;">— Tom Hougaard</div>
</div>
</div>

<div class="secao">
<div class="secao-label">Armadilhas documentadas</div>

<div class="passo">
<div class="num">⚠️</div>
<div>
<div class="passo-etapa">Stop cedo demais</div>
<div class="passo-acao">Mover para BE antes da distância necessária expõe a operação ao ruído normal do mercado. Você sai antes do movimento real acontecer.</div>
</div>
</div>

<div class="passo">
<div class="num">⚠️</div>
<div>
<div class="passo-etapa">BE como muleta emocional</div>
<div class="passo-acao">Usar o BE apenas para 'não perder o que ganhou' é viés de aversão à perda disfarçado. Para Hougaard, o BE é ferramenta de expansão — não de conforto.</div>
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# TAB 8 — SIMULADOR HOUGAARD
# ============================================================
with tab_sim:
    st.markdown(
        '<div class="info-box">Pressione <b>Próximo passo</b> para avançar pela simulação interativa da técnica de Breakeven + Piramidagem de Tom Hougaard.</div>',
        unsafe_allow_html=True
    )

    # Dados de cada passo do simulador
    HOUGAARD_STEPS = [
        {
            "label": "01 · entrada inicial",
            "text": '"Estou testando uma ideia." — Entrada em 100. Stop em 94. Risco definido: 6 pontos por contrato.',
            "price_end": 7,
            "stop_line": 94,
            "be_line": None,
            "p2_line": None,
            "pnl": None,
            "pnl_color": None,
            "stop": "94.00",
            "pos": "1 contrato",
        },
        {
            "label": "02 · mercado anda a favor",
            "text": '"Talvez eu esteja certo." — Preço sobe para 107. Momentum confirmado. Ainda não agir.',
            "price_end": 14,
            "stop_line": 94,
            "be_line": None,
            "p2_line": None,
            "pnl": "+7.00",
            "pnl_color": "green",
            "stop": "94.00",
            "pos": "1 contrato",
        },
        {
            "label": "03 · mover stop para BE",
            "text": '"Agora posso pressionar." — Stop sobe para 100 (preço de entrada). Risco eliminado. Posição 1 está segura.',
            "price_end": 14,
            "stop_line": 100,
            "be_line": 100,
            "p2_line": None,
            "pnl": "+7.00",
            "pnl_color": "green",
            "stop": "100.00 (BE)",
            "pos": "1 contrato",
        },
        {
            "label": "04 · adicionar posição",
            "text": '"Vou aumentar no que funciona." — Abre P2 em 107. Stop combinado ajustado: se mercado voltar ao BE, P1 fecha zerado e P2 fecha com pequena perda controlada.',
            "price_end": 14,
            "stop_line": 100,
            "be_line": 100,
            "p2_line": 107,
            "pnl": "+7.00",
            "pnl_color": "green",
            "stop": "100.00",
            "pos": "2 contratos",
        },
        {
            "label": "05 · mercado continua — maximizar",
            "text": '"Maximizar assimetria." — Preço avança para 118. Stop sobe junto. P&L combinado: +25 pontos. Trailing stop protegendo ganhos.',
            "price_end": 25,
            "stop_line": 108,
            "be_line": 100,
            "p2_line": 107,
            "pnl": "+25.00",
            "pnl_color": "green",
            "stop": "108.00",
            "pos": "2 contratos",
        },
        {
            "label": "06 · saída no stop",
            "text": '"A tese falhou no timing." — Preço recua e aciona o stop em 108. Saída sem hesitar. Capital mental preservado para a próxima operação.',
            "price_end": 11,
            "stop_line": 108,
            "be_line": 100,
            "p2_line": 107,
            "pnl": "+19.00",
            "pnl_color": "green",
            "stop": "acionado 108",
            "pos": "fechado",
        },
    ]

    total_bars = 22
    price_base = 100

    def build_price_sim(step_idx: int) -> list:
        s = HOUGAARD_STEPS[step_idx]
        prices = []
        for i in range(total_bars):
            t = i / (total_bars - 1)
            noise = np.sin(i * 2.3) * 0.8 + np.cos(i * 1.1) * 0.5
            trend = s["price_end"] * t
            prices.append(round(price_base + trend + noise, 2))
        return prices

    def build_hline(val, length: int) -> list:
        return [val] * length if val is not None else [None] * length

    # Controles de navegação
    col_prev, col_next, col_reset, col_counter = st.columns([1, 1, 1, 3])
    with col_prev:
        if st.button("◀ Anterior", key="hougaard_prev", use_container_width=True):
            if st.session_state.hougaard_step > -1:
                st.session_state.hougaard_step -= 1
            st.rerun()
    with col_next:
        if st.button("Próximo ▶", key="hougaard_next", type="primary", use_container_width=True):
            if st.session_state.hougaard_step < len(HOUGAARD_STEPS) - 1:
                st.session_state.hougaard_step += 1
            st.rerun()
    with col_reset:
        if st.button("↺ Reiniciar", key="hougaard_reset", use_container_width=True):
            st.session_state.hougaard_step = -1
            st.rerun()
    with col_counter:
        current_display = max(st.session_state.hougaard_step + 1, 0)
        st.markdown(
            f"<p style='text-align:right;color:#555;font-family:monospace;margin-top:8px;'>"
            f"{current_display} / {len(HOUGAARD_STEPS)}</p>",
            unsafe_allow_html=True,
        )

    # Gráfico do simulador
    fig_sim = go.Figure()

    if st.session_state.hougaard_step >= 0:
        s = HOUGAARD_STEPS[st.session_state.hougaard_step]
        x_sim = list(range(total_bars))
        price_data = build_price_sim(st.session_state.hougaard_step)

        fig_sim.add_trace(go.Scatter(
            x=x_sim, y=price_data, name="Preço",
            line=dict(color="#3D9E75", width=2), mode="lines",
        ))
        fig_sim.add_trace(go.Scatter(
            x=x_sim, y=build_hline(s["stop_line"], total_bars), name="Stop",
            line=dict(color="#C04040", width=1.5, dash="dash"),
        ))
        fig_sim.add_trace(go.Scatter(
            x=x_sim, y=build_hline(s["be_line"], total_bars), name="Breakeven",
            line=dict(color="#C98A2A", width=1, dash="dot"),
        ))
        fig_sim.add_trace(go.Scatter(
            x=x_sim, y=build_hline(s["p2_line"], total_bars), name="Entrada P2",
            line=dict(color="#8B7FD4", width=1, dash="dot"),
        ))

        # Painel de informações
        pnl_color_map = {"green": "#3D9E75", "red": "#C04040", "amber": "#C98A2A", None: "#D4CFC7"}
        pnl_color = pnl_color_map.get(s["pnl_color"], "#D4CFC7")

        c1, c2, c3 = st.columns(3)
        c1.metric("P&L Total", s["pnl"] or "—")
        c2.metric("Stop Ativo", s["stop"])
        c3.metric("Posições", s["pos"])

        # Narrativa
        st.markdown(
            f'<div class="narrative-sim">'
            f'<div class="nar-step-sim">{s["label"]}</div>'
            f'<div class="nar-text-sim">{s["text"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        # Estado inicial — gráfico vazio com instrução
        fig_sim.add_annotation(
            text="Pressione 'Próximo ▶' para iniciar a simulação",
            xref="paper", yref="paper", x=0.5, y=0.5,
            font=dict(size=14, color="#555"),
            showarrow=False,
        )
        st.markdown(
            '<div class="narrative-sim">'
            '<div class="nar-step-sim">aguardando</div>'
            '<div class="nar-text-sim">Pressione "Próximo ▶" para iniciar a simulação.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    fig_sim.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=0, r=0, t=20, b=0),
        yaxis=dict(range=[88, 125], gridcolor="rgba(255,255,255,0.06)"),
        xaxis=dict(showgrid=False, showticklabels=False),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#666"),
        ),
    )
    st.plotly_chart(fig_sim, use_container_width=True)

    # Legenda visual extra
    st.markdown("""
    <div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:4px;">
      <span style="font-size:11px;color:#666;font-family:monospace;">
        <span style="color:#3D9E75">──</span> preço
      </span>
      <span style="font-size:11px;color:#666;font-family:monospace;">
        <span style="color:#C04040">- -</span> stop loss
      </span>
      <span style="font-size:11px;color:#666;font-family:monospace;">
        <span style="color:#C98A2A">· ·</span> breakeven
      </span>
      <span style="font-size:11px;color:#666;font-family:monospace;">
        <span style="color:#8B7FD4">· ·</span> entrada P2
      </span>
    </div>
    <br><p style='text-align: center; color: #484f58; font-size: 12px;'>Montrezor Analysis System | Powered by Igor Montrezor</p>
    """, unsafe_allow_html=True)
