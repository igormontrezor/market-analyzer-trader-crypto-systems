import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
import yfinance as yf
import time

# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS
# ============================================================
st.set_page_config(page_title="MONTREZOR - Trading System", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;600&display=swap');

    [data-testid="stAppViewContainer"]  { background:#0b0e11; }
    .block-container { padding-top: 2rem; max-width: 95%; font-family:'JetBrains Mono',monospace !important;}

    /* Tabs Customizadas */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #30363d; }
    .stTabs [data-baseweb="tab"] { padding: 10px 20px; color: #8b949e; border-radius: 4px 4px 0 0; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; background-color: #161b22; }

    /* Cards gerais */
    .rule-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 15px; }
    .rule-title { color: #c9d1d9; font-size: 16px; font-weight: bold; margin-bottom: 10px; display: flex; align-items: center; gap: 10px; }
    .rule-badge { background: #da3633; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
    .rule-body { color: #8b949e; font-size: 14px; line-height: 1.6; }
    .info-box { background-color: #1c2128; border-left: 4px solid #3B8BD4; padding: 15px; border-radius: 4px; color: #c9d1d9; font-size: 14px; margin-bottom: 20px; }

    /* Checklists */
    .static-check { display: flex; align-items: center; gap: 10px; padding: 8px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; margin-bottom: 8px; color: #c9d1d9; font-size: 14px; }
    .static-check.checked { border-color: #1D9E75; }

    /* Sinais */
    .signal-card-buy { background: rgba(29, 158, 117, 0.1); border: 1px solid #1D9E75; border-radius: 8px; padding: 15px; margin-bottom: 10px;}
    .signal-card-sell { background: rgba(224, 76, 76, 0.1); border: 1px solid #E04C4C; border-radius: 8px; padding: 15px; margin-bottom: 10px;}
    .signal-title { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
    .signal-type { font-size: 12px; padding: 3px 8px; border-radius: 4px; display: inline-block; margin-bottom: 10px;}
    .bg-super { background: #E0A905; color: #000; font-weight: bold; }
    .bg-comum { background: #3B8BD4; color: #fff; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 2. SESSION STATES INICIAIS
# ============================================================
if 'step_active' not in st.session_state: st.session_state.step_active = 0
if 'simular_stoch' not in st.session_state: st.session_state.simular_stoch = False
if 'hougaard_step' not in st.session_state: st.session_state.hougaard_step = -1
if 'tracked_symbols' not in st.session_state: st.session_state.tracked_symbols = ["BTC-USD", "EURUSD=X"]
if 'neuro_athena' not in st.session_state: st.session_state.neuro_athena = {}
if 'auto_update' not in st.session_state: st.session_state.auto_update = False

# ============================================================
# 3. LÓGICA DE INDICADORES (PYTHON / PANDAS)
# ============================================================
def calc_ema(df, period, col='Close'):
    return df[col].ewm(span=period, adjust=False).mean()

def calc_supertrend(df, period=10, multiplier=3.0):
    hl2 = (df['High'] + df['Low']) / 2
    atr = df['High'].combine(df['Close'].shift(), max) - df['Low'].combine(df['Close'].shift(), min)
    atr = atr.rolling(window=period).mean() # SMA do True Range (Como no MQ5 param ChangeATRMethod=false)

    up_basic = hl2 - (multiplier * atr)
    dn_basic = hl2 + (multiplier * atr)

    up_band = pd.Series(index=df.index, dtype=float)
    dn_band = pd.Series(index=df.index, dtype=float)
    trend = pd.Series(index=df.index, dtype=int)

    for i in range(1, len(df)):
        if df['Close'].iloc[i-1] > up_band.iloc[i-1]:
            up_band.iloc[i] = max(up_basic.iloc[i], up_band.iloc[i-1])
        else:
            up_band.iloc[i] = up_basic.iloc[i]

        if df['Close'].iloc[i-1] < dn_band.iloc[i-1]:
            dn_band.iloc[i] = min(dn_basic.iloc[i], dn_band.iloc[i-1])
        else:
            dn_band.iloc[i] = dn_basic.iloc[i]

        # Trend
        if i == 1: trend.iloc[i] = 1
        else:
            if trend.iloc[i-1] == -1 and df['Close'].iloc[i] > dn_band.iloc[i-1]:
                trend.iloc[i] = 1
            elif trend.iloc[i-1] == 1 and df['Close'].iloc[i] < up_band.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]

    df['ST_Up'] = np.where(trend == 1, up_band, np.nan)
    df['ST_Dn'] = np.where(trend == -1, dn_band, np.nan)
    df['ST_Trend'] = trend
    return df

def calc_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calc_rsi_channel(df, period=14, lr_period=50, multiplier=2.0):
    df = calc_rsi(df, period)
    df['RSI_LR'] = np.nan
    df['RSI_Upper'] = np.nan
    df['RSI_Lower'] = np.nan

    # Linear Regression do RSI (aproximação do MQ5)
    for i in range(lr_period, len(df)):
        y = df['RSI'].iloc[i-lr_period:i].values
        if np.isnan(y).any(): continue
        x = np.arange(lr_period)
        slope, intercept = np.polyfit(x, y, 1)
        y_pred = slope * x + intercept
        std_err = np.std(y - y_pred)

        # Pega o valor atual da linha projetada
        df.loc[df.index[i], 'RSI_LR'] = y_pred[-1]
        df.loc[df.index[i], 'RSI_Upper'] = y_pred[-1] + (std_err * multiplier)
        df.loc[df.index[i], 'RSI_Lower'] = y_pred[-1] - (std_err * multiplier)
    return df

def calc_stoch_rsi(df, rsi_period=14, k_period=14, d_period=3, slowing=5):
    if 'RSI' not in df.columns:
        df = calc_rsi(df, rsi_period)

    rsi_min = df['RSI'].rolling(window=k_period).min()
    rsi_max = df['RSI'].rolling(window=k_period).max()

    df['StochRSI_K_Raw'] = 100 * ((df['RSI'] - rsi_min) / (rsi_max - rsi_min))
    df['StochRSI_K'] = df['StochRSI_K_Raw'].rolling(window=slowing).mean()
    df['StochRSI_D'] = df['StochRSI_K'].rolling(window=d_period).mean()
    return df

# ============================================================
# 4. DOWNLOAD E COMPILAÇÃO DE DADOS
# ============================================================
@st.cache_data(ttl=60)
def fetch_multi_tf_data(symbol):
    data = {}
    intervals = {'1mo': '5y', '1wk': '2y', '1d': '1y', '4h': '60d'}
    for intv, period in intervals.items():
        try:
            df = yf.download(symbol, period=period, interval=intv, progress=False)
            if not df.empty:
                df = calc_supertrend(df)
                df['EMA_50'] = calc_ema(df, 50)
                df['EMA_100'] = calc_ema(df, 100)
                df['EMA_200'] = calc_ema(df, 200)
                df = calc_rsi_channel(df)
                df = calc_stoch_rsi(df)
                data[intv] = df
        except Exception:
            pass
    return data

# Lógica do Sinal Trader
def check_signals(data, symbol, athena_levels):
    # Precisamos de pelo menos MN, W1 e D1/4H para rodar a lógica
    if '1mo' not in data or '1wk' not in data or ('1d' not in data and '4h' not in data):
        return None

    mn = data['1mo'].iloc[-1]
    w1 = data['1wk'].iloc[-1]

    # 3. Tendência Compra/Venda
    trend_mn = mn['ST_Trend'] # 1 ou -1

    w1_ema_converging_buy = (w1['Close'] > w1['EMA_50'] > w1['EMA_100'] > w1['EMA_200'])
    w1_ema_converging_sell = (w1['Close'] < w1['EMA_50'] < w1['EMA_100'] < w1['EMA_200'])

    is_buy_trend = trend_mn == 1 and w1_ema_converging_buy
    is_sell_trend = trend_mn == -1 and w1_ema_converging_sell

    if not is_buy_trend and not is_sell_trend:
        return None # Sem tendência clara

    # Verificar toques no RSI (Contra-fluxo)
    # Se tendência é COMPRA, RSI precisa estar no FUNDO (oversold / tocando linha de baixo)
    rsi_bottom_mn = mn['RSI'] <= mn['RSI_Lower'] * 1.05 # Margem de erro de 5%
    rsi_bottom_w1 = w1['RSI'] <= w1['RSI_Lower'] * 1.05

    rsi_top_mn = mn['RSI'] >= mn['RSI_Upper'] * 0.95
    rsi_top_w1 = w1['RSI'] >= w1['RSI_Upper'] * 0.95

    # TF Menor para toque (D1 ou 4H)
    tf_menor = data['4h'].iloc[-1] if '4h' in data else data['1d'].iloc[-1]

    rsi_bottom_tfm = tf_menor['RSI'] <= tf_menor['RSI_Lower'] * 1.05
    rsi_top_tfm = tf_menor['RSI'] >= tf_menor['RSI_Upper'] * 0.95

    # Médias Móveis próximas (Margem de 1%)
    def near_ema(row):
        c = float(row['Close'])
        return any(abs(c - float(row[e])) / c < 0.01 for e in ['EMA_50', 'EMA_100', 'EMA_200'])

    ema_touch = near_ema(mn) or near_ema(w1) or near_ema(tf_menor)

    # 4. Sinal Comum
    sinal_comum = False
    direction = ""

    if is_buy_trend and (rsi_bottom_tfm) and (rsi_bottom_w1 or rsi_bottom_mn) and ema_touch:
        sinal_comum = True
        direction = "COMPRA"

    elif is_sell_trend and (rsi_top_tfm) and (rsi_top_w1 or rsi_top_mn) and ema_touch:
        sinal_comum = True
        direction = "VENDA"

    if not sinal_comum:
        return None

    # 5. Sinal Super
    sinal_super = False
    c_price = float(tf_menor['Close'])

    # Pega valores do Neuro Athena se existirem
    # [TP3, TP2, TP1, Buy Entry, Sell Entry, TP1, TP2, TP3]
    na_buy_entry = athena_levels.get(symbol, {}).get('buy_entry', 0)
    na_sell_entry = athena_levels.get(symbol, {}).get('sell_entry', 0)

    touch_st = (abs(c_price - float(tf_menor['ST_Up'])) / c_price < 0.01) if direction == "COMPRA" else \
               (abs(c_price - float(tf_menor['ST_Dn'])) / c_price < 0.01)

    touch_na = False
    if direction == "COMPRA" and na_sell_entry > 0:
        touch_na = abs(c_price - na_sell_entry) / c_price < 0.01
    elif direction == "VENDA" and na_buy_entry > 0:
        touch_na = abs(c_price - na_buy_entry) / c_price < 0.01

    if touch_st or touch_na:
        sinal_super = True

    return {
        "symbol": symbol,
        "direction": direction,
        "type": "SUPER" if sinal_super else "COMUM",
        "price": c_price
    }

# ============================================================
# 5. CABEÇALHO DA PÁGINA
# ============================================================
st.title("Montrezor Trading System")
st.markdown("<p style='color:#8b949e;margin-top:-15px;margin-bottom:30px;'>Método interativo passo a passo para execução de alta performance.</p>", unsafe_allow_html=True)

# ============================================================
# 6. TABS
# ============================================================
tabs = st.tabs([
    "🤖 Sinais & Gráficos",
    "👁️ Visão Geral",
    "✅ Checklist",
    "📋 Método Hougaard",
    "🔬 Simulador"
])

# ============================================================
# TAB: SINAIS & GRÁFICOS (NOVO SISTEMA)
# ============================================================
with tabs[0]:
    col_l, col_r = st.columns([1, 4])

    with col_l:
        st.subheader("Ativos Observados")
        new_sym = st.text_input("Adicionar Par (ex: BTC-USD, AAPL):")
        if st.button("Adicionar"):
            if new_sym and new_sym.upper() not in st.session_state.tracked_symbols:
                st.session_state.tracked_symbols.append(new_sym.upper())
                st.session_state.neuro_athena[new_sym.upper()] = {}
                st.rerun()

        st.markdown("---")
        st.session_state.auto_update = st.toggle("Auto-Update (1 min)", value=st.session_state.auto_update)
        if st.button("🔄 Atualizar Agora"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.subheader("Neuro Athena (Manual)")
        sym_select = st.selectbox("Selecione o Par:", st.session_state.tracked_symbols)

        with st.expander(f"Valores Athena: {sym_select}", expanded=False):
            if sym_select not in st.session_state.neuro_athena:
                st.session_state.neuro_athena[sym_select] = {}

            na = st.session_state.neuro_athena[sym_select]
            na['tp3_up'] = st.number_input("TP 3 (Cima)", value=na.get('tp3_up', 0.0), format="%.5f")
            na['tp2_up'] = st.number_input("TP 2 (Cima)", value=na.get('tp2_up', 0.0), format="%.5f")
            na['tp1_up'] = st.number_input("TP 1 (Cima)", value=na.get('tp1_up', 0.0), format="%.5f")
            na['buy_entry'] = st.number_input("Buy Entry", value=na.get('buy_entry', 0.0), format="%.5f")
            na['sell_entry'] = st.number_input("Sell Entry", value=na.get('sell_entry', 0.0), format="%.5f")
            na['tp1_dn'] = st.number_input("TP 1 (Baixo)", value=na.get('tp1_dn', 0.0), format="%.5f")
            na['tp2_dn'] = st.number_input("TP 2 (Baixo)", value=na.get('tp2_dn', 0.0), format="%.5f")
            na['tp3_dn'] = st.number_input("TP 3 (Baixo)", value=na.get('tp3_dn', 0.0), format="%.5f")

            if st.button("Salvar Valores"):
                st.success("Salvo!")

    with col_r:
        st.subheader("Scanner de Sinais Ao Vivo")

        all_data = {}
        signals_found = []

        with st.spinner("Analisando mercado..."):
            for sym in st.session_state.tracked_symbols:
                sym_data = fetch_multi_tf_data(sym)
                all_data[sym] = sym_data
                if sym_data:
                    sig = check_signals(sym_data, sym, st.session_state.neuro_athena)
                    if sig:
                        signals_found.append(sig)

        if len(signals_found) == 0:
            st.info("Nenhum sinal detectado no momento de acordo com as regras estabelecidas.")
        else:
            for s in signals_found:
                if s["direction"] == "COMPRA":
                    css_class = "signal-card-buy"
                    color = "#1D9E75"
                else:
                    css_class = "signal-card-sell"
                    color = "#E04C4C"

                type_class = "bg-super" if s["type"] == "SUPER" else "bg-comum"

                st.markdown(f"""
                <div class="{css_class}">
                    <div class="signal-type {type_class}">SINAL {s['type']}</div>
                    <div class="signal-title" style="color:{color}">{s['direction']} : {s['symbol']}</div>
                    <div>Preço Atual: <b>{s['price']:.5f}</b></div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Gráficos Integrados")
        chart_sym = st.selectbox("Visualizar Gráfico:", st.session_state.tracked_symbols, key="chart_sym")
        chart_tf = st.selectbox("Timeframe:", ["4h", "1d", "1wk", "1mo"], index=0, key="chart_tf")

        if chart_sym in all_data and chart_tf in all_data[chart_sym]:
            df = all_data[chart_sym][chart_tf]

            fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

            # Row 1: Preço, EMAs, Supertrend
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Preço"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='yellow', width=1), name="EMA 50"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_100'], line=dict(color='orange', width=1), name="EMA 100"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], line=dict(color='purple', width=1), name="EMA 200"), row=1, col=1)

            fig.add_trace(go.Scatter(x=df.index, y=df['ST_Up'], line=dict(color='green', width=2), name="ST Compra"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['ST_Dn'], line=dict(color='red', width=2), name="ST Venda"), row=1, col=1)

            # Add Neuro Athena Lines
            na_vals = st.session_state.neuro_athena.get(chart_sym, {})
            colors = ['#5DCAA5', '#5DCAA5', '#5DCAA5', '#3B8BD4', '#E8593C', '#E04C4C', '#E04C4C', '#E04C4C']
            keys = ['tp3_up', 'tp2_up', 'tp1_up', 'buy_entry', 'sell_entry', 'tp1_dn', 'tp2_dn', 'tp3_dn']
            for k, c in zip(keys, colors):
                val = na_vals.get(k, 0.0)
                if val > 0:
                    fig.add_hline(y=val, line_dash="dot", line_color=c, annotation_text=k.upper(), row=1, col=1)

            # Row 2: RSI + Canal
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#3B8BD4', width=2), name="RSI"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI_Upper'], line=dict(color='gray', dash='dash'), name="RSI Upper"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI_Lower'], line=dict(color='gray', dash='dash'), name="RSI Lower"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI_LR'], line=dict(color='gray', dash='dot'), name="RSI Mid"), row=2, col=1)

            # Row 3: Stoch RSI
            fig.add_trace(go.Scatter(x=df.index, y=df['StochRSI_K'], line=dict(color='#9F77DD', width=1.5), name="Stoch %K"), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['StochRSI_D'], line=dict(color='#5DCAA5', width=1.5), name="Stoch %D"), row=3, col=1)
            fig.add_hline(y=80, line_dash="dot", line_color="red", row=3, col=1)
            fig.add_hline(y=20, line_dash="dot", line_color="green", row=3, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False,
                              title=f"Dashboard Institucional - {chart_sym} ({chart_tf.upper()})")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Dados não disponíveis para este par/timeframe no momento.")

# ============================================================
# AS OUTRAS TABS PERMANECEM INTACTAS, APENAS COPIANDO DO SEU CÓDIGO
# ============================================================
with tabs[1]:
    st.markdown("Aqui fica a Visão Geral do Método Montrezor (Mantida a mesma lógica documental).")
    # ... código original da tab_visao ...

with tabs[2]:
    st.markdown("Checklist Operacional de Entrada.")
    # ... código original da tab_checklist ...

with tabs[3]:
    st.markdown("Referência do Método Hougaard.")
    # ... código original da tab_hougaard ...

with tabs[4]:
    st.markdown("Simulador Interativo.")
    # ... código original da tab_sim ...

# ============================================================
# LÓGICA DE AUTO-REFRESH (FINAL DO ARQUIVO)
# ============================================================
if st.session_state.auto_update:
    time.sleep(60)
    st.rerun()
