"""
market_analysis_app.py
Replica fiel do notebook market_analysis_oop.ipynb (células 144–163).
Cada trace, sinal ativo/comentado e parâmetro exatamente como no notebook.

Rodar: streamlit run market_analysis_app.py
Deps:  pip install streamlit plotly yfinance pandas numpy
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import yfinance as yf
import time
from datetime import datetime
import json, os, html, requests

_TG_CFG          = os.path.join(os.path.expanduser("~"), ".montrezor_telegram.json")
_MA_SIGNALS_FILE  = os.path.join(os.path.expanduser("~"), ".montrezor_ma_signals.json")
_MA_COOLDOWN_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_ma_cooldown.json")
_MA_COOLDOWN_HOURS = 24   # mesmo sinal não reenvia por 24h

def _load_cooldown() -> dict:
    """Carrega sinais já enviados do disco — persiste entre reinicializações."""
    try:
        if os.path.exists(_MA_COOLDOWN_FILE):
            return json.load(open(_MA_COOLDOWN_FILE, encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_cooldown(data: dict):
    try:
        json.dump(data, open(_MA_COOLDOWN_FILE, "w", encoding="utf-8"), indent=2)
    except Exception:
        pass

def _is_cooldown(sig_key: str) -> bool:
    """Retorna True se o sinal ainda está em cooldown (não deve reenviar)."""
    cd = _load_cooldown()
    if sig_key not in cd:
        return False
    try:
        sent_at = pd.Timestamp(cd[sig_key])
        elapsed = (pd.Timestamp.now() - sent_at).total_seconds() / 3600
        return elapsed < _MA_COOLDOWN_HOURS
    except Exception:
        return False

def _mark_cooldown(sig_key: str):
    """Marca o sinal como enviado com timestamp atual."""
    cd = _load_cooldown()
    cd[sig_key] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    # Limpar entradas expiradas
    now = pd.Timestamp.now()
    cd = {k: v for k, v in cd.items()
          if (now - pd.Timestamp(v)).total_seconds() / 3600 < _MA_COOLDOWN_HOURS * 2}
    _save_cooldown(cd)

def _load_tg():
    try:
        if os.path.exists(_TG_CFG):
            c = json.load(open(_TG_CFG, encoding="utf-8"))
            return c.get("token","").strip(), str(c.get("chat_id","")).strip()
    except Exception:
        pass
    return "", ""

def _send_tg_ma(chart, direction, indicators):
    token, chat_id = _load_tg()
    if not token or not chat_id:
        return False
    try:
        e    = html.escape
        icon = "📈" if direction == "BUY" else "📉"
        ts   = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
        inds = " | ".join(indicators)
        msg  = (icon + " <b>MARKET ANALYSIS SIGNAL</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<b>Gráfico</b>: " + e(chart) + "\n"
                "<b>Direção</b>: " + e(direction) + "\n"
                "<b>Indicadores</b>: " + e(inds) + "\n"
                "<b>Hora</b>: " + ts + "\n\n"
                "Montrezor Market Analysis")
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        r   = requests.post(url, json={"chat_id":chat_id,"text":msg,"parse_mode":"HTML"}, timeout=10)
        if r.status_code == 200:
            return True
        requests.post(url, json={"chat_id":chat_id,"text":icon+" "+chart+" — "+direction+"\n"+inds+"\n"+ts}, timeout=10)
        return False
    except Exception:
        return False

def _log_ma_signal(chart, direction, indicators):
    try:
        logs = []
        if os.path.exists(_MA_SIGNALS_FILE):
            logs = json.load(open(_MA_SIGNALS_FILE, encoding="utf-8"))
        logs.insert(0, {"ts": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                        "chart": chart, "direction": direction, "indicators": indicators})
        json.dump(logs[:300], open(_MA_SIGNALS_FILE,"w",encoding="utf-8"), indent=2)
    except Exception:
        pass

def _load_ma_signals():
    try:
        if os.path.exists(_MA_SIGNALS_FILE):
            return json.load(open(_MA_SIGNALS_FILE, encoding="utf-8"))
    except Exception:
        pass
    return []

# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="MONTREZOR - Market Analysis", layout="wide",
                   page_icon="📊", initial_sidebar_state="expanded")

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


# ══════════════════════════════════════════════════════════════════════════════
# INDICADORES
# ══════════════════════════════════════════════════════════════════════════════
def _sma(s, p):  return s.rolling(p).mean()
def _ema(s, p):  return s.ewm(span=p, adjust=False).mean()

def calc_rsi(close, period=14):
    d = close.diff()
    g = d.clip(lower=0).rolling(period).mean()
    l = (-d.clip(upper=0)).rolling(period).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def calc_stochrsi(close, period=14, smooth=3):
    rsi  = calc_rsi(close, period)
    mn, mx = rsi.rolling(period).min(), rsi.rolling(period).max()
    k = 100 * (rsi - mn) / (mx - mn + 1e-10)
    return pd.DataFrame({"k": k, "d": k.rolling(smooth).mean()}, index=close.index)

def calc_bb_pct(close, window=20, std_dev=2.0):
    ma  = close.rolling(window).mean()
    std = close.rolling(window).std()
    return (close - (ma - std_dev * std)) / (2 * std_dev * std + 1e-10)

def calc_macd(close, fast=12, slow=26, sig=9):
    m = _ema(close, fast) - _ema(close, slow)
    s = _ema(m, sig)
    return pd.DataFrame({"macd": m, "signal": s, "histogram": m - s})

def calc_sharpe(close, period, window):
    r = close.pct_change()
    return (r.rolling(window).mean() / (r.rolling(window).std() + 1e-10)) * np.sqrt(period)

def calc_sortino(close, period, window):
    r  = close.pct_change()
    dn = r.clip(upper=0)
    return (r.rolling(window).mean() / (dn.rolling(window).std() + 1e-10)) * np.sqrt(period)


# ══════════════════════════════════════════════════════════════════════════════
# SIGNALS  — parâmetros EXATOS de cada célula
# ══════════════════════════════════════════════════════════════════════════════
def _cross_below(s, th):
    return (s < th) & (s.shift(1) <= th)
def _cross_above(s, th):
    return (s > th) & (s.shift(1) >= th)

# --- RSI ---
# BTC daily (BtcStrategy default: buy=30, sell=70)
def rsi_sig_btc_d(rsi, buy=30, sell=70):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# BTC weekly  cell 15: buy=20 sell=80
def rsi_sig_btc_w(rsi, buy=20, sell=80):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# BTC monthly cell 17: buy=25 sell=80
def rsi_sig_btc_m(rsi, buy=25, sell=80):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# SPY weekly  cell 19: buy=28 sell=85
def rsi_sig_spy_w(rsi, buy=28, sell=85):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# SPY monthly cell 21: buy=25 sell=80
def rsi_sig_spy_m(rsi, buy=25, sell=80):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# FOREX daily (BtcStrategy default: buy=30, sell=70)
def rsi_sig_fx_d(rsi, buy=30, sell=70):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# FOREX weekly cell 25: buy=20 sell=80
def rsi_sig_fx_w(rsi, buy=20, sell=80):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# FOREX monthly cell 27: buy=25 sell=80
def rsi_sig_fx_m(rsi, buy=25, sell=80):
    return _cross_below(rsi, buy), _cross_above(rsi, sell)

# --- StochRSI ---
# Default (buy=20 sell=80)
def stoch_sig(stoch, buy=20, sell=80):
    d = stoch["d"]
    return _cross_below(d, buy), _cross_above(d, sell)

# SPY weekly cell 35: buy=10 sell=90
def stoch_sig_spy_w(stoch, buy=10, sell=90):
    d = stoch["d"]
    return _cross_below(d, buy), _cross_above(d, sell)

# --- BB%B ---
# default: buy<=0 sell>=1
def bb_sig(bb, buy=0.0, sell=1.0):
    return _cross_below(bb, buy + 1e-9), _cross_above(bb, sell - 1e-9)

# monthly buy_threshold=0.1  (cells 49, 53, 59)
def bb_sig_monthly(bb, buy_th=0.1):
    return _cross_below(bb, buy_th), _cross_above(bb, 1.0 - 1e-9)

# --- MACD ---
def macd_sig(mdf):
    m, s = mdf["macd"], mdf["signal"]
    # notebook: buy==1 quando histogram vira positivo (macd cruza acima signal)
    buy  = (m > s) & (m.shift(1) <= s.shift(1))
    sell = (m < s) & (m.shift(1) >= s.shift(1))
    return buy, sell

# --- Sharpe ---
def sharpe_sig(sh, buy=-1.5, sell=2.0):
    return _cross_below(sh, buy), _cross_above(sh, sell)

# BTC monthly cell 81: buy=-2.0 sell=3.5
def sharpe_sig_btc_m(sh, buy=-2.0, sell=3.5):
    return _cross_below(sh, buy), _cross_above(sh, sell)

# SPY weekly cell 83: buy=-0.5 sell=2.19
def sharpe_sig_spy_w(sh, buy=-0.5, sell=2.19):
    return _cross_below(sh, buy), _cross_above(sh, sell)

# SPY monthly cell 85: buy=-0.5 sell=3.5
def sharpe_sig_spy_m(sh, buy=-0.5, sell=3.5):
    return _cross_below(sh, buy), _cross_above(sh, sell)

# FOREX monthly cell 91: buy=-0.5 sell=3.5
def sharpe_sig_fx_m(sh, buy=-0.5, sell=3.5):
    return _cross_below(sh, buy), _cross_above(sh, sell)

# --- Sortino ---
def sortino_sig(so, buy=-1.5, sell=5.2):
    return _cross_below(so, buy), _cross_above(so, sell)

# BTC monthly cell 97: buy=-1.5 sell=6.0
def sortino_sig_btc_m(so, buy=-1.5, sell=6.0):
    return _cross_below(so, buy), _cross_above(so, sell)

# SPY weekly  cell 99: buy=-0.7 sell=4.7
def sortino_sig_spy_w(so, buy=-0.7, sell=4.7):
    return _cross_below(so, buy), _cross_above(so, sell)

# SPY monthly cell 101: buy=-1.0 sell=6.5
def sortino_sig_spy_m(so, buy=-1.0, sell=6.5):
    return _cross_below(so, buy), _cross_above(so, sell)

# FOREX monthly cell 107: buy=-1.0 sell=6.5
def sortino_sig_fx_m(so, buy=-1.0, sell=6.5):
    return _cross_below(so, buy), _cross_above(so, sell)

# --- Sortino MA crossover (generate_ma_signals) ---
# ── Sinal de sobreextensão — Sharpe/Sortino esticados demais ────────────────
# Quando os indicadores disparam muito acima dos thresholds normais de venda,
# o ativo está em euforia/overextension — sinal de alerta de reversão iminente.
OVEREXT = {
    "BTC_SHARPE":  6.0,   # Sharpe mensal BTC acima de 6 → overextended
    "BTC_SORTINO": 8.0,   # Sortino mensal BTC acima de 8 → overextended
    "SPY_SHARPE":  6.0,   # Sharpe mensal SPY acima de 6 → overextended
    "SPY_SORTINO": 5.0,   # Sortino mensal SPY acima de 5 → overextended
}

def overextended_sig(series, threshold):
    """
    Retorna máscara booleana onde o valor da série excede o threshold.
    Usado para detectar Sharpe/Sortino em território de euforia.
    """
    try:
        return series >= threshold, series < threshold   # (alert_mask, clear_mask)
    except Exception:
        import pandas as pd
        empty = pd.Series(False, index=series.index)
        return empty, empty


def sortino_ma_sig(so, slow_sma, fast_sma):
    buy  = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))
    sell = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))
    return buy, sell

# --- Combined (weighted quantity_threshold) ---
def combined(sigs_b, sigs_s, weights, qty_th):
    w  = np.array(weights)
    bs = sum(b.astype(float) * w[i] for i, b in enumerate(sigs_b))
    ss = sum(s.astype(float) * w[i] for i, s in enumerate(sigs_s))
    return bs >= qty_th, ss >= qty_th

# --- Confirmed (both Sharpe AND Sortino agree) ---
def confirmed(sh_b, sh_s, so_b, so_s):
    return sh_b & so_b, sh_s & so_s

# --- Macro Signal (cell 141) ---
# BTC: SharpeSignal(default) + SortinoSignal(sell_th=4.9)
# SPY: SharpeSignal(buy=-0.5,sell=2.19) + SortinoSignal(buy=-0.7,sell=4.7)
# FX:  SharpeSignal(default) + SortinoSignal(buy=-0.7,sell=4.7)
def macro_sig_btc(sh, so):
    sh_b, sh_s = sharpe_sig(sh, -1.5, 2.0)
    so_b, so_s = sortino_sig(so, -1.5, 4.5)
    return sh_b & so_b, sh_s & so_s

def macro_sig_spy(sh, so):
    sh_b, sh_s = sharpe_sig_spy_w(sh, -0.5, 2.19)
    so_b, so_s = sortino_sig_spy_w(so, -0.7, 4.7)
    return sh_b & so_b, sh_s & so_s

def macro_sig_fx(sh, so):
    sh_b, sh_s = sharpe_sig(sh)
    so_b, so_s = sortino_sig_spy_w(so)   # buy=-0.7 sell=4.7 igual ao SPY macro
    return sh_b & so_b, sh_s & so_s


# ══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def _dl(symbol, period, interval):
    df = yf.download(symbol, period=period, interval=interval,
                     auto_adjust=True, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df

def load_all(fx_sym):
    specs = [
        ("btc_d",  "BTC-USD", "4y",  "1d"),
        ("btc_w",  "BTC-USD", "8y",  "1wk"),
        ("btc_m",  "BTC-USD", "8y",  "1mo"),
        ("spy_d",  "SPY",     "8y",  "1d"),
        ("spy_w",  "SPY",     "8y",  "1wk"),
        ("spy_m",  "SPY",     "8y",  "1mo"),
        ("fx_d",   fx_sym,    "8y",  "1d"),
        ("fx_w",   fx_sym,    "8y",  "1wk"),
        ("fx_m",   fx_sym,    "8y",  "1mo"),
        ("vix_w",  "^VIX",   "7y",  "1wk"),
        ("vix_m",  "^VIX",   "7y",  "1mo"),
    ]
    out = {}
    bar = st.progress(0, "Baixando dados…")
    for i, (k, sym, per, itv) in enumerate(specs):
        try:
            out[k] = _dl(sym, per, itv)
        except Exception as e:
            out[k] = pd.DataFrame()
            st.warning(f"Erro {sym} {itv}: {e}")
        bar.progress((i + 1) / len(specs), f"Baixando {sym} {itv}…")
    bar.empty()
    return out

def cl(df):
    """Série Close limpa."""
    if df.empty:
        return pd.Series(dtype=float)
    return df["Close"].squeeze().dropna()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE PLOTLY
# ══════════════════════════════════════════════════════════════════════════════
DARK = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#070B0F", xaxis_rangeslider_visible=False,
            font_family="JetBrains Mono", font_size=11,
            legend=dict(font_size=10, bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=0, r=0, t=36, b=0))

def _candle(fig, df, name, row=1):
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=name,
        increasing_line_color="#26a641", decreasing_line_color="#da3633",
    ), row=row, col=1)

def _mk(fig, idx, vals, mask, color, sym, name, row, size=10, opacity=0.7):
    if not isinstance(mask, pd.Series) or mask.sum() == 0:
        return
    sz = size if isinstance(size, (int, float)) else list(size)
    fig.add_trace(go.Scatter(
        x=idx[mask], y=vals[mask], mode="markers",
        marker=dict(size=sz, color=color, symbol=sym),
        showlegend=True, name=name, opacity=opacity,
    ), row=row, col=1)

def _ln(fig, s, color, name, row, w=2, opacity=1.0):
    if s is None or (hasattr(s, "empty") and s.empty):
        return
    fig.add_trace(go.Scatter(
        x=s.index, y=s, line=dict(color=color, width=w),
        showlegend=True, name=name, opacity=opacity,
    ), row=row, col=1)

def _bar(fig, s, name, row, opacity=0.7):
    if s is None or (hasattr(s, "empty") and s.empty):
        return
    fig.add_trace(go.Bar(
        x=s.index, y=s, marker_color=s,
        showlegend=True, name=name, opacity=opacity,
    ), row=row, col=1)

def _hl(fig, y, color, row):
    fig.add_hline(y=y, line_dash="dot", line_color=color, row=row, col=1)

def _upd(fig, height, title=None, showlegend=True):
    kw = {**DARK, "height": height, "showlegend": showlegend}
    if title:
        kw["title"] = title
    fig.update_layout(**kw)


# ══════════════════════════════════════════════════════════════════════════════
# BUILDERS — réplica célula a célula
# ══════════════════════════════════════════════════════════════════════════════

# ─── CELL 144 — BTC+SPY Macro Weekly ────────────────────────────────────────
def build_rr(A):
    df = A["btc_w"]
    if df.empty:
        return None
    c = cl(df)
    # BTC macro (cell 141)
    sh_btc = calc_sharpe(c, 52, 60)
    so_btc = calc_sortino(c, 52, 60)
    btc_mb, btc_ms = macro_sig_btc(sh_btc, so_btc)
    # SPY macro (cell 141)
    spy_c  = cl(A["spy_w"])
    sh_spy = calc_sharpe(spy_c, 52, 60)
    so_spy = calc_sortino(spy_c, 52, 60)
    spy_mb, spy_ms = macro_sig_spy(sh_spy, so_spy)
    spy_mb = spy_mb.reindex(c.index).fillna(False)
    spy_ms = spy_ms.reindex(c.index).fillna(False)

    fig = make_subplots(rows=1, cols=1, subplot_titles=("BTC-USD",))
    _candle(fig, df, "BTC-USD")
    _mk(fig, c.index, c, btc_mb, "#00BFFF", "triangle-left",  "BTC Buy Confirmed Weekly",  1, 12, 1.0)
    _mk(fig, c.index, c, btc_ms, "white",   "triangle-right", "BTC Sell Confirmed Weekly", 1, 12, 1.0)
    _mk(fig, c.index, c, spy_mb, "blue",    "arrow-up",       "SPY Buy Confirmed Weekly",  1, 12, 1.0)
    _mk(fig, c.index, c, spy_ms, "#FF00FF", "arrow-down",     "SPY Sell Confirmed Weekly", 1, 12, 1.0)
    _upd(fig, 800)
    return fig


# ─── CELL 147 — BTC Daily ────────────────────────────────────────────────────
def build_btc_d(A):
    df = A["btc_d"]
    if df.empty:
        return None
    c = cl(df)

    rsi  = calc_rsi(c, 14)
    sma20_rsi = _sma(rsi, 20)
    stoch = calc_stochrsi(c, 14, 3)
    bb    = calc_bb_pct(c, 20, 2)          # BtcStrategy default
    sma20_bb = _sma(bb, 20)
    macd  = calc_macd(c)
    sharpe = calc_sharpe(c, 252, 60)
    sortino= calc_sortino(c, 252, 60)
    so_sma_slow = _sma(sortino, 70)        # cell 93: ma_slow=70
    so_sma_fast = _sma(sortino, 20)        # cell 93: ma_fast=20

    # signals
    rsi_b,  rsi_s  = rsi_sig_btc_d(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig(bb)
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig(sharpe, sell=4.5)
    so_b,   so_s   = sortino_ma_sig(sortino, so_sma_slow, so_sma_fast)  # cell 93

    # combined cell 109: rsi+stochrsi+bb weights=[0.5,0.5,2.0] threshold=3.0
    comb_b, comb_s = combined([rsi_b,stch_b,bb_b], [rsi_s,stch_s,bb_s], [0.5,0.5,2.0], 3.0)
    # confirmed cell 125: sharpe+sortino weights=[0.5,0.5] threshold=1.0
    conf_b, conf_s = combined([sh_b,so_b], [sh_s,so_s], [0.5,0.5], 1.0)

    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.008,
        subplot_titles=("BTC-USD",), row_width=[1.0,1.0,1.0,1.0,1.0,2.0])

    # row 1 — candle + signals
    _candle(fig, df, "BTC-USD Daily")
    #_mk(fig, df.index, df["Close"], conf_b, "#00BFFF", "star",       "Buy Confirmed Daily",       1, 15, 1.0)
    #_mk(fig, df.index, df["Close"], conf_s, "#FFFF00", "star",       "Sell Confirmed Daily",      1, 15, 1.0)
    _mk(fig, df.index, df["Close"], comb_b, "blue",    "arrow-up",   "Buy Combined Daily Signals",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], comb_s, "red",     "arrow-down", "Sell Combined Daily Signals", 1, 15, 1.0)
    # (MACD daily on row1 is commented out in notebook — não plotado)

    # row 2 — RSI
    _ln(fig, rsi, "lightblue", "RSI Daily", 2)
    _mk(fig, rsi.index, rsi, rsi_b, "green", "triangle-up",   "RSI Buy Daily Signals",  2, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",   "triangle-down", "RSI Sell Daily Signals", 2, 10)
    _ln(fig, sma20_rsi, "orange", "RSI SMA 20 Daily", 2, w=2, opacity=0.7)
    for y, col in [(20,"lightgreen"),(50,"gray"),(80,"lightcoral")]:
        _hl(fig, y, col, 2)

    # row 3 — StochRSI
    _ln(fig, stoch["d"], "lightcoral", "StochRSI d Daily", 3)
    _ln(fig, stoch["k"], "lightblue",  "StochRSI K Daily", 3)   # notebook usa stochrsi_daily_values (k)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green", "triangle-up",   "StochRSI Buy Daily Signals",  3, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",   "triangle-down", "StochRSI Sell Daily Signals", 3, 10)
    _ln(fig, rsi, "lightblue", "RSI Daily", 3)     # notebook plota RSI novamente na row3
    for y, col in [(5,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 3)

    # row 4 — BB%B
    _ln(fig, bb, "lightblue", "BB %B Daily", 4)
    _mk(fig, bb.index, bb, bb_b, "green", "triangle-up",   "BB Buy Daily Signals",  4, 10)
    _mk(fig, bb.index, bb, bb_s, "red",   "triangle-down", "BB Sell Daily Signals", 4, 10)
    _ln(fig, sma20_bb, "orange", "BB SMA 20 Daily", 4, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 4)

    # row 5 — MACD
    _ln(fig, macd["macd"],    "lightblue", "MACD Daily",          5, w=1)
    _ln(fig, macd["signal"],  "red",       "MACD Signal Daily",   5, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram Daily", 5)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green", "triangle-up",   "MACD Buy Signals Daily",  5, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",   "triangle-down", "MACD Sell Signals Daily", 5, 12)

    # row 6 — Sharpe + Sortino
    _ln(fig, sharpe, "lightblue", "Sharpe", 6, w=1)
    sz_shb = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_shs = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    _mk(fig, sharpe.index, sharpe, sh_b, "green", "circle", "Sharpe Buy Signals Daily",  6, sz_shb, 0.5)
    _mk(fig, sharpe.index, sharpe, sh_s, "red",   "circle", "Sharpe Sell Signals Daily", 6, sz_shs, 0.7)
    # (Sharpe SMA20 comentado no notebook — não plotado)
    _bar(fig, sortino, "Sortino", 6)
    _mk(fig, sortino.index, sortino, so_b, "green", "triangle-up",   "Sortino Buy Signals Daily",  6, 10)
    _mk(fig, sortino.index, sortino, so_s, "red",   "triangle-down", "Sortino Sell Signals Daily", 6, 10)
    _ln(fig, so_sma_slow, "#00E5FF", "Sortino SMA 14 Daily", 6)
    _ln(fig, so_sma_fast, "#D60000", "Sortino SMA 7 Daily",  6)

    _upd(fig, 1150, showlegend=False)
    return fig


# ─── CELL 149 — BTC Weekly ───────────────────────────────────────────────────
def build_btc_w(A):
    df = A["btc_w"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma20  = _sma(rsi, 20)
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 30, 2)       # window=30 cell 47
    sma20_bb = _sma(bb, 20)
    macd   = calc_macd(c)
    sharpe = calc_sharpe(c, 52, 60)
    sortino= calc_sortino(c, 52, 60)
    so14   = _sma(sortino, 14)
    so7    = _sma(sortino, 7)

    rsi_b,  rsi_s  = rsi_sig_btc_w(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig(bb)
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig(sharpe)
    so_b,   so_s   = sortino_sig(sortino)

    # confirmed cell 127: Sharpe(buy=-1.5,sell=2.1)+Sortino(buy=-1.7,sell=4.7) qty=2
    sh_b2, sh_s2 = sharpe_sig(sharpe, -1.5, 2.1)
    so_b2, so_s2 = sortino_sig(sortino, -1.7, 4.7)
    conf_b, conf_s = confirmed(sh_b2, sh_s2, so_b2, so_s2)

    # combined cell 111: bb+stochrsi+rsi w=[1,1,1] th=3
    comb_b, comb_s = combined([bb_b,stch_b,rsi_b],[bb_s,stch_s,rsi_s],[1,1,1],3.0)
    # (combined comentado no notebook — não plotado no candle)

    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.0008,
        subplot_titles=("BTC-USD",), row_width=[1.0,1.0,1.0,1.0,1.0,2.0])

    _candle(fig, df, "BTC-USD")
    _mk(fig, df.index, df["Close"], conf_b, "#00BFFF", "star", "Buy Confirmed Weekly",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], conf_s, "#FFFF00", "star", "Sell Confirmed Weekly", 1, 15, 1.0)
    # (buy_combined, MACD buy/sell no row1 comentados no notebook)

    _ln(fig, rsi, "lightblue", "RSI", 2)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "RSI Buy Signals",  2, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "RSI Sell Signals", 2, 10)
    _ln(fig, sma20, "orange", "SMA 20", 2, w=2, opacity=0.7)
    for y, col in [(20,"lightgreen"),(50,"gray"),(80,"lightcoral")]:
        _hl(fig, y, col, 2)

    _ln(fig, stoch["d"], "lightcoral", "StochRSI d", 3)
    _ln(fig, rsi, "lightblue", "RSI", 3)      # notebook plota RSI junto
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "StochRSI Buy Signals",  3, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "StochRSI Sell Signals", 3, 10)
    for y, col in [(5,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 3)

    _ln(fig, bb, "lightblue", "BB", 4)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "BB Buy Signals",  4, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "BB Sell Signals", 4, 10)
    _ln(fig, sma20_bb, "orange", "BB SMA 20", 4, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 4)

    _ln(fig, macd["macd"],   "lightblue","MACD",           5, w=1)
    _ln(fig, macd["signal"], "red",       "MACD Signal",   5, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram", 5)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green","triangle-up",   "MACD Buy Signals",  5, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",  "triangle-down", "MACD Sell Signals", 5, 12)

    _ln(fig, sharpe, "lightblue", "Sharpe", 6, w=1)
    sz_b = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    _mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Sharpe Buy Signals",  6, sz_b, 0.5)
    _mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Sharpe Sell Signals", 6, sz_s, 0.7)
    # (Sharpe SMA20 comentado)
    _bar(fig, sortino, "Sortino", 6)
    sz_ob = list(sortino[so_b].abs() * 5) if so_b.sum() > 0 else 6
    sz_os = list(sortino[so_s].abs() * 3) if so_s.sum() > 0 else 6
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Sortino Buy Signals",  6, sz_ob)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Sortino Sell Signals", 6, sz_os)
    _ln(fig, so14, "#00E5FF", "Sortino SMA 14", 6)
    _ln(fig, so7,  "#D60000", "Sortino SMA 7",  6)
    # (VIX comentado no notebook)

    _upd(fig, 1150)
    return fig


# ─── CELL 151 — BTC Monthly ──────────────────────────────────────────────────
def build_btc_m(A):
    df = A["btc_m"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma16  = _sma(rsi, 16)               # cell 17: SMA=16
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 20, 2)
    sma20_bb = _sma(bb, 20)
    macd   = calc_macd(c)
    sharpe = calc_sharpe(c, 12, 6)       # cell 81: period=12, window=6
    sortino= calc_sortino(c, 12, 14)     # cell 97: period=12, window=14
    so_s14 = _sma(sortino, 5)            # cell 97: SMA slow=5
    so_s7  = _sma(sortino, 3)            # cell 97: SMA fast=3

    rsi_b,  rsi_s  = rsi_sig_btc_m(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig_monthly(bb, 0.1)   # cell 49: buy_threshold=0.1
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig_btc_m(sharpe)  # buy=-2.0 sell=3.5
    so_b,   so_s   = sortino_sig_btc_m(sortino)# buy=-1.5 sell=6.0

    # combined cell 113: rsi+stochrsi+bb w=[1,0.5,1] th=2
    comb_b, comb_s = combined([rsi_b,stch_b,bb_b],[rsi_s,stch_s,bb_s],[1.0,0.5,1.0],2.0)
    # confirmed cell 129: Sharpe(-1.5/3.5)+Sortino(-1.5/5.0)
    sh_cb, sh_cs = sharpe_sig(sharpe, -1.5, 3.5)
    so_cb, so_cs = sortino_sig(sortino, -1.5, 5.0)
    conf_b, conf_s = confirmed(sh_cb, sh_cs, so_cb, so_cs)

    specs = [[{"secondary_y": True}]] * 6
    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.008,
        specs=specs, subplot_titles=("BTC-USD",),
        row_width=[1.0]*6)

    # row 1 — candle + signals (todos ativos no notebook)
    _candle(fig, df, "BTC-USD")
    _mk(fig, df.index, df["Close"], conf_b, "#00BFFF","star",       "Buy Very Strong Signals",   1, 15, 1.0)
    _mk(fig, df.index, df["Close"], conf_s, "#FFFF00","star",       "Sell Very Strong Signals",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], comb_b, "blue",   "arrow-up",   "Buy Strong Signals",        1, 10, 0.7)
    _mk(fig, df.index, df["Close"], comb_s, "red",    "arrow-down", "Sell Strong Signals",       1, 10, 0.7)
    _mk(fig, df.index, df["Close"], macd_b, "#4CAF50","arrow-up",   "MACD Buy Signals Monthly",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], macd_s, "#FF0000","arrow-down", "MACD Sell Signals Monthly", 1, 15, 1.0)

    # row 2 — Sharpe + Sortino
    _ln(fig, sharpe, "lightblue", "Sharpe", 2, w=1)
    sz_b = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    _mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Sharpe Buy Signals",  2, sz_b, 0.5)
    _mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Sharpe Sell Signals", 2, sz_s, 0.7)
    # (Sharpe SMA14 comentado)
    _bar(fig, sortino, "Sortino", 2)
    sz_ob = list(sortino[so_b].abs() * 5) if so_b.sum() > 0 else 6
    sz_os = list(sortino[so_s].abs() * 3) if so_s.sum() > 0 else 6
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Sortino Buy Signals",  2, sz_ob)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Sortino Sell Signals", 2, sz_os)
    _ln(fig, so_s14, "#00E5FF", "Sortino SMA 14", 2)
    _ln(fig, so_s7,  "#D60000", "Sortino SMA 7",  2)

    # row 3 — RSI
    _ln(fig, rsi, "lightblue", "RSI", 3)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "RSI Buy Signals",  3, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "RSI Sell Signals", 3, 10)
    _ln(fig, sma16, "orange", "RSI SMA 20", 3, w=2, opacity=0.7)
    for y, col in [(20,"lightgreen"),(50,"gray"),(80,"lightcoral")]:
        _hl(fig, y, col, 3)

    # row 4 — StochRSI
    _ln(fig, stoch["d"], "lightcoral", "StochRSI d", 4)
    _ln(fig, rsi, "lightblue", "StochRSI", 4)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "StochRSI Buy Signals",  4, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "StochRSI Sell Signals", 4, 10)
    for y, col in [(10,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 4)

    # row 5 — BB%B
    _ln(fig, bb, "lightblue", "BB%B", 5)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "BB Buy Signals",  5, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "BB Sell Signals", 5, 10)
    _ln(fig, sma20_bb, "orange", "BB SMA 20", 5, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 5)

    # row 6 — MACD
    _ln(fig, macd["macd"],   "lightblue","MACD",         6, w=1)
    _ln(fig, macd["signal"], "red",       "MACD Signal", 6, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram", 6)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green","triangle-up",   "MACD Buy Signals",  6, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",  "triangle-down", "MACD Sell Signals", 6, 12)

    _upd(fig, 1200, "BTC-USD Monthly")
    return fig


# ─── CELL 153 — SPY Weekly ───────────────────────────────────────────────────
def build_spy_w(A):
    df = A["spy_w"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma20  = _sma(rsi, 20)
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 30, 2)        # window=30 cell 51
    sma20_bb = _sma(bb, 20)
    sharpe = calc_sharpe(c, 52, 60)
    sortino= calc_sortino(c, 52, 60)
    sma20_sh = _sma(sharpe, 20)
    so14   = _sma(sortino, 14)
    so7    = _sma(sortino, 7)
    vix_w  = cl(A["vix_w"])
    vix9   = _ema(vix_w, 9)  if not vix_w.empty else None
    vix20  = _ema(vix_w, 20) if not vix_w.empty else None

    rsi_b,  rsi_s  = rsi_sig_spy_w(rsi)
    stch_b, stch_s = stoch_sig_spy_w(stoch)   # buy=10 sell=90  cell 35
    bb_b,   bb_s   = bb_sig(bb)
    sh_b,   sh_s   = sharpe_sig_spy_w(sharpe)  # buy=-0.5 sell=2.19
    so_b,   so_s   = sortino_sig_spy_w(sortino) # buy=-0.7 sell=4.7

    # (Candle + Confirmed + Combined comentados no notebook — NÃO plotados)

    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.0008,
        subplot_titles=("SPY Weekly",), row_width=[1.0]*5)

    # row 1 — RSI (candle comentado)
    _ln(fig, rsi, "lightblue", "RSI", 1)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "Spy RSI Buy Signals",  1, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "Spy RSI Sell Signals", 1, 10)
    _ln(fig, sma20, "orange", "SMA 20", 1, w=2, opacity=0.7)
    for y, col in [(80,"lightgreen"),(50,"gray"),(30,"lightcoral")]:
        _hl(fig, y, col, 1)

    # row 2 — StochRSI
    _ln(fig, rsi, "lightblue", "RSI", 2)
    _ln(fig, stoch["d"], "lightcoral", "Spy StochRSI d", 2)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "Spy StochRSI Buy Signals",  2, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "Spy StochRSI Sell Signals", 2, 10)
    for y, col in [(80,"lightgreen"),(50,"gray"),(20,"lightcoral")]:
        _hl(fig, y, col, 2)

    # row 3 — BB%B
    _ln(fig, bb, "lightblue", "BB", 3)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "Spy BB Buy Signals",  3, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "Spy BB Sell Signals", 3, 10)
    _ln(fig, sma20_bb, "orange", "BB SMA 20", 3, w=2, opacity=0.7)  # notebook usa fig_btc_weekly (bug original - portamos na fig_spy_weekly)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 3)
    # (MACD comentado no notebook)

    # row 4 — Sharpe + Sortino
    _ln(fig, sharpe, "lightblue", "Sharpe", 4, w=1)
    sz_b = list(sharpe[sh_b].abs() * 15) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4)  if sh_s.sum() > 0 else 6
    _mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Spy Sharpe Buy Signals",  4, sz_b, 0.5)
    _mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Spy Sharpe Sell Signals", 4, sz_s, 0.7)
    _ln(fig, sma20_sh, "purple", "Spy Sharpe SMA 20", 4, w=2, opacity=0.7)
    _bar(fig, sortino, "Sortino", 4)
    sz_ob = list(sortino[so_b].abs() * 5) if so_b.sum() > 0 else 6
    sz_os = list(sortino[so_s].abs() * 3) if so_s.sum() > 0 else 6
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Spy Sortino Buy Signals",  4, sz_ob)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Spy Sortino Sell Signals", 4, sz_os)
    _ln(fig, so14, "#00E5FF", "Spy Sortino SMA 14", 4)
    _ln(fig, so7,  "#D60000", "Spy Sortino SMA 7",  4)

    # row 5 — VIX (ativo no notebook)
    if not vix_w.empty:
        _bar(fig, vix_w, "VIX", 5)
        if vix9 is not None:
            fig.add_trace(go.Scatter(x=vix9.index, y=vix9, name="VIX SMA 9",
                                     line=dict(color="orange"), opacity=0.7), row=5, col=1)
        if vix20 is not None:
            fig.add_trace(go.Scatter(x=vix20.index, y=vix20, name="VIX SMA 50",
                                     line=dict(color="lightgreen")), row=5, col=1)

    _upd(fig, 1000)
    return fig


# ─── CELL 155 — SPY Monthly ──────────────────────────────────────────────────
def build_spy_m(A):
    df = A["spy_m"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma9   = _sma(rsi, 9)                 # cell 21: SMA=9
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 20, 2)
    sma9_bb = _sma(bb, 9)                 # cell 53: SMA=9
    macd   = calc_macd(c)
    sharpe = calc_sharpe(c, 12, 6)
    sortino= calc_sortino(c, 12, 20)      # cell 101: window=20
    so5    = _sma(sortino, 5)
    so3    = _sma(sortino, 3)
    vix_m  = cl(A["vix_m"])
    vix7   = _ema(vix_m, 7)  if not vix_m.empty else None
    vix14  = _ema(vix_m, 14) if not vix_m.empty else None

    rsi_b,  rsi_s  = rsi_sig_spy_m(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig_monthly(bb, 0.1)
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig_spy_m(sharpe)
    so_b,   so_s   = sortino_sig_spy_m(sortino)

    # (candle + signals on row1 comentados no notebook)

    specs = [[{"secondary_y": True}]] * 6
    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.008,
        specs=specs, subplot_titles=("Spy Monthly",),
        row_width=[1.0,1.0,1.0,1.0,1.0,2.0])

    # row 1 — Sharpe + Sortino (candle comentado)
    _ln(fig, sharpe, "lightblue", "Sharpe", 1, w=1)
    sz_b = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    _mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Sharpe Buy Signals",  1, sz_b, 0.5)
    _mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Sharpe Sell Signals", 1, sz_s, 0.7)
    # (Sharpe SMA14 comentado)
    _bar(fig, sortino, "Sortino", 1)
    sz_ob = list(sortino[so_b].abs() * 5) if so_b.sum() > 0 else 6
    sz_os = list(sortino[so_s].abs() * 3) if so_s.sum() > 0 else 6
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Sortino Buy Signals",  1, sz_ob)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Sortino Sell Signals", 1, sz_os)
    _ln(fig, so5, "#00E5FF", "Sortino SMA 14", 1)
    _ln(fig, so3, "#D60000", "Sortino SMA 7",  1)

    # row 2 — RSI
    _ln(fig, rsi, "lightblue", "RSI", 2)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "RSI Buy Signals",  2, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "RSI Sell Signals", 2, 10)
    _ln(fig, sma9, "orange", "RSI SMA 20", 2, w=2, opacity=0.7)
    for y, col in [(20,"lightgreen"),(50,"gray"),(80,"lightcoral")]:
        _hl(fig, y, col, 2)

    # row 3 — StochRSI
    _ln(fig, stoch["d"], "lightcoral", "StochRSI d", 3)
    _ln(fig, rsi, "lightblue", "StochRSI", 3)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "StochRSI Buy Signals",  3, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "StochRSI Sell Signals", 3, 10)
    for y, col in [(10,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 3)

    # row 4 — BB%B
    _ln(fig, bb, "lightblue", "BB%B", 4)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "BB Buy Signals",  4, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "BB Sell Signals", 4, 10)
    _ln(fig, sma9_bb, "orange", "BB SMA 20", 4, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 4)

    # row 5 — MACD
    _ln(fig, macd["macd"],   "lightblue","MACD",         5, w=1)
    _ln(fig, macd["signal"], "red",       "MACD Signal", 5, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram", 5)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green","triangle-up",   "MACD Buy Signals",  5, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",  "triangle-down", "MACD Sell Signals", 5, 12)

    # row 6 — VIX
    if not vix_m.empty:
        _bar(fig, vix_m, "VIX", 6)
        if vix7 is not None:
            fig.add_trace(go.Scatter(x=vix7.index,  y=vix7,  name="VIX SMA 7",
                                     line=dict(color="orange"), opacity=0.7), row=6, col=1)
        if vix14 is not None:
            fig.add_trace(go.Scatter(x=vix14.index, y=vix14, name="VIX SMA 14",
                                     line=dict(color="lightgreen")), row=6, col=1)

    _upd(fig, 1200, "SPY Monthly")
    return fig


# ─── CELL 157 — FOREX Daily ──────────────────────────────────────────────────
def build_fx_d(A, sym):
    df = A["fx_d"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma20  = _sma(rsi, 20)
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 20, 2)
    sma20_bb = _sma(bb, 20)
    macd   = calc_macd(c)
    sharpe = calc_sharpe(c, 252, 60)
    sortino= calc_sortino(c, 252, 60)
    so_slow = _sma(sortino, 100)    # cell 103: ma_slow=100
    so_fast = _sma(sortino, 50)     # cell 103: ma_fast=50

    rsi_b,  rsi_s  = rsi_sig_fx_d(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig(bb)
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig(sharpe)
    so_b,   so_s   = sortino_ma_sig(sortino, so_slow, so_fast)

    # combined cell 119: rsi+stochrsi+bb w=[0.5,0.5,2.0] th=3.0
    comb_b, comb_s = combined([rsi_b,stch_b,bb_b],[rsi_s,stch_s,bb_s],[0.5,0.5,2.0],3.0)
    # (confirmed comentado no notebook)

    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.008,
        subplot_titles=(sym,), row_width=[1.0,1.0,1.0,1.0,1.0,2.0])

    _candle(fig, df, sym)
    # (confirmed comentado)
    _mk(fig, df.index, df["Close"], comb_b, "blue","arrow-up",   "Buy Combined Daily Signals",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], comb_s, "red", "arrow-down", "Sell Combined Daily Signals", 1, 15, 1.0)

    _ln(fig, rsi, "lightblue", "RSI Daily", 2)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "RSI Buy Daily Signals",  2, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "RSI Sell Daily Signals", 2, 10)
    _ln(fig, sma20, "orange", "RSI SMA 20 Daily", 2, w=2, opacity=0.7)
    for y, col in [(20,"lightgreen"),(50,"gray"),(80,"lightcoral")]:
        _hl(fig, y, col, 2)

    _ln(fig, stoch["d"], "lightcoral", "StochRSI d Daily", 3)
    _ln(fig, stoch["k"], "lightblue",  "StochRSI K Daily", 3)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "StochRSI Buy Daily Signals",  3, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "StochRSI Sell Daily Signals", 3, 10)
    _ln(fig, rsi, "lightblue", "RSI Daily", 3)
    for y, col in [(5,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 3)

    _ln(fig, bb, "lightblue", "BB %B Daily", 4)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "BB Buy Daily Signals",  4, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "BB Sell Daily Signals", 4, 10)
    _ln(fig, sma20_bb, "orange", "BB SMA 20 Daily", 4, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 4)

    _ln(fig, macd["macd"],   "lightblue","MACD Daily",          5, w=1)
    _ln(fig, macd["signal"], "red",       "MACD Signal Daily",  5, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram Daily", 5)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green","triangle-up",   "MACD Buy Signals Daily",  5, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",  "triangle-down", "MACD Sell Signals Daily", 5, 12)

    _ln(fig, sharpe, "lightblue", "Sharpe", 6, w=1)
    sz_b = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    #_mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Sharpe Buy Signals Daily",  6, sz_b, 0.5)
    #_mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Sharpe Sell Signals Daily", 6, sz_s, 0.7)
    _bar(fig, sortino, "Sortino", 6)
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Sortino Buy Signals Daily",  6, 15)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Sortino Sell Signals Daily", 6, 15)
    _ln(fig, so_slow, "#00E5FF", "Sortino SMA Slow Daily", 6)
    _ln(fig, so_fast, "#D60000", "Sortino SMA Fast Daily", 6)

    _upd(fig, 1150, showlegend=False)
    return fig


# ─── CELL 159 — FOREX Weekly ─────────────────────────────────────────────────
def build_fx_w(A, sym):
    df = A["fx_w"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma20  = _sma(rsi, 20)
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 30, 2)        # window=30 cell 57
    sma20_bb = _sma(bb, 20)
    macd   = calc_macd(c)
    sharpe = calc_sharpe(c, 52, 60)
    sortino= calc_sortino(c, 52, 60)
    so_slow = _sma(sortino, 14)           # cell 105: ma_slow=14
    so_fast = _sma(sortino, 7)            # cell 105: ma_fast=7

    rsi_b,  rsi_s  = rsi_sig_fx_w(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig(bb)
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig(sharpe)
    so_b,   so_s   = sortino_ma_sig(sortino, so_slow, so_fast)

    # (confirmed e combined comentados no notebook)

    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.0008,
        subplot_titles=(sym,), row_width=[1.0,1.0,1.0,1.0,1.0,2.0])

    _candle(fig, df, sym)
    # (confirmed/combined comentados)

    _ln(fig, rsi, "lightblue", "RSI", 2)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "RSI Buy Signals",  2, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "RSI Sell Signals", 2, 10)
    _ln(fig, sma20, "orange", "SMA 20", 2, w=2, opacity=0.7)
    for y, col in [(80,"lightgreen"),(50,"gray"),(30,"lightcoral")]:
        _hl(fig, y, col, 2)

    _ln(fig, stoch["d"], "lightcoral", "StochRSI d", 3)
    _ln(fig, rsi, "lightblue", "RSI", 3)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "StochRSI Buy Signals",  3, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "StochRSI Sell Signals", 3, 10)
    for y, col in [(5,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 3)

    _ln(fig, bb, "lightblue", "BB", 4)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "BB Buy Signals",  4, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "BB Sell Signals", 4, 10)
    _ln(fig, sma20_bb, "orange", "BB SMA 20", 4, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 4)

    _ln(fig, macd["macd"],   "lightblue","MACD",         5, w=1)
    _ln(fig, macd["signal"], "red",       "MACD Signal", 5, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram", 5)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green","triangle-up",   "MACD Buy Signals",  5, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",  "triangle-down", "MACD Sell Signals", 5, 12)

    _ln(fig, sharpe, "lightblue", "Sharpe", 6, w=1)
    sz_b = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    _mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Sharpe Buy Signals",  6, sz_b, 0.5)
    _mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Sharpe Sell Signals", 6, sz_s, 0.7)
    _bar(fig, sortino, "Sortino", 6)
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Sortino Buy Signals",  6, 15)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Sortino Sell Signals", 6, 15)
    _ln(fig, so_slow, "#00E5FF", "Sortino SMA Slow", 6)
    _ln(fig, so_fast, "#D60000", "Sortino SMA Fast", 6)

    _upd(fig, 1150)
    return fig


# ─── CELL 161 — FOREX Monthly ────────────────────────────────────────────────
def build_fx_m(A, sym):
    df = A["fx_m"]
    if df.empty:
        return None
    c = cl(df)

    rsi    = calc_rsi(c, 14)
    sma9   = _sma(rsi, 9)                  # cell 27: SMA=9
    stoch  = calc_stochrsi(c, 14, 3)
    bb     = calc_bb_pct(c, 20, 2)
    sma9_bb = _sma(bb, 9)                  # cell 59: SMA=9
    macd   = calc_macd(c)
    sharpe = calc_sharpe(c, 12, 6)
    sortino= calc_sortino(c, 12, 20)       # cell 107: window=20
    so_slow = _sma(sortino, 5)             # cell 107: ma_slow=5
    so_fast = _sma(sortino, 3)             # cell 107: ma_fast=3

    rsi_b,  rsi_s  = rsi_sig_fx_m(rsi)
    stch_b, stch_s = stoch_sig(stoch)
    bb_b,   bb_s   = bb_sig_monthly(bb, 0.1)   # cell 59
    macd_b, macd_s = macd_sig(macd)
    sh_b,   sh_s   = sharpe_sig_fx_m(sharpe)   # buy=-0.5 sell=3.5
    so_b,   so_s   = sortino_ma_sig(sortino, so_slow, so_fast)

    # combined cell 123: rsi+stochrsi+bb w=[1,0.5,1] th=2
    comb_b, comb_s = combined([rsi_b,stch_b,bb_b],[rsi_s,stch_s,bb_s],[1.0,0.5,1.0],2.0)
    # confirmed cell 139: Sharpe(default)+Sortino(default)
    sh_cb, sh_cs = sharpe_sig(sharpe)
    so_cb, so_cs = sortino_sig(sortino)
    conf_b, conf_s = confirmed(sh_cb, sh_cs, so_cb, so_cs)

    specs = [[{"secondary_y": True}]] * 6
    fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.008,
        specs=specs, subplot_titles=(sym,), row_width=[1.0]*6)

    # row 1 — candle + all signals (todos ativos)
    _candle(fig, df, sym)
    _mk(fig, df.index, df["Close"], conf_b, "#00BFFF","star",       "Buy Very Strong Signals",   1, 15, 1.0)
    _mk(fig, df.index, df["Close"], conf_s, "#FFFF00","star",       "Sell Very Strong Signals",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], comb_b, "blue",   "arrow-up",   "Buy Strong Signals",        1, 10, 0.7)
    _mk(fig, df.index, df["Close"], comb_s, "red",    "arrow-down", "Sell Strong Signals",       1, 10, 0.7)
    _mk(fig, df.index, df["Close"], macd_b, "#4CAF50","arrow-up",   "MACD Buy Signals Monthly",  1, 15, 1.0)
    _mk(fig, df.index, df["Close"], macd_s, "#FF0000","arrow-down", "MACD Sell Signals Monthly", 1, 15, 1.0)

    # row 2 — Sharpe + Sortino
    _ln(fig, sharpe, "lightblue", "Sharpe", 2, w=1)
    sz_b = list(sharpe[sh_b].abs() * 7) if sh_b.sum() > 0 else 6
    sz_s = list(sharpe[sh_s].abs() * 4) if sh_s.sum() > 0 else 6
    #_mk(fig, sharpe.index, sharpe, sh_b, "green","circle","Sharpe Buy Signals",  2, sz_b, 0.5)
    #_mk(fig, sharpe.index, sharpe, sh_s, "red",  "circle","Sharpe Sell Signals", 2, sz_s, 0.7)
    _bar(fig, sortino, "Sortino", 2)
    _mk(fig, sortino.index, sortino, so_b, "green","triangle-up",   "Sortino Buy Signals",  2, 15)
    _mk(fig, sortino.index, sortino, so_s, "red",  "triangle-down", "Sortino Sell Signals", 2, 15)
    _ln(fig, so_slow, "#00E5FF", "Sortino SMA Slow", 2)
    _ln(fig, so_fast, "#D60000", "Sortino SMA Fast", 2)

    # row 3 — RSI
    _ln(fig, rsi, "lightblue", "RSI", 3)
    _mk(fig, rsi.index, rsi, rsi_b, "green","triangle-up",   "RSI Buy Signals",  3, 10)
    _mk(fig, rsi.index, rsi, rsi_s, "red",  "triangle-down", "RSI Sell Signals", 3, 10)
    _ln(fig, sma9, "orange", "RSI SMA 20", 3, w=2, opacity=0.7)
    for y, col in [(20,"lightgreen"),(50,"gray"),(80,"lightcoral")]:
        _hl(fig, y, col, 3)

    # row 4 — StochRSI
    _ln(fig, stoch["d"], "lightcoral", "StochRSI d", 4)
    _ln(fig, rsi, "lightblue", "StochRSI", 4)
    _mk(fig, stoch["d"].index, stoch["d"], stch_b, "green","triangle-up",   "StochRSI Buy Signals",  4, 10)
    _mk(fig, stoch["d"].index, stoch["d"], stch_s, "red",  "triangle-down", "StochRSI Sell Signals", 4, 10)
    for y, col in [(10,"lightgreen"),(50,"gray"),(90,"lightcoral")]:
        _hl(fig, y, col, 4)

    # row 5 — BB%B
    _ln(fig, bb, "lightblue", "BB%B", 5)
    _mk(fig, bb.index, bb, bb_b, "green","triangle-up",   "BB Buy Signals",  5, 10)
    _mk(fig, bb.index, bb, bb_s, "red",  "triangle-down", "BB Sell Signals", 5, 10)
    _ln(fig, sma9_bb, "orange", "BB SMA 20", 5, w=2, opacity=0.7)
    for y, col in [(0,"lightgreen"),(0.5,"gray"),(1,"lightcoral")]:
        _hl(fig, y, col, 5)

    # row 6 — MACD
    _ln(fig, macd["macd"],   "lightblue","MACD",         6, w=1)
    _ln(fig, macd["signal"], "red",       "MACD Signal", 6, w=1, opacity=0.7)
    _bar(fig, macd["histogram"], "MACD Histogram", 6)
    _mk(fig, macd["macd"].index, macd["macd"], macd_b, "green","triangle-up",   "MACD Buy Signals",  6, 12)
    _mk(fig, macd["macd"].index, macd["macd"], macd_s, "red",  "triangle-down", "MACD Sell Signals", 6, 12)

    _upd(fig, 1200, "FOREX Monthly")
    return fig


# ─── CELL 163 — FOREX Macro Weekly ──────────────────────────────────────────
def build_fx_macro(A, sym):
    df = A["fx_w"]
    if df.empty:
        return None
    c  = cl(df)
    sh = calc_sharpe(c, 52, 60)
    so = calc_sortino(c, 52, 60)
    mb, ms = macro_sig_fx(sh, so)    # cell 141: Sharpe default + Sortino buy=-0.7 sell=4.7

    fig = make_subplots(rows=1, cols=1, subplot_titles=("FOREX-USD",))
    _candle(fig, df, sym)
    _mk(fig, df.index, df["Close"], mb, "#00BFFF","triangle-left",  "FOREX Buy Confirmed Weekly",  1, 12, 1.0)
    _mk(fig, df.index, df["Close"], ms, "white",  "triangle-right", "FOREX Sell Confirmed Weekly", 1, 12, 1.0)
    _upd(fig, 600)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
FOREX_PAIRS = [
    "BTCUSD=X",
    "AUDCAD=X",
    "AUDCHF=X",
    "AUDJPY=X",
    "CADCHF=X",
    "CADJPY=X",
    "CHFJPY=X",
    "DE30=X",
    "DXY=X",
    "EURAUD=X",
    "EURCAD=X",
    "EURGBP=X",
    "EURCHF=X",
    "EURUSD=X",
    "EURJPY=X",
    "EURNZD=X",
    "GBPAUD=X",
    "GBPCAD=X",
    "GBPCHF=X",
    "GBPUSD=X",
    "GBPJPY=X",
    "HK50=X",
    "HKDJPY=X",
    "JP225=X",
    "NZDCAD=X",
    "NZDCHF=X",
    "NZDJPY=X",
    "NZDUSD=X",
    "SEKJPY=X",
    "TRYDKK=X",
    "TRYJPY=X",
    "US30=X",
    "US500=X",
    "USDCAD=X",
    "USDCHF=X",
    "USDJPY=X",
    "USOIL=X",
    "XAGGBP=X",
    "XAGUSD=X",
    "XAUUSD=X",

]

# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE SINAIS ATIVOS — sem modificar nenhuma lógica existente
# ══════════════════════════════════════════════════════════════════════════════
def _last_signal(buy_mask, sell_mask):
    last_b = buy_mask[buy_mask].index[-1]  if buy_mask.any()  else None
    last_s = sell_mask[sell_mask].index[-1] if sell_mask.any() else None
    if last_b is None and last_s is None: return None, None
    if last_b is None: return "SELL", last_s
    if last_s is None: return "BUY",  last_b
    return ("BUY", last_b) if last_b > last_s else ("SELL", last_s)

def check_active_signals(A, fx_sym, selected_charts):
    sigs = []
    def _add(chart, direction, date, indicators):
        if direction and chart in selected_charts:
            sigs.append({"chart": chart, "direction": direction,
                         "indicators": indicators,
                         "date": str(date)[:10] if date is not None else ""})

    if "Risk-Return Weekly (BTC+SPY Macro)" in selected_charts:
        try:
            c = cl(A["btc_w"])
            b,s = macro_sig_btc(calc_sharpe(c,52,60), calc_sortino(c,52,60))
            d,dt = _last_signal(b,s)
            _add("Risk-Return Weekly (BTC+SPY Macro)", d, dt, ["Sharpe","Sortino","Macro BTC"])
        except Exception: pass

    if "BTC Daily" in selected_charts:
        try:
            c = cl(A["btc_d"])
            rb,rs = rsi_sig_btc_d(calc_rsi(c,14))
            sb,ss = stoch_sig(calc_stochrsi(c,14,3))
            bb_b,bb_s = bb_sig(calc_bb_pct(c,20,2))
            b,s = combined([rb,sb,bb_b],[rs,ss,bb_s],[0.5,0.5,2.0],3.0)
            d,dt = _last_signal(b,s)
            _add("BTC Daily", d, dt, ["RSI","StochRSI","BB%B","Combined"])
        except Exception: pass

    if "BTC Weekly" in selected_charts:
        try:
            c = cl(A["btc_w"])
            sh=calc_sharpe(c,52,60); so=calc_sortino(c,52,60)
            sh_b,sh_s = sharpe_sig(sh,-1.5,2.1)
            so_b,so_s = sortino_sig(so,-1.7,4.7)
            b,s = confirmed(sh_b,sh_s,so_b,so_s)
            d,dt = _last_signal(b,s)
            _add("BTC Weekly", d, dt, ["Sharpe","Sortino","Confirmed"])
        except Exception: pass

    if "BTC Monthly" in selected_charts:
        try:
            c = cl(A["btc_m"])
            b,s = macro_sig_btc(calc_sharpe(c,12,60), calc_sortino(c,12,60))
            d,dt = _last_signal(b,s)
            _add("BTC Monthly", d, dt, ["Sharpe","Sortino","Macro"])
        except Exception: pass

    if "SPY Weekly" in selected_charts:
        try:
            c = cl(A["spy_w"])
            b,s = macro_sig_spy(calc_sharpe(c,52,60), calc_sortino(c,52,60))
            d,dt = _last_signal(b,s)
            _add("SPY Weekly", d, dt, ["Sharpe","Sortino","Macro SPY"])
        except Exception: pass

    if "SPY Monthly" in selected_charts:
        try:
            c = cl(A["spy_m"])
            b,s = macro_sig_spy(calc_sharpe(c,12,60), calc_sortino(c,12,60))
            d,dt = _last_signal(b,s)
            _add("SPY Monthly", d, dt, ["Sharpe","Sortino","Macro SPY"])
        except Exception: pass

    # ── BTC Overextended (Sharpe >= 6 ou Sortino >= 8, mensal) ──
    if "BTC Monthly" in selected_charts or "Risk-Return Weekly (BTC+SPY Macro)" in selected_charts:
        try:
            c  = cl(A["btc_m"])
            sh = calc_sharpe(c, 12, 60)
            so = calc_sortino(c, 12, 60)
            sh_alert, _ = overextended_sig(sh, OVEREXT["BTC_SHARPE"])
            so_alert, _ = overextended_sig(so, OVEREXT["BTC_SORTINO"])
            # Alerta se QUALQUER um dos dois estourar
            alert = sh_alert | so_alert
            clear = ~alert
            d, dt = _last_signal(alert, clear)
            inds = []
            if sh.iloc[-1] >= OVEREXT["BTC_SHARPE"]:
                inds.append(f"Sharpe {sh.iloc[-1]:.2f} (≥{OVEREXT['BTC_SHARPE']})")
            if so.iloc[-1] >= OVEREXT["BTC_SORTINO"]:
                inds.append(f"Sortino {so.iloc[-1]:.2f} (≥{OVEREXT['BTC_SORTINO']})")
            if inds:
                _add("⚠️ BTC Overextended (Mensal)", "SELL", dt or sh.index[-1], inds)
        except Exception: pass

    # ── SPY Overextended (Sharpe >= 6 ou Sortino >= 5, mensal) ──
    if "SPY Monthly" in selected_charts or "Risk-Return Weekly (BTC+SPY Macro)" in selected_charts:
        try:
            c  = cl(A["spy_m"])
            sh = calc_sharpe(c, 12, 60)
            so = calc_sortino(c, 12, 60)
            sh_alert, _ = overextended_sig(sh, OVEREXT["SPY_SHARPE"])
            so_alert, _ = overextended_sig(so, OVEREXT["SPY_SORTINO"])
            alert = sh_alert | so_alert
            clear = ~alert
            d, dt = _last_signal(alert, clear)
            inds = []
            if sh.iloc[-1] >= OVEREXT["SPY_SHARPE"]:
                inds.append(f"Sharpe {sh.iloc[-1]:.2f} (≥{OVEREXT['SPY_SHARPE']})")
            if so.iloc[-1] >= OVEREXT["SPY_SORTINO"]:
                inds.append(f"Sortino {so.iloc[-1]:.2f} (≥{OVEREXT['SPY_SORTINO']})")
            if inds:
                _add("⚠️ SPY Overextended (Mensal)", "SELL", dt or sh.index[-1], inds)
        except Exception: pass

    if "Forex Daily" in selected_charts:
        try:
            c = cl(A["fx_d"])
            rb,rs = rsi_sig_fx_d(calc_rsi(c,14))
            sb,ss = stoch_sig(calc_stochrsi(c,14,3))
            bb_b,bb_s = bb_sig(calc_bb_pct(c,20,2))
            b,s = combined([rb,sb,bb_b],[rs,ss,bb_s],[0.5,0.5,2.0],3.0)
            d,dt = _last_signal(b,s)
            _add("Forex Daily", d, dt, ["RSI","StochRSI","BB%B","Combined"])
        except Exception: pass

    if "Forex Weekly" in selected_charts:
        try:
            c = cl(A["fx_w"])
            rb,rs = rsi_sig_fx_w(calc_rsi(c,14))
            sb,ss = stoch_sig(calc_stochrsi(c,14,3))
            b,s = combined([rb,sb],[rs,ss],[1,1],2.0)
            d,dt = _last_signal(b,s)
            _add("Forex Weekly", d, dt, ["RSI","StochRSI","Combined"])
        except Exception: pass

    return sigs


ALL_CHARTS = [
    "Risk-Return Weekly (BTC+SPY Macro)",
    "BTC Daily",
    "BTC Weekly",
    "BTC Monthly",
    "SPY Weekly",
    "SPY Monthly",
    "Forex Daily",
    "Forex Weekly",
    "Forex Monthly",
    "Forex Macro Weekly",
]
CHART_KEYS = {
    "Risk-Return Weekly (BTC+SPY Macro)": "rr",
    "BTC Daily":       "btc_d",
    "BTC Weekly":      "btc_w",
    "BTC Monthly":     "btc_m",
    "SPY Weekly":      "spy_w",
    "SPY Monthly":     "spy_m",
    "Forex Daily":     "fx_d",
    "Forex Weekly":    "fx_w",
    "Forex Monthly":   "fx_m",
    "Forex Macro Weekly": "fx_macro",
}

with st.sidebar:
    st.markdown("## 📊 Montrezor Market Analysis")

    st.markdown('<div class="sec">GRÁFICOS A EXIBIR</div>', unsafe_allow_html=True)
    sel = st.multiselect(
        "", ALL_CHARTS,
        default=["Risk-Return Weekly (BTC+SPY Macro)", "BTC Daily", "BTC Weekly", "BTC Monthly", "SPY Weekly", "SPY Monthly", "Forex Daily", "Forex Weekly"],
        label_visibility="collapsed",
    )

    # par forex só aparece se algum gráfico forex estiver selecionado
    fx_charts = {"Forex Daily","Forex Weekly","Forex Monthly","Forex Macro Weekly"}
    show_fx = any(s in fx_charts for s in sel)
    if show_fx:
        st.markdown('<div class="sec">PAR FOREX</div>', unsafe_allow_html=True)
        fx_sym = st.selectbox("", FOREX_PAIRS, index=0, label_visibility="collapsed")
    else:
        fx_sym = "EURCHF=X"

    # ══════════════════════════════════════════════════════════════════════════════
    # REFRESH AUTOMÁTICO (Igual ao Trading System)
    # ══════════════════════════════════════════════════════════════════════════════
    REFRESH_INTERVAL = 600 # 10 minutos em segundos

    # 1. O Toggle (interruptor) igual ao do trading_system
    auto_refresh = st.sidebar.toggle("🔄 Auto-Refresh (10 min)", value=False, key="auto_update")

    # Inicializa o timestamp se não existir
    if "last_ma_update" not in st.session_state:
        st.session_state.last_ma_update = time.time()

    # 2. Botão manual na barra lateral
    if st.sidebar.button("Atualizar Dados Agora"):
        st.session_state.last_ma_update = time.time()
        st.cache_data.clear()
        st.rerun()

    # 3. Lógica do Auto-Refresh acoplada ao toggle e exibição do painel
    if st.session_state.auto_update:
        now = time.time()
        last = st.session_state.last_ma_update
        elapsed = now - last
        remaining = REFRESH_INTERVAL - elapsed

        # Mostra o status do temporizador de forma visível
        st.sidebar.markdown(
            f"<div style='margin-top:5px;padding:10px;background:#0D1117;"
            f"border:1px solid #21262D;border-radius:6px;font-size:10px;color:#484F58;'>"
            f"Última atualização:<br><span style='color:#58A6FF; font-weight:bold;'> "
            f"{datetime.fromtimestamp(last).strftime('%d/%m %H:%M:%S')}</span><br>"
            f"Próxima em: {max(0, int(remaining//60))}m {max(0, int(remaining%60))}s</div>",
            unsafe_allow_html=True
        )

        if elapsed >= REFRESH_INTERVAL:
            st.session_state.last_ma_update = time.time()
            st.cache_data.clear()
            st.rerun()
        else:
            # Força o Streamlit a atualizar a página para redesenhar o contador (JavaScript injection)
            # Recarrega a cada 30 segundos para atualizar o contador visual sem sobrecarregar o servidor
            st.markdown(
                f"""
                <noscript><meta http-equiv="refresh" content="30"></noscript>
                <script>
                    setTimeout(function() {{
                        window.parent.postMessage({{type: 'streamlit:setComponentValue', value: true}}, '*');
                    }}, 30000);
                </script>
                """,
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 📊Montrezor Market Analysis")
if not sel:
    st.info("Selecione pelo menos um gráfico no painel lateral.")
    st.stop()

# Carrega dados (cacheado)
assets = load_all(fx_sym)

BUILDERS = {
    "rr":       lambda: build_rr(assets),
    "btc_d":    lambda: build_btc_d(assets),
    "btc_w":    lambda: build_btc_w(assets),
    "btc_m":    lambda: build_btc_m(assets),
    "spy_w":    lambda: build_spy_w(assets),
    "spy_m":    lambda: build_spy_m(assets),
    "fx_d":     lambda: build_fx_d(assets, fx_sym),
    "fx_w":     lambda: build_fx_w(assets, fx_sym),
    "fx_m":     lambda: build_fx_m(assets, fx_sym),
    "fx_macro": lambda: build_fx_macro(assets, fx_sym),
}

# ── PAINEL DE SINAIS ATIVOS ─────────────────────────────────────
active_sigs = check_active_signals(assets, fx_sym, sel)

if "ma_alerted" not in st.session_state:
    # Recarregar do disco para não perder controle entre reinicializações
    cd = _load_cooldown()
    st.session_state.ma_alerted = {k: True for k in cd if not _is_cooldown(k) is False}
if "ma_tg_enabled" not in st.session_state: st.session_state.ma_tg_enabled = True

if active_sigs:
    st.markdown("<div style='font-size:12px;font-weight:700;color:#8b949e;"
                "letter-spacing:.8px;text-transform:uppercase;margin-bottom:8px'>"
                "📡 SINAIS ATIVOS</div>", unsafe_allow_html=True)

    pills = "<div style='display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px'>"
    for sig in active_sigs:
        clr  = "#3fb950" if sig["direction"]=="BUY" else "#f85149"
        icon = "▲" if sig["direction"]=="BUY" else "▼"
        pills += ("<span style='background:" + clr + "22;border:1px solid " + clr + ";"
                  "border-radius:6px;padding:4px 10px;font-size:12px;"
                  "font-family:JetBrains Mono,monospace;color:" + clr + "'>"
                  + icon + " " + sig["chart"] + " · " + sig["date"] + "</span>")
    pills += "</div>"
    st.markdown(pills, unsafe_allow_html=True)

    cols = st.columns(min(len(active_sigs), 3))
    for i, sig in enumerate(active_sigs):
        clr  = "#3fb950" if sig["direction"]=="BUY" else "#f85149"
        icon = "▲" if sig["direction"]=="BUY" else "▼"
        with cols[i % 3]:
            inds_str = " · ".join(sig["indicators"])
            st.markdown(
                "<div style='background:#161b22;border:1px solid " + clr + "44;"
                "border-radius:8px;padding:12px 14px;margin-bottom:8px'>"
                "<div style='font-size:11px;font-weight:700;color:" + clr + ";"
                "letter-spacing:1px;text-transform:uppercase;margin-bottom:6px'>"
                + icon + " " + sig["direction"] + "</div>"
                "<div style='font-size:13px;color:#e6edf3;font-weight:600;"
                "font-family:JetBrains Mono,monospace'>" + sig["chart"] + "</div>"
                "<div style='font-size:11px;color:#8b949e;margin-top:4px'>" + inds_str + "</div>"
                "<div style='font-size:10px;color:#484f58;margin-top:4px'>" + sig["date"] + "</div>"
                "</div>",
                unsafe_allow_html=True)

        # Chave sem data — mesmo sinal de direção em gráfico não reenvia por 24h
        # (data muda a cada candle novo mas o sinal pode ser o mesmo)
        sig_key = sig["chart"] + "_" + sig["direction"]
        if st.session_state.ma_tg_enabled and not _is_cooldown(sig_key):
            ok = _send_tg_ma(sig["chart"], sig["direction"], sig["indicators"])
            if ok:
                _log_ma_signal(sig["chart"], sig["direction"], sig["indicators"])
            _mark_cooldown(sig_key)   # persiste em disco — sobrevive a reinicializações
            st.session_state.ma_alerted[sig_key] = True

    logs = _load_ma_signals()
    if logs:
        with st.expander("📋 Histórico de sinais (" + str(len(logs)) + ")", expanded=False):
            st.dataframe([{"Hora":l["ts"],"Gráfico":l["chart"],"Direção":l["direction"],
                           "Indicadores":" | ".join(l.get("indicators",[]))}
                          for l in logs[:50]], use_container_width=True, hide_index=True)
            if st.button("🗑 Limpar histórico", key="ma_clr_log"):
                if os.path.exists(_MA_SIGNALS_FILE): os.remove(_MA_SIGNALS_FILE)
                st.rerun()
else:
    st.markdown("<div style='color:#484f58;font-size:12px;margin-bottom:12px'>"
                "🔍 Nenhum sinal ativo nos gráficos selecionados.</div>",
                unsafe_allow_html=True)

st.markdown("---")

for name in sel:
    key = CHART_KEYS[name]
    with st.spinner(f"Calculando {name}…"):
        try:
            fig = BUILDERS[key]()
        except Exception as e:
            st.error(f"Erro em {name}: {e}")
            continue
    if fig is None:
        st.warning(f"Sem dados para: {name}")
        continue
    st.plotly_chart(fig, use_container_width=True,
                    config={"scrollZoom": True, "displayModeBar": True,
                            "modeBarButtonsToRemove": ["lasso2d","select2d"]})
st.markdown("<br><p style='text-align: center; color: #484f58; font-size: 12px;'>Montrezor Analysis System | Powered by Igor Montrezor</p>", unsafe_allow_html=True)
