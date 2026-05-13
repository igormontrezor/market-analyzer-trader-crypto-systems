import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
import time
import json
import os

# ============================================================
# MT5 DATA PROVIDER  (fonte única — sem yfinance)
# ============================================================
# Requer: pip install MetaTrader5
# Requer: terminal MT5 aberto e logado no broker
#
# Por que MT5 puro:
#   yfinance tem OHLC diferente do MT5 (spread, fonte diferente).
#   Isso causava sinais errados — RSI calculado sobre OHLC diferente
#   do gráfico que você vê, resultando em toques que não existiam
#   ou toques reais que não eram detectados.
#   Com MT5 os dados são idênticos ao terminal: mesmos candles,
#   mesmo RSI, mesmos toques.
# ============================================================
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    _MT5_AVAILABLE = False

# ── Timeframes MT5 ────────────────────────────────────────────
MT5_TF = {
    "1mo": 49153,   # TIMEFRAME_MN1
    "1wk": 32769,   # TIMEFRAME_W1
    "1d":  16408,   # TIMEFRAME_D1
    "4h":  16388,   # TIMEFRAME_H4
}

# Quantidade de barras por TF (suficiente para todos os indicadores)
MT5_BARS = {
    "1mo": 120,    # ~10 anos
    "1wk": 300,    # ~6 anos
    "1d":  730,    # ~3 anos
    "4h":  1500,   # ~250 dias
}

# ── Inicialização MT5 ─────────────────────────────────────────
def _init_mt5() -> bool:
    """Inicializa e conecta ao terminal MT5. Retorna True se OK."""
    if not _MT5_AVAILABLE:
        return False
    try:
        # Se já está conectado não faz nada
        if mt5.terminal_info() is not None:
            return True
        return mt5.initialize()
    except Exception:
        return False

# ── Download via MT5 ──────────────────────────────────────────
def fetch_ohlcv(symbol: str, interval: str) -> pd.DataFrame | None:
    """
    Baixa dados OHLCV do MetaTrader5.

    symbol:   nome exato como aparece no MT5 (ex: CHFJPY#, EURUSD#, BTCUSD#)
    interval: '1mo' | '1wk' | '1d' | '4h'

    Retorna DataFrame com colunas Open/High/Low/Close/Volume
    e índice DatetimeIndex tz-naive (UTC), ordenado do mais antigo
    para o mais recente. Retorna None se falhar.
    """
    if not _init_mt5():
        return None

    tf  = MT5_TF.get(interval, 16408)
    n   = MT5_BARS.get(interval, 500)

    # Garantir que o símbolo está ativo no Market Watch
    if mt5.symbol_info(symbol) is None:
        mt5.symbol_select(symbol, True)
        if mt5.symbol_info(symbol) is None:
            return None   # símbolo não existe neste broker

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) == 0:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')   # UTC tz-naive
    df = (df.rename(columns={'time':'Date','open':'Open','high':'High',
                              'low':'Low','close':'Close','tick_volume':'Volume'})
           .set_index('Date')
          [['Open','High','Low','Close','Volume']]
           .sort_index())
    return df

def get_data_source_label() -> str:
    """Retorna string com nome do terminal MT5 conectado."""
    if _init_mt5():
        info = mt5.terminal_info()
        if info:
            return f"MT5 ✅ {info.name}"
    return "MT5 ❌ não conectado"


# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS
# ============================================================
st.set_page_config(page_title="MONTREZOR - Trading System", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;600&display=swap');

    [data-testid="stAppViewContainer"]  { background:#0b0e11; }
    .block-container { padding-top: 2rem; max-width: 98%; font-family:'JetBrains Mono',monospace !important;}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #30363d; }
    .stTabs [data-baseweb="tab"] { padding: 10px 20px; color: #8b949e; border-radius: 4px 4px 0 0; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; background-color: #161b22; }

    /* Cards */
    .rule-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 15px; }
    .rule-title { color: #c9d1d9; font-size: 16px; font-weight: bold; margin-bottom: 10px; display: flex; align-items: center; gap: 10px; }
    .rule-badge { background: #da3633; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
    .rule-body { color: #8b949e; font-size: 14px; line-height: 1.6; }
    .info-box { background-color: #1c2128; border-left: 4px solid #3B8BD4; padding: 15px; border-radius: 4px; color: #c9d1d9; font-size: 14px; margin-bottom: 20px; }

    /* Sinais */
    .signal-card-buy  { background: rgba(29,158,117,0.12); border: 1px solid #1D9E75; border-radius: 8px; padding: 15px; margin-bottom: 10px;}
    .signal-card-sell { background: rgba(224,76,76,0.12);  border: 1px solid #E04C4C; border-radius: 8px; padding: 15px; margin-bottom: 10px;}
    .signal-title { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
    .signal-type  { font-size: 12px; padding: 3px 8px; border-radius: 4px; display: inline-block; margin-bottom: 10px;}
    .bg-super { background: #E0A905; color: #000; font-weight: bold; }
    .bg-comum { background: #3B8BD4; color: #fff; font-weight: bold; }

    /* Painel de sinais compacto */
    .signals-bar { display:flex; flex-wrap:wrap; gap:8px; padding:12px; background:#0f1319; border-radius:8px; border:1px solid #30363d; margin-bottom:16px; }
    .sig-pill-buy  { background:rgba(29,158,117,0.18); border:1px solid #1D9E75; border-radius:20px; padding:5px 14px; color:#1D9E75; font-size:13px; font-weight:bold; }
    .sig-pill-sell { background:rgba(224,76,76,0.18);  border:1px solid #E04C4C; border-radius:20px; padding:5px 14px; color:#E04C4C; font-size:13px; font-weight:bold; }
    .sig-pill-super { outline:2px solid #E0A905; }

    /* Athena panel */
    .athena-label { color:#8b949e; font-size:12px; margin-bottom:2px; }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 2. SESSION STATES
# ============================================================
if 'step_active'      not in st.session_state: st.session_state.step_active      = 0
if 'hougaard_step'    not in st.session_state: st.session_state.hougaard_step    = -1
if 'tracked_symbols'  not in st.session_state: st.session_state.tracked_symbols  = ["CHFJPY#", "EURUSD#", "BTCUSD#"]
if 'neuro_athena'     not in st.session_state: st.session_state.neuro_athena     = {}
if 'auto_update'      not in st.session_state: st.session_state.auto_update      = False
if 'last_update'      not in st.session_state: st.session_state.last_update      = 0
if 'cached_data'      not in st.session_state: st.session_state.cached_data      = {}
if 'na_tf_select'     not in st.session_state: st.session_state.na_tf_select     = {}

# ============================================================
# 3. INDICADORES
# ============================================================
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr(df, period=10, use_true_atr=True):
    high = df['High']
    low  = df['Low']
    close_prev = df['Close'].shift(1)
    if use_true_atr:
        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low  - close_prev).abs()
        ], axis=1).max(axis=1)
        return tr.ewm(alpha=1/period, adjust=False).mean()
    else:
        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low  - close_prev).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

def calc_supertrend(df, period=10, multiplier=3.0, use_true_atr=True):
    hl2  = (df['High'] + df['Low']) / 2
    atr  = calc_atr(df, period, use_true_atr)

    up_basic = hl2 - (multiplier * atr)
    dn_basic = hl2 + (multiplier * atr)

    n = len(df)
    up_band  = [np.nan] * n
    dn_band  = [np.nan] * n
    trend    = [0]      * n
    close    = df['Close'].values

    for i in range(1, n):
        ub = up_basic.iloc[i] if not np.isnan(up_basic.iloc[i]) else 0
        db = dn_basic.iloc[i] if not np.isnan(dn_basic.iloc[i]) else 0

        prev_up = up_band[i-1] if not np.isnan(up_band[i-1]) else ub
        prev_dn = dn_band[i-1] if not np.isnan(dn_band[i-1]) else db

        up_band[i] = max(ub, prev_up) if close[i-1] > prev_up else ub
        dn_band[i] = min(db, prev_dn) if close[i-1] < prev_dn else db

        if   trend[i-1] == -1 and close[i] > prev_dn: trend[i] =  1
        elif trend[i-1] ==  1 and close[i] < prev_up: trend[i] = -1
        else: trend[i] = trend[i-1] if trend[i-1] != 0 else 1

    df = df.copy()
    up_arr  = np.array(up_band, dtype=float)
    dn_arr  = np.array(dn_band, dtype=float)
    t_arr   = np.array(trend,   dtype=int)

    df['ST_Up']    = np.where(t_arr ==  1, up_arr, np.nan)
    df['ST_Dn']    = np.where(t_arr == -1, dn_arr, np.nan)
    df['ST_Line']  = np.where(t_arr ==  1, up_arr, dn_arr)
    df['ST_Trend'] = t_arr
    return df

def calc_rsi(series, period=14):
    """RSI de Wilder — identico ao iRSI do MT5.
    Seed: SMA simples dos primeiros `period` deltas.
    Smoothing: (prev * (period-1) + current) / period
    Diferenca vs ewm(com=period-1): tipicamente 3-8 pts,
    suficiente para alinhar os toques de canal com o MT5.
    """
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0)
    loss  = (-delta.where(delta < 0, 0.0))

    n = len(series)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)

    vals_g = gain.values
    vals_l = loss.values

    if n > period:
        avg_gain[period] = float(np.nanmean(vals_g[1:period+1]))
        avg_loss[period] = float(np.nanmean(vals_l[1:period+1]))
        for i in range(period + 1, n):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + vals_g[i]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + vals_l[i]) / period

    ag = pd.Series(avg_gain, index=series.index)
    al = pd.Series(avg_loss, index=series.index).replace(0, np.nan)
    rs = ag / al
    return 100 - (100 / (1 + rs))

def calc_rsi_channel(df, rsi_period=14, lr_period=50, multiplier=2.0):
    df = df.copy()
    df['RSI']       = calc_rsi(df['Close'], rsi_period)
    df['RSI_LR']    = np.nan
    df['RSI_Upper'] = np.nan
    df['RSI_Lower'] = np.nan

    rsi_vals = df['RSI'].values
    x = np.arange(lr_period, dtype=float)
    sumx = float(np.sum(x))
    sumxx = float(np.sum(x * x))
    denom = (sumx * sumx - lr_period * sumxx)

    lr_loc = df.columns.get_loc('RSI_LR')
    up_loc = df.columns.get_loc('RSI_Upper')
    lo_loc = df.columns.get_loc('RSI_Lower')

    # Mladen logic (iLrValue):
    # - Uses x = 0..period-1 and y as [current, past...] (reversed window)
    # - Returns LR intercept at x=0 as (sumy + slope*sumx)/period
    # - "error" is the regression standard error (not residual std)
    for i in range(lr_period - 1, len(df)):
        y_win = rsi_vals[i - lr_period + 1:i + 1]
        if np.isnan(y_win).any():
            continue

        # Reverse so y[0] is current bar like the MQL5 implementation
        y = y_win[::-1]
        sumy = float(np.sum(y))
        sumyy = float(np.sum(y * y))
        sumxy = float(np.sum(x * y))

        if denom == 0.0:
            continue

        slope = (lr_period * sumxy - sumx * sumy) / denom

        # Regression standard error (matches MQL5 formula)
        # guard against negative due to floating point
        if lr_period > 2:
            err_num = (
                lr_period * sumyy
                - sumy * sumy
                - slope * slope * (lr_period * sumxx - sumx * sumx)
            )
            err_den = (lr_period * (lr_period - 2.0))
            error = float(np.sqrt(max(err_num / err_den, 0.0))) if err_den != 0 else 0.0
        else:
            error = 0.0

        mid = (sumy + slope * sumx) / lr_period
        df.iloc[i, lr_loc] = mid
        df.iloc[i, up_loc] = mid + error * multiplier
        df.iloc[i, lo_loc] = mid - error * multiplier
    return df

def calc_stoch_rsi(df, rsi_period=14, k_period=14, d_period=3, slowing=5):
    df = df.copy()
    if 'RSI' not in df.columns:
        df['RSI'] = calc_rsi(df['Close'], rsi_period)
    rsi_min = df['RSI'].rolling(k_period).min()
    rsi_max = df['RSI'].rolling(k_period).max()
    raw_k   = 100 * ((df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9))
    df['StochRSI_K'] = raw_k.rolling(slowing).mean()
    df['StochRSI_D'] = df['StochRSI_K'].rolling(d_period).mean()
    return df

# ============================================================
# 4. DOWNLOAD MULTI-TIMEFRAME
# ============================================================
TF_PARAMS = {
    '1mo': {'label': 'Mensal'},
    '1wk': {'label': 'Semanal'},
    '1d':  {'label': 'Diário'},
    '4h':  {'label': '4 Horas'},
}

def _build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica todos os indicadores a um DataFrame OHLCV limpo."""
    df = calc_supertrend(df)
    df['EMA_50']  = calc_ema(df['Close'], 50)
    df['EMA_100'] = calc_ema(df['Close'], 100)
    df['EMA_200'] = calc_ema(df['Close'], 200)
    df = calc_rsi_channel(df)
    df = calc_stoch_rsi(df)
    return df

@st.cache_data(ttl=60, show_spinner=False)
def fetch_multi_tf_data(symbol):
    """
    Baixa dados multi-timeframe para um símbolo via MetaTrader5.
    O símbolo deve ser exatamente como aparece no MT5 (ex: CHFJPY#, EURUSD, BTCUSD).
    Requer terminal MT5 aberto e logado no broker.
    """
    data = {}
    for intv in TF_PARAMS:
        try:
            df = fetch_ohlcv(symbol, intv)
            if df is None or len(df) < 30:
                continue
            df.dropna(subset=['Open','High','Low','Close'], inplace=True)
            data[intv] = _build_indicators(df)
        except Exception:
            pass
    return data

# ============================================================
# 5. LÓGICA DE SINAIS
# ============================================================
def _near(a, b, pct=0.015):
    """Retorna True se a e b estiverem dentro de pct (1.5%) um do outro."""
    try:
        a, b = float(a), float(b)
        if b == 0: return False
        return abs(a - b) / abs(b) < pct
    except:
        return False

def _rsi_touch_bottom(row):
    """TOQUE no fundo do CANAL RSI (opção A): RSI <= RSI_Lower."""
    try:
        return float(row['RSI']) <= float(row['RSI_Lower'])
    except:
        return False

def _rsi_touch_top(row):
    """TOQUE no topo do CANAL RSI (opção A): RSI >= RSI_Upper."""
    try:
        return float(row['RSI']) >= float(row['RSI_Upper'])
    except:
        return False

def _rsi_near_bottom(row, near_pct=0.3):
    """Perto do fundo do CANAL RSI.

    Interpretação: near_pct é percentual da escala do RSI (0..100).
    Ex.: 10% => 10 pontos de RSI acima do Lower.
    """
    try:
        rsi = float(row['RSI'])
        lo = float(row['RSI_Lower'])
        threshold = float(near_pct) * 100.0
        return rsi <= (lo + threshold)
    except:
        return False

def _rsi_near_top(row, near_pct=0.3):
    """Perto do topo do CANAL RSI.

    Interpretação: near_pct é percentual da escala do RSI (0..100).
    Ex.: 10% => 10 pontos de RSI abaixo do Upper.
    """
    try:
        rsi = float(row['RSI'])
        up = float(row['RSI_Upper'])
        threshold = float(near_pct) * 100.0
        return rsi >= (up - threshold)
    except:
        return False

def _count_rsi_points(df, direction, lookback, near_pct=0.10):
    """Conta quantos candles (nos últimos lookback) ficaram em 'ponto' perto da borda do canal."""
    try:
        if df is None or df.empty:
            return 0
        window = df.tail(int(lookback))
        if direction == "COMPRA":
            return int(sum(_rsi_near_bottom(row, near_pct=near_pct) for _, row in window.iterrows()))
        return int(sum(_rsi_near_top(row, near_pct=near_pct) for _, row in window.iterrows()))
    except:
        return 0

def _ema_near(row, pct=0.015):
    try:
        c = float(row['Close'])
        return any(_near(c, float(row[e]), pct) for e in ['EMA_50','EMA_100','EMA_200'])
    except: return False

def _get_confirmed_row(df, allow_current=False):
    """
    Retorna o último candle FECHADO (confirmado) de um dataframe.

    Problema que resolve:
      O MT5 retorna o candle em formação (ainda aberto) como o mais recente.
      Um candle 4H em formação tem Low/High provisórios — isso faz
      'Low <= ST_Line <= High' disparar toque fantasma no Supertrend,
      gerando sinais SUPER que não existem no MT5.

    Regra:
      - Para 4H: se o último candle tiver timestamp de hoje E horário
        de início de candle (0h, 4h, 8h, 12h, 16h, 20h UTC), ele está
        em formação → usar penúltimo.
      - Para 1D: se o último candle for de hoje → usar penúltimo.
      - allow_current=True: nunca descarta (usado para tendência/EMAs,
        onde o candle em formação não distorce o resultado).
    """
    if df is None or len(df) < 2:
        return df.iloc[-1] if df is not None and len(df) >= 1 else None

    if allow_current:
        return df.iloc[-1]

    now_utc = pd.Timestamp.utcnow().tz_localize(None)
    last_ts = df.index[-1]
    # Normalizar para tz-naive para comparação
    if hasattr(last_ts, 'tz') and last_ts.tz is not None:
        last_ts_naive = last_ts.tz_convert('UTC').tz_localize(None)
    else:
        last_ts_naive = last_ts

    # Se o último candle é de hoje, provavelmente está em formação → descartar
    if last_ts_naive.date() >= now_utc.date():
        return df.iloc[-2]

    return df.iloc[-1]


def check_signals(data, symbol, athena_levels):
    if '1mo' not in data or '1wk' not in data:
        return None

    # =========================================================
    # SEPARACAO DE CANDLES POR USO
    # ---------------------------------------------------------
    # TENDENCIA / EMAs        → candle atual (em formacao OK)
    # RSI CANAL 4H/1D         → candle FECHADO (oscila muito intraday)
    # RSI CANAL SEMANAL/MENSAL → candle ATUAL (em formacao OK)
    #
    # Por que semanal/mensal usam o candle em formacao para RSI:
    #   O gatilho 4H/D dispara DURANTE a semana que esta tocando
    #   o canal. O semanal fechado e da semana ANTERIOR — que pode
    #   nao ter tocado ainda. Na 3a/4a feira o semanal em formacao
    #   ja tem 3-4 dias de preco; o RSI e estavel o suficiente.
    #   Usar so o semanal fechado eliminava todos os sinais SUPER
    #   gerados durante a semana do toque (ex: 31/03 e 01/04).
    # =========================================================
    mn_trend = data['1mo'].iloc[-1]        # mensal atual  - tendencia/EMAs
    w1_trend = data['1wk'].iloc[-1]        # semanal atual - tendencia/EMAs

    mn_rsi = data['1mo'].iloc[-1]          # mensal atual  - RSI (em formacao OK)
    w1_rsi = data['1wk'].iloc[-1]          # semanal atual - RSI (em formacao OK)
    if mn_rsi is None or w1_rsi is None:
        return None

    # ── Tendencia Mensal (Supertrend) — PESO MAIOR ──
    # Mensal e obrigatorio. Semanal e confirmacao adicional (peso menor).
    # Sinal pode ser gerado so com mensal; semanal convergindo e bonus.
    trend_mn = int(mn_trend.get('ST_Trend', 0))

    if trend_mn == 0:
        return None   # mensal indefinido — sem sinal

    # ── Tendencia Semanal (so as 3 EMAs — preco nao importa) ──
    try:
        w1_buy_ema  = float(w1_trend['EMA_50']) > float(w1_trend['EMA_100']) > float(w1_trend['EMA_200'])
        w1_sell_ema = float(w1_trend['EMA_50']) < float(w1_trend['EMA_100']) < float(w1_trend['EMA_200'])
    except:
        w1_buy_ema = w1_sell_ema = False

    # Direcao determinada pelo mensal (obrigatorio)
    # Semanal deve CONVERGIR com o mensal para confirmar — se divergir bloqueia
    if trend_mn == 1:
        direction = "COMPRA"
        # Semanal deve confirmar compra ou estar indefinido (nao pode estar em venda)
        if w1_sell_ema:   # semanal divergindo — bloquear
            return None
    else:  # trend_mn == -1
        direction = "VENDA"
        if w1_buy_ema:    # semanal divergindo — bloquear
            return None

    # ── RSI canal — gatilho no DIARIO e/ou 4H (independentes) ──────────────
    # O diario e avaliado SEMPRE (TF de gatilho principal do metodo).
    # O 4H e avaliado como alternativa quando disponivel.
    # Ambos usam candle FECHADO (sem candle em formacao).
    #
    # Near:
    #   Diario/4H      → toque real obrigatorio (hit)
    #   Semanal/Mensal → near 5 pts RSI
    #     3 pts = quase-toque visual no semanal/mensal
    # ────────────────────────────────────────────────────────────────────────
    touch_fn = _rsi_touch_bottom if direction == "COMPRA" else _rsi_touch_top
    near_fn  = _rsi_near_bottom  if direction == "COMPRA" else _rsi_near_top

    # Near universal: 3 pts RSI em todos os TFs (= "3% de 0-100" do método)
    # Semanal/mensal: mesmo 3pts — canal mais largo, toque visual é suficiente
    NEAR_TF  = 0.03   # 3 pontos RSI — diario e 4H
    NEAR_W1_MN = 0.03   # 3 pontos RSI — semanal e mensal

    # Gatilho diario (sempre avaliado, candle FECHADO)
    d1_data   = data.get('1d')
    d1_closed = _get_confirmed_row(d1_data, allow_current=False) if d1_data is not None else None
    hit_d1    = (touch_fn(d1_closed) or near_fn(d1_closed, near_pct=NEAR_TF)) if d1_closed is not None else False

    # Gatilho 4H (alternativa quando disponivel, candle FECHADO)
    hit_4h = False
    tfm_4h = None
    if '4h' in data:
        tfm_4h = _get_confirmed_row(data['4h'], allow_current=False)
        hit_4h = (touch_fn(tfm_4h) or near_fn(tfm_4h, near_pct=NEAR_TF)) if tfm_4h is not None else False

    # Candle de referencia para preco/ST: 4H se tocou, senao diario
    if hit_4h and tfm_4h is not None:
        tfm = tfm_4h
        tf_menor_key = '4h'
    elif d1_closed is not None:
        tfm = d1_closed
        tf_menor_key = '1d'
    else:
        return None

    hit_tfm = hit_d1 or hit_4h   # toque em qualquer dos dois TFs menores

    # Semanal/Mensal
    hit_w1  = touch_fn(w1_rsi)
    hit_mn  = touch_fn(mn_rsi)
    near_w1 = near_fn(w1_rsi, near_pct=NEAR_W1_MN)
    near_mn = near_fn(mn_rsi, near_pct=NEAR_W1_MN)

    minor_ok   = hit_tfm
    weekly_ok  = hit_w1 or near_w1
    monthly_ok = hit_mn or near_mn

    canal_ok = minor_ok and (weekly_ok or monthly_ok)
    if not canal_ok:
        return None

    # ── EMA proxima (qualquer TF) - candles atuais (EMAs sao suaves) ──
    d1_cur = d1_data.iloc[-1] if d1_data is not None and not d1_data.empty else None
    ema_ok = _ema_near(mn_trend) or _ema_near(w1_trend) or (_ema_near(d1_cur) if d1_cur is not None else False)
    if not ema_ok:
        return None

    # ── Sinal COMUM confirmado ──
    # ── Checar Sinal SUPER ──
    sinal_super = False
    c_price = float(tfm['Close'])

    na = athena_levels.get(symbol, {})
    na_buy_entry  = na.get('buy_entry',  0.0)
    na_sell_entry = na.get('sell_entry', 0.0)

    # Toque OU PROXIMO do Supertrend (candle FECHADO — sem Low/High provisorio)
    # "Proximo" = Close dentro de 1.5% do ST_Line (mesmo threshold das EMAs)
    try:
        st_line  = float(tfm['ST_Line'])
        c_low    = float(tfm['Low'])
        c_high   = float(tfm['High'])
        touch_st = (c_low <= st_line <= c_high) or _near(c_price, st_line, pct=0.015)
    except:
        touch_st = False

    # Toque OU PROXIMO do nivel Athena oposto
    # Compra: preco proximo do Sell Entry (zona de suporte oposto)
    # Venda:  preco proximo do Buy Entry
    touch_na = False
    if direction == "COMPRA" and na_sell_entry > 0:
        touch_na = _near(c_price, na_sell_entry, pct=0.012)
    elif direction == "VENDA" and na_buy_entry > 0:
        touch_na = _near(c_price, na_buy_entry, pct=0.012)

    if touch_st or touch_na:
        sinal_super = True

    # Timestamp do candle que gerou o sinal
    try:
        signal_ts = tfm.name
    except Exception:
        signal_ts = None

    return {
        "symbol":    symbol,
        "direction": direction,
        "type":      "SUPER" if sinal_super else "COMUM",
        "price":     c_price,
        "tf_menor":  tf_menor_key,
        "trend_mn":  trend_mn,
        "signal_ts": signal_ts,
        # debug: quais condicoes passaram
        "_debug": {
            "hit_tfm": hit_tfm, "hit_w1": hit_w1, "hit_mn": hit_mn,
            "near_w1": near_w1, "near_mn": near_mn,
            "touch_st": touch_st, "touch_na": touch_na,
            "w1_rsi_val": round(float(w1_rsi.get('RSI', 0)), 2),
            "w1_lower":   round(float(w1_rsi.get('RSI_Lower', 0)), 2),
            "w1_upper":   round(float(w1_rsi.get('RSI_Upper', 0)), 2),
            "mn_rsi_val": round(float(mn_rsi.get('RSI', 0)), 2),
        },
    }

# ============================================================
# 6. FUNÇÃO DE GRÁFICO PRINCIPAL
# ============================================================
COLORS = {
    'ema50':   '#F9E55D',
    'ema100':  '#F0953A',
    'ema200':  '#B44BF5',
    'st_up':   '#00D26A',
    'st_dn':   '#FF4C4C',
    'rsi_mn':  '#9F77DD',
    'rsi_w1':  '#5DCAA5',
    'rsi_d':   '#3B8BD4',
    'rsi_4h':  '#F97316',
    'stoch_k_w1': '#5DCAA5',
    'stoch_d_w1': '#9F77DD',
    'stoch_k_d':  '#3B8BD4',
    'stoch_d_d':  '#F9E55D',
    'stoch_k_4h': '#F97316',
    'stoch_d_4h': '#E04C4C',
    'canal':    '#ffffff',
    'athena_up':   ['#2ecc71','#27ae60','#1abc9c'],  # TP3,TP2,TP1 (cima/buy)
    'athena_buy':  '#3B8BD4',
    'athena_sell': '#E8593C',
    'athena_dn':   ['#e74c3c','#c0392b','#922b21'],  # TP1,TP2,TP3 (baixo/sell)
}

TF_COLOR_MAP = {'1mo': COLORS['rsi_mn'], '1wk': COLORS['rsi_w1'],
                '1d': COLORS['rsi_d'], '4h': COLORS['rsi_4h']}

def build_chart(all_data, symbol, chart_tf, athena_levels, show_tfs):
    """Constrói o gráfico multi-painel com todos os indicadores."""
    if chart_tf not in all_data:
        return None

    df = all_data[chart_tf]
    na = athena_levels.get(symbol, {})

    # ── Layout: Price | RSI multi-TF | Stoch multi-TF ──
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.58, 0.22, 0.20],
        subplot_titles=[
            f"Preço — {symbol} ({chart_tf.upper()})",
            "RSI + Canal (Multi-TF)",
            "Stochastic RSI (Multi-TF)"
        ]
    )

    # ─── ROW 1: PREÇO ───────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        name="Preço",
        increasing_line_color='#2ecc71',
        decreasing_line_color='#e74c3c',
        increasing_fillcolor='#2ecc71',
        decreasing_fillcolor='#e74c3c',
    ), row=1, col=1)

    # EMAs
    for col, clr, nm in [('EMA_50', COLORS['ema50'], 'EMA 50'),
                          ('EMA_100', COLORS['ema100'], 'EMA 100'),
                          ('EMA_200', COLORS['ema200'], 'EMA 200')]:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col],
                line=dict(color=clr, width=1.2), name=nm, opacity=0.85), row=1, col=1)

    # Supertrend
    if 'ST_Up' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['ST_Up'],
            line=dict(color=COLORS['st_up'], width=2), name="ST Compra",
            mode='lines'), row=1, col=1)
    if 'ST_Dn' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['ST_Dn'],
            line=dict(color=COLORS['st_dn'], width=2), name="ST Venda",
            mode='lines'), row=1, col=1)

    # ── Neuro Athena lines ──
    athena_keys = [
        ('tp3_up',    COLORS['athena_up'][0],   'TP3 ↑',   True),
        ('tp2_up',    COLORS['athena_up'][1],   'TP2 ↑',   True),
        ('tp1_up',    COLORS['athena_up'][2],   'TP1 ↑',   True),
        ('buy_entry', COLORS['athena_buy'],     'Buy Entry', True),
        ('sell_entry',COLORS['athena_sell'],    'Sell Entry',True),
        ('tp1_dn',    COLORS['athena_dn'][0],   'TP1 ↓',   True),
        ('tp2_dn',    COLORS['athena_dn'][1],   'TP2 ↓',   True),
        ('tp3_dn',    COLORS['athena_dn'][2],   'TP3 ↓',   True),
    ]
    for key, clr, label, _ in athena_keys:
        val = na.get(key, 0.0)
        if val and float(val) > 0:
            fig.add_hline(y=float(val), line_dash="dot", line_color=clr,
                          line_width=1.4, annotation_text=f"  {label}",
                          annotation_font_color=clr, annotation_font_size=11,
                          row=1, col=1)

    # ─── ROW 2: RSI MULTI-TF ────────────────────────────────
    tf_labels = {'1mo': 'Mensal', '1wk': 'Semanal', '1d': 'Diário', '4h': '4H'}
    tfs_rsi = [tf for tf in ['1mo', '1wk', '1d', '4h'] if tf in show_tfs and tf in all_data]

    def _last_lr_channel_params(rsi_series, lr_period, width_mult):
        """Params do canal LR no ÚLTIMO candle (igual lógica do Mladen)."""
        try:
            s = pd.Series(rsi_series).dropna()
            if len(s) < lr_period:
                return None

            y_win = s.values[-lr_period:]
            # y[0] = candle atual
            y = y_win[::-1].astype(float)
            x = np.arange(lr_period, dtype=float)

            sumx = float(np.sum(x))
            sumxx = float(np.sum(x * x))
            sumy = float(np.sum(y))
            sumyy = float(np.sum(y * y))
            sumxy = float(np.sum(x * y))

            denom = (sumx * sumx - lr_period * sumxx)
            if denom == 0.0:
                return None

            slope = (lr_period * sumxy - sumx * sumy) / denom

            if lr_period > 2:
                err_num = (
                    lr_period * sumyy
                    - sumy * sumy
                    - slope * slope * (lr_period * sumxx - sumx * sumx)
                )
                err_den = (lr_period * (lr_period - 2.0))
                error = float(np.sqrt(max(err_num / err_den, 0.0))) if err_den != 0 else 0.0
            else:
                error = 0.0

            mid_now = (sumy + slope * sumx) / lr_period
            mid_then = mid_now - (lr_period - 1.0) * slope
            half_width = error * float(width_mult)
            return {
                'mid_now': mid_now,
                'mid_then': mid_then,
                'up_now': mid_now + half_width,
                'up_then': mid_then + half_width,
                'lo_now': mid_now - half_width,
                'lo_then': mid_then - half_width,
            }
        except:
            return None

    for tf in tfs_rsi:
        dft  = all_data[tf]
        clr  = TF_COLOR_MAP[tf]
        lbl  = tf_labels[tf]
        # Normalizar índices para mesmo timezone antes do reindex
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            dft_index = dft.index.tz_localize(df.index.tz) if dft.index.tz is None else dft.index.tz_convert(df.index.tz)
        else:
            dft_index = dft.index.tz_localize(None) if hasattr(dft.index, 'tz') and dft.index.tz is not None else dft.index

        dft_aligned = dft.copy()
        dft_aligned.index = dft_index
        # Alinhar índice ao timeframe do gráfico (resample/forward-fill)
        rsi_aligned = dft_aligned['RSI'].reindex(df.index, method='ffill')
        fig.add_trace(go.Scatter(x=df.index, y=rsi_aligned,
            line=dict(color=clr, width=1.5), name=f"RSI {lbl}"), row=2, col=1)

        # Canal RSI igual MT5: 3 linhas RETAS usando só o último LR (não é banda/BB)
        params = _last_lr_channel_params(dft_aligned['RSI'], lr_period=50, width_mult=2.0)
        if params is not None and len(df.index) >= 2:
            # desenhar o canal no eixo do gráfico atual: do "agora" até lr_period candles atrás
            x_now = df.index[-1]
            x_then = df.index[max(0, len(df.index) - 50)]

            fig.add_trace(go.Scatter(
                x=[x_then, x_now],
                y=[params['up_then'], params['up_now']],
                line=dict(color=clr, width=1.0, dash='solid'),
                name=f"Upper {lbl}",
                showlegend=False,
                opacity=0.70,
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=[x_then, x_now],
                y=[params['lo_then'], params['lo_now']],
                line=dict(color=clr, width=1.0, dash='solid'),
                name=f"Lower {lbl}",
                showlegend=False,
                opacity=0.70,
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=[x_then, x_now],
                y=[params['mid_then'], params['mid_now']],
                line=dict(color=clr, width=0.9, dash='dot'),
                name=f"LR {lbl}",
                showlegend=False,
                opacity=0.85,
            ), row=2, col=1)

    # Níveis 30/70
    fig.add_hline(y=70, line_dash="dot", line_color="rgba(255,80,80,0.4)", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="rgba(80,255,160,0.4)", row=2, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="rgba(200,200,200,0.2)", row=2, col=1)

    # ─── ROW 3: STOCH RSI MULTI-TF ──────────────────────────
    stoch_colors = {
        '1wk': (COLORS['stoch_k_w1'], COLORS['stoch_d_w1']),
        '1d':  (COLORS['stoch_k_d'],  COLORS['stoch_d_d']),
        '4h':  (COLORS['stoch_k_4h'], COLORS['stoch_d_4h']),
    }
    tfs_stoch = [tf for tf in ['1wk', '1d', '4h'] if tf in show_tfs and tf in all_data]

    for tf in tfs_stoch:
        dft = all_data[tf]
        ck, cd = stoch_colors.get(tf, ('#aaa', '#888'))
        lbl = tf_labels[tf]

        # Normalizar índices para mesmo timezone antes do reindex
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            dft_index = dft.index.tz_localize(df.index.tz) if dft.index.tz is None else dft.index.tz_convert(df.index.tz)
        else:
            dft_index = dft.index.tz_localize(None) if hasattr(dft.index, 'tz') and dft.index.tz is not None else dft.index

        dft_aligned = dft.copy()
        dft_aligned.index = dft_index

        if 'StochRSI_K' in dft.columns:
            k_aligned = dft_aligned['StochRSI_K'].reindex(df.index, method='ffill')
            d_aligned = dft_aligned['StochRSI_D'].reindex(df.index, method='ffill')
            fig.add_trace(go.Scatter(x=df.index, y=k_aligned,
                line=dict(color=ck, width=1.4), name=f"%K {lbl}"), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=d_aligned,
                line=dict(color=cd, width=1.0, dash='dot'), name=f"%D {lbl}"), row=3, col=1)

    fig.add_hline(y=80, line_dash="dot", line_color="rgba(255,80,80,0.4)",  row=3, col=1)
    fig.add_hline(y=20, line_dash="dot", line_color="rgba(80,255,160,0.4)", row=3, col=1)

    # ─── LAYOUT ─────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        height=900,
        paper_bgcolor="#0b0e11",
        plot_bgcolor="#0f1319",
        font=dict(family="JetBrains Mono", color="#c9d1d9", size=11),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    xanchor="left", x=0, font_size=10, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1e2530", row=i, col=1, showspikes=True,
                         spikecolor="#444", spikethickness=1)
        fig.update_yaxes(gridcolor="#1e2530", row=i, col=1)

    return fig

# ============================================================
# 7. CABEÇALHO
# ============================================================
st.markdown("""
<div style='display:flex;align-items:center;gap:16px;margin-bottom:8px'>
  <span style='font-size:28px;font-weight:bold;color:#c9d1d9;
               font-family:JetBrains Mono,monospace;letter-spacing:2px'>
    ⬛ MONTREZOR
  </span>
  <span style='color:#8b949e;font-size:14px;margin-top:6px'>Trading System v2</span>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 8. TABS
# ============================================================
tabs = st.tabs([
    "📡 Sinais & Gráficos",
    "👁️ Visão Geral",
    "✅ Checklist",
    "📋 Método Hougaard",
    "🔬 Simulador"
])

# ════════════════════════════════════════════════════════════
# TAB 0 — SINAIS & GRÁFICOS
# ════════════════════════════════════════════════════════════
with tabs[0]:

    # ── Layout: sidebar esquerda | área principal ──
    col_side, col_main = st.columns([1, 5], gap="medium")

    # ─────────────── SIDEBAR ───────────────────────────────
    with col_side:
        st.markdown("#### 🔍 Ativos")

        new_sym = st.text_input("Adicionar par:", placeholder="MT5: CHFJPY#, EURUSD# | yf: CHFJPY#, BTCUSD#")
        if st.button("➕ Adicionar", use_container_width=True):
            syms = [s.strip().upper() for s in new_sym.split(",") if s.strip()]
            for s in syms:
                if s and s not in st.session_state.tracked_symbols:
                    st.session_state.tracked_symbols.append(s)
                    st.session_state.neuro_athena.setdefault(s, {})
            st.rerun()

        # Lista de pares — clicável para selecionar
        if st.session_state.tracked_symbols:
            sym_to_remove = None
            for sym in st.session_state.tracked_symbols:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"<span style='color:#c9d1d9;font-size:13px'>📌 {sym}</span>",
                                unsafe_allow_html=True)
                with c2:
                    if st.button("✕", key=f"rm_{sym}", help=f"Remover {sym}"):
                        sym_to_remove = sym
            if sym_to_remove:
                st.session_state.tracked_symbols.remove(sym_to_remove)
                st.rerun()

        st.markdown("---")
        # Badge de fonte de dados
        _src_label = get_data_source_label()
        _src_color = "#1D9E75" if "MT5" in _src_label else "#E0A905"
        st.markdown(
            f"<div style='background:rgba(0,0,0,0.3);border:1px solid {_src_color};"
            f"border-radius:6px;padding:6px 10px;font-size:11px;color:{_src_color};"
            f"text-align:center;margin-bottom:8px'>📡 {_src_label}</div>",
            unsafe_allow_html=True)

        st.session_state.auto_update = st.toggle("⏱ Auto (1 min)", value=st.session_state.auto_update)
        if st.button("🔄 Atualizar Agora", use_container_width=True):
            st.cache_data.clear()
            st.session_state.last_update = 0
            st.rerun()

        # ── TFs visíveis ──
        st.markdown("---")
        st.markdown("#### 📊 Timeframes")
        show_1mo = st.checkbox("Mensal",   value=True)
        show_1wk = st.checkbox("Semanal",  value=True)
        show_1d  = st.checkbox("Diário",   value=True)
        show_4h  = st.checkbox("4 Horas",  value=True)
        show_tfs = [tf for tf, ok in [('1mo',show_1mo),('1wk',show_1wk),
                                       ('1d',show_1d),('4h',show_4h)] if ok]

        st.markdown("---")

        # ── Neuro Athena ──
        st.markdown("#### 🧠 Neuro Athena")
        sym_select = st.selectbox("Par:", st.session_state.tracked_symbols,
                                  key="athena_sym_sel")

        # Seleção de timeframe para os níveis Athena
        tf_options = ["Qualquer (geral)", "Mensal (1mo)", "Semanal (1wk)", "Diário (1d)", "4H (4h)"]
        tf_sel = st.selectbox("Timeframe dos níveis:", tf_options, key="athena_tf_sel_box")

        if sym_select not in st.session_state.neuro_athena:
            st.session_state.neuro_athena[sym_select] = {}

        na = st.session_state.neuro_athena[sym_select]

        st.markdown("<div style='color:#8b949e;font-size:11px;margin-bottom:6px'>"
                    "Deixe 0 para ocultar o nível</div>", unsafe_allow_html=True)

        def na_input(label, key, color):
            val = float(na.get(key, 0.0))
            new_val = st.number_input(
                f"🔵 {label}" if "Buy" in label else
                f"🔴 {label}" if "Sell" in label else
                f"🟢 {label}" if "↑" in label else f"🔴 {label}",
                value=val, format="%.5f", key=f"na_{sym_select}_{key}", step=0.00001)
            na[key] = new_val

        na_input("TP 3 ↑", "tp3_up", "#2ecc71")
        na_input("TP 2 ↑", "tp2_up", "#27ae60")
        na_input("TP 1 ↑", "tp1_up", "#1abc9c")
        na_input("Buy Entry", "buy_entry", "#3B8BD4")
        na_input("Sell Entry", "sell_entry", "#E8593C")
        na_input("TP 1 ↓", "tp1_dn", "#e74c3c")
        na_input("TP 2 ↓", "tp2_dn", "#c0392b")
        na_input("TP 3 ↓", "tp3_dn", "#922b21")

        if st.button("💾 Salvar Athena", use_container_width=True):
            st.success("✅ Salvo!")

    # ─────────────── ÁREA PRINCIPAL ────────────────────────
    with col_main:

        # ── Baixar todos os dados ──
        all_sym_data = {}
        signals_found = []

        progress_ph = st.empty()
        with progress_ph.container():
            prog = st.progress(0, text="Carregando dados...")

        for i, sym in enumerate(st.session_state.tracked_symbols):
            sym_data = fetch_multi_tf_data(sym)
            all_sym_data[sym] = sym_data
            prog_val = int((i + 1) / max(len(st.session_state.tracked_symbols), 1) * 100)
            prog.progress(prog_val, text=f"Analisando {sym}...")
            if sym_data:
                sig = check_signals(sym_data, sym, st.session_state.neuro_athena)
                if sig:
                    signals_found.append(sig)

        progress_ph.empty()

        # ── PAINEL DE SINAIS (topo) ──
        st.markdown("### 📡 Sinais Detectados")

        if not signals_found:
            st.info("🔍 Nenhum sinal detectado no momento. O mercado aguarda confluência.")
        else:
            pills_html = "<div class='signals-bar'>"
            for s in signals_found:
                cls = "sig-pill-buy" if s["direction"] == "COMPRA" else "sig-pill-sell"
                super_cls = " sig-pill-super" if s["type"] == "SUPER" else ""
                icon = "▲" if s["direction"] == "COMPRA" else "▼"
                tag  = "⭐SUPER" if s["type"] == "SUPER" else "•COMUM"
                pills_html += f"<span class='{cls}{super_cls}'>{icon} {s['symbol']} {tag}</span>"
            pills_html += "</div>"
            st.markdown(pills_html, unsafe_allow_html=True)

            # Detalhes dos sinais
            cols_sig = st.columns(min(len(signals_found), 3))
            for idx, s in enumerate(signals_found):
                with cols_sig[idx % 3]:
                    css = "signal-card-buy" if s["direction"] == "COMPRA" else "signal-card-sell"
                    clr = "#1D9E75" if s["direction"] == "COMPRA" else "#E04C4C"
                    typ_cls = "bg-super" if s["type"] == "SUPER" else "bg-comum"
                    st.markdown(f"""
                    <div class="{css}">
                      <div class="signal-type {typ_cls}">SINAL {s['type']}</div>
                      <div class="signal-title" style="color:{clr}">
                        {"▲" if s["direction"]=="COMPRA" else "▼"} {s["direction"]} · {s["symbol"]}
                      </div>
                      <div style="color:#8b949e;font-size:13px">
                        Preço: <b style="color:#c9d1d9">{s['price']:.5f}</b><br>
                        TF ref: {s['tf_menor'].upper()}<br>
                        Candle: <b style="color:#c9d1d9">{str(s.get('signal_ts', ''))[:16] if s.get('signal_ts') is not None else '—'}</b>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("---")

        # ── GRÁFICO ──
        st.markdown("### 📈 Gráfico Integrado")

        g_col1, g_col2 = st.columns([2, 1])
        with g_col1:
            chart_sym = st.selectbox("Par:", st.session_state.tracked_symbols, key="chart_sym_sel")
        with g_col2:
            chart_tf = st.selectbox("Timeframe:", ["4h","1d","1wk","1mo"], key="chart_tf_sel")

        if chart_sym in all_sym_data and all_sym_data[chart_sym]:
            fig = build_chart(all_sym_data[chart_sym], chart_sym,
                              chart_tf, st.session_state.neuro_athena, show_tfs)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={
                    'scrollZoom': True,
                    'displayModeBar': True,
                    'modeBarButtonsToRemove': ['autoScale2d'],
                })
            else:
                st.warning(f"Dados insuficientes para {chart_sym} no timeframe {chart_tf}.")
        else:
            st.warning(f"Dados não disponíveis para {chart_sym}. Verifique o ticker.")

        # ── Timestamp ──
        st.markdown(
            f"<div style='color:#444;font-size:11px;text-align:right;margin-top:8px'>"
            f"Última atualização: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
            unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 1 — VISÃO GERAL
# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown("""
    <div class='info-box'>
    <b>📖 Método Montrezor — Visão Geral</b><br><br>
    Sistema baseado em confluência de múltiplos timeframes, combinando:<br>
    <ul>
    <li><b>Tendência Mensal</b>: Supertrend ATR (10/3.0)</li>
    <li><b>Tendência Semanal</b>: EMAs 50/100/200 convergindo</li>
    <li><b>Gatilho</b>: RSI Slope (canal de regressão linear) tocando extremos no contra-fluxo</li>
    <li><b>Confirmação</b>: Proximidade de EMA nos TFs superiores</li>
    <li><b>Sinal Super</b>: Toque no Supertrend ativo ou no nível Neuro Athena oposto</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='rule-card'>
      <div class='rule-title'>🎯 Tendência</div>
      <div class='rule-body'>
        <b>COMPRA</b>: Supertrend Mensal = alta + EMAs Semanal 50>100>200 abaixo do preço<br>
        <b>VENDA</b>: Supertrend Mensal = baixa + EMAs Semanal 50<100<200 acima do preço<br>
        <span style='color:#5DCAA5'>⚡ Peso maior para tendência mensal</span>
      </div>
    </div>
    <div class='rule-card'>
      <div class='rule-title'>🔔 Sinal Comum <span class='rule-badge'>COMUM</span></div>
      <div class='rule-body'>
        Tendência Mensal confirmada + <br>
        Toque (D ou 4H) no canal RSI + (toque ou 3 pontos no Semanal OR 1 ponto no Mensal) + <br>
        Proximidade/toque de EMA (qualquer, em D/S/M)
      </div>
    </div>
    <div class='rule-card'>
      <div class='rule-title'>⭐ Sinal Super <span class='rule-badge' style='background:#E0A905;color:#000'>SUPER</span></div>
      <div class='rule-body'>
        Todos os critérios do Sinal Comum + <br>
        Toque/proximidade do Sell Entry (na compra) ou Buy Entry (na venda) do Neuro Athena OU<br>
        Toque no Supertrend ativo
      </div>
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 2 — CHECKLIST
# ════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("### ✅ Checklist de Entrada")
    items = [
        ("Tendência Mensal (Supertrend) definida",           True),
        ("Tendência Semanal (EMAs 50/100/200 convergindo)",  True),
        ("RSI no canal — toque no extremo (contra-fluxo)",   True),
        ("EMA próxima no D/S/M",                             True),
        ("Volume acima da média (opcional)",                  False),
        ("Nível Neuro Athena confirmado (Super)",             False),
        ("Supertrend do TF menor confirmando (Super)",        False),
        ("Risco/Retorno > 2:1",                              True),
    ]
    for label, required in items:
        badge = "<span class='rule-badge'>Obrigatório</span>" if required else \
                "<span class='rule-badge' style='background:#2d3748'>Opcional</span>"
        checked = st.checkbox(label, key=f"chk_{label}")
        icon = "✅" if checked else "⬜"
        st.markdown(f"""
        <div class='static-check {"checked" if checked else ""}'>
          {icon} {label} {badge}
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 3 — MÉTODO HOUGAARD
# ════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("### 📋 Método Hougaard")
    steps = [
        ("Identificar Tendência Macro", "Supertrend Mensal + EMAs Semanal → definir direcional"),
        ("Aguardar Pullback",           "Preço recuando para zona de EMA ou suporte/resistência chave"),
        ("Verificar RSI Canal",         "RSI tocando fundo/topo do canal no contra-fluxo da tendência"),
        ("Confirmar Stoch RSI",         "Stoch RSI saindo de zona de over em W1/D/4H"),
        ("Checar Athena",               "Preço próximo de Buy/Sell Entry do Neuro Athena"),
        ("Executar Entrada",            "Ordem a mercado ou limit no nível — SL abaixo do ST"),
        ("Gerenciar Trade",             "Parcial nos TP1/TP2, mover SL para BE, deixar correr ao TP3"),
    ]
    for i, (title, desc) in enumerate(steps):
        active = st.session_state.hougaard_step == i
        col_n, col_t = st.columns([1, 10])
        with col_n:
            if st.button(f"{i+1}", key=f"hstep_{i}"):
                st.session_state.hougaard_step = i if not active else -1
                st.rerun()
        with col_t:
            bg = "#1a2332" if active else "#161b22"
            st.markdown(f"""
            <div style='background:{bg};border:1px solid {"#3B8BD4" if active else "#30363d"};
                 border-radius:6px;padding:10px;margin-bottom:6px'>
              <b style='color:#c9d1d9'>{title}</b>
              {"<br><span style='color:#8b949e;font-size:13px'>" + desc + "</span>" if active else ""}
            </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 4 — SIMULADOR
# ════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown("### 🔬 Simulador de Confluência")

    c1, c2, c3 = st.columns(3)
    with c1:
        sim_sym = st.text_input("Par:", value="BTC-USD", key="sim_sym")
        sim_trend = st.radio("Tendência Macro:", ["Compra", "Venda", "Indefinida"])
    with c2:
        sim_rsi_touch = st.checkbox("RSI tocou canal (contra-fluxo)?")
        sim_ema_near  = st.checkbox("Preço próximo de EMA?")
        sim_athena    = st.checkbox("Nível Athena ativado?")
    with c3:
        sim_st_touch  = st.checkbox("Supertrend tocado?")
        sim_stoch_ok  = st.checkbox("Stoch RSI em zona extrema?")

    if st.button("🔎 Avaliar Setup"):
        score = 0
        msgs  = []
        if sim_trend != "Indefinida":
            score += 30
            msgs.append(("✅", f"Tendência macro: {sim_trend} (+30)"))
        else:
            msgs.append(("⚠️", "Tendência indefinida — aguardar"))

        if sim_rsi_touch: score += 25; msgs.append(("✅","RSI canal tocado (+25)"))
        if sim_ema_near:  score += 20; msgs.append(("✅","EMA próxima (+20)"))
        if sim_stoch_ok:  score += 10; msgs.append(("✅","Stoch confirmando (+10)"))
        if sim_athena:    score += 10; msgs.append(("⭐","Nível Athena (+10 → SUPER)"))
        if sim_st_touch:  score += 5;  msgs.append(("⭐","ST tocado (+5 → SUPER)"))

        for icon, msg in msgs:
            st.markdown(f"**{icon}** {msg}")

        color = "#1D9E75" if score >= 75 else "#E0A905" if score >= 50 else "#E04C4C"
        label = "SINAL SUPER ⭐" if score >= 85 and (sim_athena or sim_st_touch) else \
                "SINAL COMUM ✅" if score >= 75 else \
                "SETUP PARCIAL ⚠️" if score >= 50 else "AGUARDAR ❌"

        st.markdown(f"""
        <div style='background:rgba(0,0,0,0.3);border:2px solid {color};border-radius:10px;
             padding:20px;text-align:center;margin-top:16px'>
          <div style='font-size:32px;font-weight:bold;color:{color}'>{score}/100</div>
          <div style='font-size:18px;color:{color};margin-top:8px'>{label}</div>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# AUTO-REFRESH
# ════════════════════════════════════════════════════════════
if st.session_state.auto_update:
    time.sleep(60)
    st.cache_data.clear()
    st.rerun()
