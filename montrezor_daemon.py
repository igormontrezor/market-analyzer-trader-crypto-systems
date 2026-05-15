#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  MONTREZOR DAEMON UNIFICADO                                          ║
║  Cobre os 3 sistemas que emitem sinais:                             ║
║                                                                      ║
║  1. TRADING_SYSTEM  — check_signals() via MT5                       ║
║     Forex/CFDs: RSI canal + Supertrend + EMAs multi-TF              ║
║     Config: ~/.montrezor_data.json                                  ║
║                                                                      ║
║  2. APP (Gems/Macro) — macro_timing.json                            ║
║     Crypto: regime BTC + funding rate + USDT.D semanal              ║
║     Sinais: SUPER_BUY, SUPER_SELL, SUPER_REPIQUE, REPIQUE, BUY, SELL║
║                                                                      ║
║  3. VISUALIZER — _build_macro_timing()                              ║
║     Nao emite sinais — GERA o macro_timing.json que o App consome.  ║
║     O daemon chama _build_macro_timing() para manter o JSON         ║
║     atualizado mesmo sem o browser aberto.                          ║
║                                                                      ║
║  TELEGRAM: ~/.montrezor_telegram.json (mesmo ficheiro dos 3)        ║
║                                                                      ║
║  COMO USAR:                                                          ║
║    python montrezor_daemon.py                    # todos os sistemas ║
║    python montrezor_daemon.py --only trading     # so MT5/forex     ║
║    python montrezor_daemon.py --only gems        # so crypto/macro  ║
║    python montrezor_daemon.py --silent           # sem output       ║
║    python montrezor_daemon.py --install-service  # Windows auto     ║
║                                                                      ║
║  NAO MODIFICA nenhum dos 3 arquivos originais.                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import time
import json
import html
import logging
import argparse
import hashlib
from datetime import datetime

import numpy as np
import pandas as pd
import requests

# ════════════════════════════════════════════════════════════════════════
# CONFIGURACAO
# ════════════════════════════════════════════════════════════════════════
TRADING_SCAN_SEC   = 60    # trading_system: checar a cada 60s
GEMS_SCAN_SEC      = 300   # gems/macro: checar a cada 5 min
MACRO_REBUILD_SEC  = 300   # visualizer: rebuild macro_timing.json a cada 5 min

TRADING_COOLDOWN_MIN = 240  # 4h cooldown forex
GEMS_COOLDOWN_MIN    = 60   # 1h cooldown crypto

PERSIST_FILE  = os.path.join(os.path.expanduser("~"), ".montrezor_data.json")
TELEGRAM_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_telegram.json")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MACRO_JSON  = os.path.join(PROJECT_DIR, "gems_system", "data", "macro", "macro_timing.json")
LOG_FILE    = os.path.join(PROJECT_DIR, "montrezor_daemon.log")

# ════════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════════
def setup_logging(silent):
    logger = logging.getLogger("montrezor")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt); logger.addHandler(fh)
    if not silent:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt); logger.addHandler(sh)
    return logger

# ════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ════════════════════════════════════════════════════════════════════════
def _norm(s):
    if not s: return ""
    s = str(s).strip().replace("\r","").replace("\n","")
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'": s = s[1:-1].strip()
    return s

def _post(token, chat_id, msg, parse_mode="HTML"):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r   = requests.post(url, json={"chat_id": chat_id, "text": msg,
                                        "parse_mode": parse_mode}, timeout=15)
        return r.status_code == 200 and r.json().get("ok", False)
    except Exception:
        return False

def send_trading_tg(symbol, direction, sig_type, price, token, chat_id,
                    touch_tfs=None, enrich=None):
    """
    enrich: dict com campos do enrich_signal (div_grade, vol_ratio, atr_low, elevated, etc.)
    Se None, envia mensagem padrão sem campos extras.
    """
    token = _norm(token); chat_id = _norm(chat_id)
    if not token or not chat_id: return False
    icon = "📈" if direction == "COMPRA" else "📉"
    star = "⭐" if sig_type == "SUPER" else "•"
    e    = html.escape
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # TFs tocados
    tf_text = f"<b>Toques RSI</b>: {e(' | '.join(touch_tfs))}\n" if touch_tfs else ""

    # Elevação
    elev_text = ""
    if enrich and enrich.get("elevated"):
        reason = enrich.get("elevation_reason", "")
        elev_text = f"<b>Elevação</b>: COMUM → SUPER ({e(reason)})\n"

    # Divergência RSI
    div_text = ""
    if enrich:
        div_grade = enrich.get("div_grade")
        if div_grade:
            parts = []
            if enrich.get("div_w1"): parts.append("W1 ⚡")
            elif enrich.get("div_d1"): parts.append("D1")
            elif enrich.get("div_4h"): parts.append("4H")
            if parts:
                div_text = f"<b>Divergência RSI</b>: {e(' > '.join(parts))}\n"

    # Volume
    vol_text = ""
    if enrich:
        vol_ratio = enrich.get("vol_ratio", 1.0)
        vol_high  = enrich.get("vol_high", False)
        vol_icon  = "🔥" if vol_high else "·"
        vol_text  = f"<b>Volume 4H</b>: {vol_icon} {vol_ratio:.1f}x média\n"

    # ATR
    atr_text = ""
    if enrich and enrich.get("atr_low"):
        atr_ratio = enrich.get("atr_ratio", 1.0)
        atr_text  = f"⚠️ <b>ATR baixo</b> ({atr_ratio:.2f}x média) — mercado em range\n"

    # --- NOVOS ALERTAS AQUI ---
    stoch_text = ""
    if enrich and enrich.get("stoch_div"):
        stoch_text = "⚠️ <b>StochRSI</b>: Contra o movimento (aguarde cruzar)\n"

    ema_mn_text = ""
    if enrich and enrich.get("mn_ema_div"):
        ema_mn_text = "🚨 <b>EMA Mensal</b>: Divergente do Supertrend\n"
    # --------------------------

    msg = (
        f"{icon} <b>SINAL {e(sig_type)}</b> {star}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<b>Par</b>: {e(symbol)}\n"
        f"<b>Direção</b>: {e(direction)}\n"
        f"<b>Preço</b>: {price:.5f}\n"
        f"{tf_text}"
        f"{elev_text}"
        f"{div_text}"
        f"{vol_text}"
        f"{atr_text}"
        f"{stoch_text}"       # Inserir aqui
        f"{ema_mn_text}"      # Inserir aqui
        f"<b>Hora</b>: {e(ts)}\n\n"
        "Montrezor Trading [daemon]"
    )
    if _post(token, chat_id, msg): return True

    # Fallback texto simples
    tf_plain   = f"Toques: {' | '.join(touch_tfs)}\n" if touch_tfs else ""
    div_plain  = f"Div RSI: {enrich.get('div_grade','—')}\n" if enrich and enrich.get('div_grade') else ""
    vol_plain  = f"Volume: {enrich.get('vol_ratio',1.0):.1f}x\n" if enrich else ""
    atr_plain  = "ATR: RANGE MORTO\n" if enrich and enrich.get('atr_low') else ""
    elev_plain = f"Elevacao: COMUM->SUPER ({enrich.get('elevation_reason','')})\n" if enrich and enrich.get('elevated') else ""
    stoch_plain = "StochRSI: DIVERGENTE\n" if enrich and enrich.get('stoch_div') else ""
    ema_mn_plain = "EMA Mensal: DIVERGENTE\n" if enrich and enrich.get('mn_ema_div') else ""
    plain = (
        f"SINAL {sig_type}\nPar: {symbol}\nDirecao: {direction}\nPreco: {price:.5f}\n"
        f"{tf_plain}{elev_plain}{div_plain}{vol_plain}{atr_plain}{stoch_plain}{ema_mn_plain}Hora: {ts}\nMontrezor [daemon]"
    )
    return _post(token, chat_id, plain, "")

def send_gems_tg(symbol, sig_type, funding, token, chat_id):
    token = _norm(token); chat_id = _norm(chat_id)
    if not token or not chat_id: return False
    icons = {"SUPER_BUY":"⚡🟢","SUPER_SELL":"🚨🔴","SUPER_REPIQUE":"⚡🔵",
             "REPIQUE":"🔵","BUY":"🟢","SELL":"🔴"}
    icon = icons.get(sig_type, "•")
    e    = html.escape
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg  = (f"{icon} <b>GEMS ALERT — {e(sig_type)}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Ativo</b>: {e(symbol)}\n<b>Sinal</b>: {e(sig_type)}\n"
            f"<b>Funding</b>: {funding:.4f}%\n<b>Hora</b>: {e(ts)}\n\nMontrezor Gems [daemon]")
    if _post(token, chat_id, msg): return True
    plain = f"GEMS {sig_type}\nAtivo: {symbol}\nFunding: {funding:.4f}%\nHora: {ts}\nMontrezor [daemon]"
    return _post(token, chat_id, plain, "")

# ════════════════════════════════════════════════════════════════════════
# CONFIG LOADER
# ════════════════════════════════════════════════════════════════════════
def load_config():
    data = {"symbols": [], "athena": {}, "tg_token": "", "tg_chat_id": ""}
    try:
        if os.path.exists(PERSIST_FILE):
            with open(PERSIST_FILE,"r",encoding="utf-8") as f:
                raw = json.load(f)
                data["symbols"] = raw.get("symbols", [])
                data["athena"]  = raw.get("athena",  {})
    except Exception: pass
    try:
        if os.path.exists(TELEGRAM_FILE):
            with open(TELEGRAM_FILE,"r",encoding="utf-8") as f:
                cfg = json.load(f)
                data["tg_token"]   = _norm(cfg.get("token",""))
                data["tg_chat_id"] = _norm(cfg.get("chat_id",""))
    except Exception: pass
    return data

# ════════════════════════════════════════════════════════════════════════
# COOLDOWN
# ════════════════════════════════════════════════════════════════════════
class AlertState:
    def __init__(self, cooldown_min):
        self._d = {}; self._s = cooldown_min * 60
    def _k(self, *p): return hashlib.md5("|".join(str(x) for x in p).encode()).hexdigest()
    def ok(self, *p): return (time.time() - self._d.get(self._k(*p), 0)) >= self._s
    def mark(self, *p): self._d[self._k(*p)] = time.time()
    def clear(self, *p): self._d.pop(self._k(*p), None)

# ════════════════════════════════════════════════════════════════════════
# SISTEMA 1 — TRADING (MT5)
# Indicadores e check_signals copiados EXATAMENTE do trading_system.py
# ════════════════════════════════════════════════════════════════════════
try:
    import MetaTrader5 as mt5
    _MT5_OK = True
except ImportError:
    mt5 = None; _MT5_OK = False

MT5_TF   = {"1mo":49153,"1wk":32769,"1d":16408,"4h":16388}
MT5_BARS = {"1mo":120,"1wk":300,"1d":730,"4h":1500}

def _mt5_init():
    if not _MT5_OK: return False
    try:
        if mt5.terminal_info() is not None: return True
        return mt5.initialize()
    except: return False

def _mt5_fetch(symbol, interval):
    if not _mt5_init(): return None
    tf = MT5_TF.get(interval, 16408); n = MT5_BARS.get(interval, 500)
    if mt5.symbol_info(symbol) is None:
        mt5.symbol_select(symbol, True)
        if mt5.symbol_info(symbol) is None: return None
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return (df.rename(columns={"time":"Date","open":"Open","high":"High",
                                "low":"Low","close":"Close","tick_volume":"Volume"})
              .set_index("Date")[["Open","High","Low","Close","Volume"]].sort_index())

def _ema(s, p): return s.ewm(span=p, adjust=False).mean()

# FIX 1: calc_atr identico ao trading_system (use_true_atr=True por default)
def _calc_atr(df, period=10, use_true_atr=True):
    high = df['High']; low = df['Low']; close_prev = df['Close'].shift(1)
    if use_true_atr:
        tr = pd.concat([high-low, (high-close_prev).abs(), (low-close_prev).abs()], axis=1).max(axis=1)
        return tr.ewm(alpha=1/period, adjust=False).mean()
    else:
        tr = pd.concat([high-low, (high-close_prev).abs(), (low-close_prev).abs()], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

# FIX 2: _supertrend identico ao trading_system — gera ST_Up, ST_Dn, ST_Line, ST_Trend
def _supertrend(df, period=10, mult=3.0, use_true_atr=True):
    hl2=(df['High']+df['Low'])/2
    atr=_calc_atr(df, period, use_true_atr)
    up_basic=hl2-(mult*atr); dn_basic=hl2+(mult*atr)
    n=len(df); up=[np.nan]*n; dn=[np.nan]*n; tr_=[0]*n; cl=df['Close'].values
    for i in range(1,n):
        ub=up_basic.iloc[i] if not np.isnan(up_basic.iloc[i]) else 0
        db=dn_basic.iloc[i] if not np.isnan(dn_basic.iloc[i]) else 0
        pu=up[i-1] if not np.isnan(up[i-1]) else ub
        pd_=dn[i-1] if not np.isnan(dn[i-1]) else db
        up[i]=max(ub,pu) if cl[i-1]>pu else ub
        dn[i]=min(db,pd_) if cl[i-1]<pd_ else db
        if   tr_[i-1]==-1 and cl[i]>pd_: tr_[i]=1
        elif tr_[i-1]==1  and cl[i]<pu:  tr_[i]=-1
        else: tr_[i]=tr_[i-1] if tr_[i-1]!=0 else 1
    df=df.copy()
    up_arr=np.array(up,dtype=float); dn_arr=np.array(dn,dtype=float); ta=np.array(tr_,dtype=int)
    df['ST_Up']   = np.where(ta ==  1, up_arr, np.nan)   # identico ao trading_system
    df['ST_Dn']   = np.where(ta == -1, dn_arr, np.nan)   # identico ao trading_system
    df['ST_Line'] = np.where(ta ==  1, up_arr, dn_arr)
    df['ST_Trend']= ta
    return df

def _rsi_wilder(series, period=14):
    delta=series.diff(); g=delta.where(delta>0,0.0).values; l=(-delta.where(delta<0,0.0)).values
    n=len(series); ag=np.full(n,np.nan); al=np.full(n,np.nan)
    if n>period:
        ag[period]=float(np.nanmean(g[1:period+1])); al[period]=float(np.nanmean(l[1:period+1]))
        for i in range(period+1,n):
            ag[i]=(ag[i-1]*(period-1)+g[i])/period; al[i]=(al[i-1]*(period-1)+l[i])/period
    rs=pd.Series(ag,index=series.index)/pd.Series(al,index=series.index).replace(0,np.nan)
    return 100-(100/(1+rs))

def _rsi_channel(df, rsi_period=14, lr_period=50, mult=2.0):
    df=df.copy(); df["RSI"]=_rsi_wilder(df["Close"],rsi_period)
    df["RSI_LR"]=np.nan; df["RSI_Upper"]=np.nan; df["RSI_Lower"]=np.nan  # FIX 12: RSI_LR
    rv=df["RSI"].values; x=np.arange(lr_period,dtype=float)
    sx=float(np.sum(x)); sxx=float(np.sum(x*x)); denom=sx*sx-lr_period*sxx
    lr_loc=df.columns.get_loc("RSI_LR")
    ul=df.columns.get_loc("RSI_Upper"); ll=df.columns.get_loc("RSI_Lower")
    for i in range(lr_period-1,len(df)):
        yw=rv[i-lr_period+1:i+1]
        if np.isnan(yw).any(): continue
        y=yw[::-1]; sy=float(np.sum(y)); syy=float(np.sum(y*y)); sxy=float(np.sum(x*y))
        if denom==0: continue
        slope=(lr_period*sxy-sx*sy)/denom
        en=lr_period*syy-sy*sy-slope*slope*(lr_period*sxx-sx*sx); ed=lr_period*(lr_period-2.0)
        err=float(np.sqrt(max(en/ed,0.0))) if ed!=0 else 0.0
        mid=(sy+slope*sx)/lr_period
        df.iloc[i,lr_loc]=mid                   # FIX 12: linha central
        df.iloc[i,ul]=mid+err*mult; df.iloc[i,ll]=mid-err*mult
    return df

# FIX 3: calc_stoch_rsi identico ao trading_system
def _calc_stoch_rsi(df, rsi_period=14, k_period=14, d_period=3, slowing=5):
    df = df.copy()
    if 'RSI' not in df.columns:
        df['RSI'] = _rsi_wilder(df['Close'], rsi_period)
    rsi_min = df['RSI'].rolling(k_period).min()
    rsi_max = df['RSI'].rolling(k_period).max()
    raw_k   = 100 * ((df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9))
    df['StochRSI_K'] = raw_k.rolling(slowing).mean()
    df['StochRSI_D'] = df['StochRSI_K'].rolling(d_period).mean()
    return df

def _build_indicators(raw):
    df=_supertrend(raw); df["EMA_50"]=_ema(df["Close"],50)
    df["EMA_100"]=_ema(df["Close"],100); df["EMA_200"]=_ema(df["Close"],200)
    df=_rsi_channel(df)
    df=_calc_stoch_rsi(df)   # FIX 3: identico ao trading_system
    return df

def _near(a,b,pct=0.0075):  # FIX 4: identico ao trading_system (era 0.015)
    try: return abs(float(a)-float(b))/abs(float(b))<pct if float(b)!=0 else False
    except: return False

def _rsi_hit_bot(r):
    try: return float(r["RSI"])<=float(r["RSI_Lower"])
    except: return False

def _rsi_hit_top(r):
    try: return float(r["RSI"])>=float(r["RSI_Upper"])
    except: return False

def _rsi_near_bot(r, near_pct=0.03):
    try: return float(r["RSI"])<=(float(r["RSI_Lower"])+near_pct*100)
    except: return False

def _rsi_near_top(r, near_pct=0.03):
    try: return float(r["RSI"])>=(float(r["RSI_Upper"])-near_pct*100)
    except: return False

def _ema_near(r,pct=0.018):  # FIX 5: identico ao trading_system (era 0.015)
    try:
        c=float(r["Close"])
        return any(_near(c,float(r[e]),pct) for e in ["EMA_50","EMA_100","EMA_200"])
    except: return False

def _get_confirmed_row(df, allow_current=False):
    if df is None or len(df)<2: return df.iloc[-1] if df is not None and len(df)>=1 else None
    if allow_current: return df.iloc[-1]
    now=pd.Timestamp.utcnow().tz_localize(None); last=df.index[-1]
    if hasattr(last,"tz") and last.tz is not None: last=last.tz_convert("UTC").tz_localize(None)
    return df.iloc[-2] if last.date()>=now.date() else df.iloc[-1]

def check_signals_trading(data, symbol, athena_levels):
    """
    Copia EXATA de check_signals() do trading_system.py.
    Todos os fixes aplicados: NEAR_TF=0.015, NEAR_W1_MN=0.030,
    touch_st toque EXATO (sem near), retorno completo com touch_tfs e _debug.
    """
    if '1mo' not in data or '1wk' not in data: return None

    mn_trend = data['1mo'].iloc[-1]   # mensal atual - tendencia/EMAs
    w1_trend = data['1wk'].iloc[-1]   # semanal atual - tendencia/EMAs
    mn_rsi   = data['1mo'].iloc[-1]   # mensal atual - RSI (em formacao OK)
    w1_rsi   = data['1wk'].iloc[-1]   # semanal atual - RSI (em formacao OK)
    if mn_rsi is None or w1_rsi is None: return None

    trend_mn = int(mn_trend.get('ST_Trend', 0))
    if trend_mn == 0: return None

    try:
        w1_buy_ema  = float(w1_trend['EMA_50']) > float(w1_trend['EMA_100']) > float(w1_trend['EMA_200'])
        w1_sell_ema = float(w1_trend['EMA_50']) < float(w1_trend['EMA_100']) < float(w1_trend['EMA_200'])
    except:
        w1_buy_ema = w1_sell_ema = False

    if trend_mn == 1:
        direction = "COMPRA"
        if w1_sell_ema: return None   # semanal divergindo
    else:
        direction = "VENDA"
        if w1_buy_ema:  return None   # semanal divergindo

    touch_fn = _rsi_hit_bot  if direction == "COMPRA" else _rsi_hit_top
    near_fn  = _rsi_near_bot if direction == "COMPRA" else _rsi_near_top

    # FIX 6: NEAR_TF=0.015 (1.5 pts RSI) identico ao trading_system (era 0.03)
    NEAR_TF    = 0.015   # D1 / 4H
    NEAR_W1_MN = 0.030   # Semanal / Mensal

    d1_data   = data.get('1d')
    d1_current = _get_confirmed_row(d1_data, allow_current=True) if d1_data is not None else None
    hit_d1     = (touch_fn(d1_current) or near_fn(d1_current, near_pct=NEAR_TF)) if d1_current is not None else False

    hit_4h = False; tfm_4h = None
    if '4h' in data:
        tfm_4h = _get_confirmed_row(data['4h'], allow_current=True)
        hit_4h = (touch_fn(tfm_4h) or near_fn(tfm_4h, near_pct=NEAR_TF)) if tfm_4h is not None else False

    if hit_4h and tfm_4h is not None: tfm = tfm_4h; tf_menor_key = '4h'
    elif d1_current is not None:      tfm = d1_current; tf_menor_key = '1d'
    else: return None

    hit_tfm = hit_d1 or hit_4h

    hit_w1  = touch_fn(w1_rsi)
    hit_mn  = touch_fn(mn_rsi)
    near_w1 = near_fn(w1_rsi, near_pct=NEAR_W1_MN)
    near_mn = near_fn(mn_rsi, near_pct=NEAR_W1_MN)

    minor_ok   = hit_tfm
    weekly_ok  = hit_w1 or near_w1
    monthly_ok = hit_mn or near_mn
    canal_ok   = minor_ok and (weekly_ok or monthly_ok)
    if not canal_ok: return None

    d1_cur = d1_data.iloc[-1] if d1_data is not None and not d1_data.empty else None
    ema_ok = _ema_near(mn_trend) or _ema_near(w1_trend) or (_ema_near(d1_cur) if d1_cur is not None else False)
    if not ema_ok: return None

    c_price = float(tfm['Close'])
    na = athena_levels.get(symbol, {})
    na_buy_entry  = na.get('buy_entry',  0.0)
    na_sell_entry = na.get('sell_entry', 0.0)

    # FIX 8: toque EXATO no ST — sem _near() (identico ao trading_system)
    try:
        st_line = float(tfm['ST_Line'])
        c_low   = float(tfm['Low'])
        c_high  = float(tfm['High'])
        touch_st = (c_low <= st_line <= c_high)   # toque exato: sem near
    except:
        touch_st = False

    touch_na = False
    if direction == "COMPRA" and float(na_sell_entry) > 0:
        touch_na = _near(c_price, na_sell_entry, pct=0.012)
    elif direction == "VENDA" and float(na_buy_entry) > 0:
        touch_na = _near(c_price, na_buy_entry, pct=0.012)

    sinal_super = touch_st or touch_na

    # FIX 11: retorno completo identico ao trading_system
    try: signal_ts = tfm.name
    except: signal_ts = None

    # FIX 10: touch_tfs para mensagem Telegram enriquecida
    touch_tfs = []
    if hit_d1:  touch_tfs.append('1D')
    if hit_4h:  touch_tfs.append('4H')
    if hit_w1:  touch_tfs.append('1W')
    elif near_w1: touch_tfs.append('1W~')
    if hit_mn:  touch_tfs.append('1M')
    elif near_mn: touch_tfs.append('1M~')

    # ... código existente ...
    # FIX 10: touch_tfs para mensagem Telegram enriquecida
    touch_tfs = []
    if hit_d1:  touch_tfs.append('1D')
    if hit_4h:  touch_tfs.append('4H')
    if hit_w1:  touch_tfs.append('1W')
    elif near_w1: touch_tfs.append('1W~')
    if hit_mn:  touch_tfs.append('1M')
    elif near_mn: touch_tfs.append('1M~')

    # =========================================================
    # NOVAS TRAVAS E ALERTAS
    # =========================================================
    try:
        mn_ema50 = float(mn_trend['EMA_50'])
        mn_ema100 = float(mn_trend['EMA_100'])
        mn_ema_div = (mn_ema50 < mn_ema100) if direction == "COMPRA" else (mn_ema50 > mn_ema100)
    except:
        mn_ema_div = False

    try:
        stk = float(tfm['StochRSI_K'])
        std = float(tfm['StochRSI_D'])
        if direction == "COMPRA":
            stoch_div = (stk >= 80) or (stk < std)
        else:
            stoch_div = (stk <= 20) or (stk > std)
    except:
        stoch_div = False

    # if stoch_div or mn_ema_div:
    #     return None
    # =========================================================

    return {
        "symbol":    symbol,
        "direction": direction,
        "type":      "SUPER" if sinal_super else "COMUM",
        "price":     c_price,
        "tf_menor":  tf_menor_key,
        "trend_mn":  trend_mn,
        "signal_ts": signal_ts,
        "touch_tfs": touch_tfs,
        "stoch_div": stoch_div,    # Repassando para o bot
        "mn_ema_div": mn_ema_div,  # Repassando para o bot
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


# ════════════════════════════════════════════════════════════════════════
# ENRIQUECIMENTO DE SINAL — divergência RSI, volume, ATR
# Chamado APÓS check_signals_trading() — nunca altera a lógica base.
# Pode elevar COMUM→SUPER mas nunca rebaixa nem bloqueia.
# ════════════════════════════════════════════════════════════════════════

# ── Parâmetros de enriquecimento ─────────────────────────────────────────
ENRICH_VOLUME_BARS    = 14     # candles 4H para calcular média de volume
ENRICH_VOLUME_MULT    = 1.5    # toque com volume > 1.5x média = "volume alto"
#
# Lookback para detecção de divergência por TF:
#   Divergência exige 2 pivôs — o lookback define a janela onde os pivôs
#   são procurados. Valores corretos por TF:
#     4H: 40 candles = ~1 semana de histórico para achar 2 fundos/topos
#     D1: 20 candles = ~1 mês de pregões
#     W1: 10 semanas = ~2,5 meses (pivôs semanais são mais espaçados)
#
ENRICH_DIV_BARS_4H    = 40     # lookback divergência 4H (candles 4H)
ENRICH_DIV_BARS_D1    = 20     # lookback divergência D1 (dias)
ENRICH_DIV_BARS_W1    = 10     # lookback divergência W1 (semanas)
ENRICH_DIV_MIN_DIST   = 5      # distância mínima entre pivôs (candles)
ENRICH_ATR_BARS       = 20     # período ATR para comparação
ENRICH_ATR_LOW_RATIO  = 0.5    # ATR atual < 50% da média = range morto

def _find_pivot_low(series, left=3, right=3):
    """
    Encontra índices de pivôs de mínimo dentro da série.
    Um pivô de mínimo é um ponto menor que `left` candles à esquerda
    e `right` candles à direita.
    """
    pivots = []
    vals = series.values
    n = len(vals)
    for i in range(left, n - right):
        if np.isnan(vals[i]):
            continue
        if all(vals[i] <= vals[i-j] for j in range(1, left+1)) and            all(vals[i] <= vals[i+j] for j in range(1, right+1)):
            pivots.append(i)
    return pivots

def _find_pivot_high(series, left=3, right=3):
    """
    Encontra índices de pivôs de máximo dentro da série.
    """
    pivots = []
    vals = series.values
    n = len(vals)
    for i in range(left, n - right):
        if np.isnan(vals[i]):
            continue
        if all(vals[i] >= vals[i-j] for j in range(1, left+1)) and            all(vals[i] >= vals[i+j] for j in range(1, right+1)):
            pivots.append(i)
    return pivots

def _check_divergence(df, direction, lookback):
    """
    Divergência RSI vs Preço por PIVÔS — método técnico correto.

    BULLISH (COMPRA):
      Preço faz mínimo mais baixo (P2_low < P1_low)
      RSI    faz mínimo mais ALTO  (R2_low > R1_low)
      → preço cai mas momentum sobe = reversão provável para cima

    BEARISH (VENDA):
      Preço faz máximo mais alto  (P2_high > P1_high)
      RSI    faz máximo mais BAIXO (R2_high < R1_high)
      → preço sobe mas momentum cai = reversão provável para baixo

    Exige pelo menos 2 pivôs separados por ENRICH_DIV_MIN_DIST candles
    dentro da janela `lookback`. Retorna True se confirmado.
    """
    try:
        if df is None or len(df) < lookback + 6:
            return False
        window = df.tail(lookback).copy()
        if 'RSI' not in window.columns or window['RSI'].isna().sum() > lookback * 0.3:
            return False

        rsi_s = window['RSI'].reset_index(drop=True)

        if direction == "COMPRA":
            price_s = window['Low'].reset_index(drop=True)
            p_pivots = _find_pivot_low(price_s)
            r_pivots = _find_pivot_low(rsi_s)

            # Precisamos de pelo menos 2 pivôs em cada
            if len(p_pivots) < 2 or len(r_pivots) < 2:
                return False

            # Pegar os 2 pivôs mais recentes de preço
            p1_idx, p2_idx = p_pivots[-2], p_pivots[-1]
            if (p2_idx - p1_idx) < ENRICH_DIV_MIN_DIST:
                return False

            p1_val = price_s.iloc[p1_idx]
            p2_val = price_s.iloc[p2_idx]

            # RSI: achar pivôs mais próximos dos pivôs de preço
            r1_candidates = [i for i in r_pivots if abs(i - p1_idx) <= 4]
            r2_candidates = [i for i in r_pivots if abs(i - p2_idx) <= 4]

            if not r1_candidates or not r2_candidates:
                return False

            r1_val = rsi_s.iloc[min(r1_candidates, key=lambda i: abs(i - p1_idx))]
            r2_val = rsi_s.iloc[min(r2_candidates, key=lambda i: abs(i - p2_idx))]

            # BULLISH: preço faz fundo mais baixo, RSI faz fundo mais alto
            return (p2_val < p1_val) and (r2_val > r1_val)

        else:  # VENDA
            price_s = window['High'].reset_index(drop=True)
            p_pivots = _find_pivot_high(price_s)
            r_pivots = _find_pivot_high(rsi_s)

            if len(p_pivots) < 2 or len(r_pivots) < 2:
                return False

            p1_idx, p2_idx = p_pivots[-2], p_pivots[-1]
            if (p2_idx - p1_idx) < ENRICH_DIV_MIN_DIST:
                return False

            p1_val = price_s.iloc[p1_idx]
            p2_val = price_s.iloc[p2_idx]

            r1_candidates = [i for i in r_pivots if abs(i - p1_idx) <= 4]
            r2_candidates = [i for i in r_pivots if abs(i - p2_idx) <= 4]

            if not r1_candidates or not r2_candidates:
                return False

            r1_val = rsi_s.iloc[min(r1_candidates, key=lambda i: abs(i - p1_idx))]
            r2_val = rsi_s.iloc[min(r2_candidates, key=lambda i: abs(i - p2_idx))]

            # BEARISH: preço faz topo mais alto, RSI faz topo mais baixo
            return (p2_val > p1_val) and (r2_val < r1_val)

    except:
        return False

def _check_volume(df_4h, lookback=ENRICH_VOLUME_BARS, mult=ENRICH_VOLUME_MULT):
    """
    Compara o tick volume do último candle 4H fechado
    com a média dos `lookback` candles anteriores.

    Retorna: (ratio, is_high) onde ratio = vol_atual / media
    """
    try:
        if df_4h is None or len(df_4h) < lookback + 2:
            return 1.0, False
        if 'Volume' not in df_4h.columns:
            return 1.0, False
        # Penúltimo = último fechado (último pode estar em formação)
        vol_current = float(df_4h['Volume'].iloc[-2])
        vol_mean    = float(df_4h['Volume'].iloc[-(lookback+2):-2].mean())
        if vol_mean <= 0:
            return 1.0, False
        ratio = vol_current / vol_mean
        return round(ratio, 2), ratio >= mult
    except:
        return 1.0, False

def _check_atr(df_4h, period=ENRICH_ATR_BARS, low_ratio=ENRICH_ATR_LOW_RATIO):
    """
    Compara ATR atual (último candle) com a média dos últimos `period` ATRs.

    Retorna: (ratio, is_low) onde is_low=True significa mercado em range morto.
    """
    try:
        if df_4h is None or len(df_4h) < period + 5:
            return 1.0, False
        atr_series = _calc_atr(df_4h, period=14)
        if atr_series is None or atr_series.isna().all():
            return 1.0, False
        atr_current = float(atr_series.iloc[-1])
        atr_mean    = float(atr_series.iloc[-period-1:-1].mean())
        if atr_mean <= 0:
            return 1.0, False
        ratio = atr_current / atr_mean
        return round(ratio, 2), ratio < low_ratio
    except:
        return 1.0, False

def enrich_signal(sig, data):
    """
    Recebe o sinal aprovado por check_signals_trading() e adiciona:
      - divergência RSI por grau (4H, D1, W1)
      - volume 4H relativo
      - ATR relativo (range morto?)
      - possível elevação COMUM → SUPER

    Regras de elevação (nunca rebaixa, nunca bloqueia):
      COMUM → SUPER se divergência W1 confirmada
      COMUM → SUPER se volume alto (>1.5x) E divergência D1 ou W1

    Retorna o dict do sinal com campos extras adicionados.
    Nunca levanta exceção — em caso de erro retorna o sinal original intacto.
    """
    try:
        direction  = sig["direction"]
        sig_type   = sig["type"]        # tipo original da lógica base

        df_4h = data.get("4h")
        df_d1 = data.get("1d")
        df_w1 = data.get("1wk")

        # ── Divergência RSI por grau ─────────────────────────────────
        div_4h = _check_divergence(df_4h, direction, ENRICH_DIV_BARS_4H)
        div_d1 = _check_divergence(df_d1, direction, ENRICH_DIV_BARS_D1)
        div_w1 = _check_divergence(df_w1, direction, ENRICH_DIV_BARS_W1)

        # Grau máximo de divergência encontrado
        if div_w1:
            div_grade = "W1"      # mais forte
        elif div_d1:
            div_grade = "D1"
        elif div_4h:
            div_grade = "4H"      # mais fraco
        else:
            div_grade = None

        # ── Volume 4H ────────────────────────────────────────────────
        vol_ratio, vol_high = _check_volume(df_4h)

        # ── ATR relativo ─────────────────────────────────────────────
        atr_ratio, atr_low = _check_atr(df_4h)

        # ── Regras de elevação ───────────────────────────────────────
        elevated = False
        elevation_reason = None

        if sig_type == "COMUM":
            if div_w1:
                elevated = True
                elevation_reason = "DIV_W1"
            elif vol_high and (div_d1 or div_w1):
                elevated = True
                elevation_reason = "VOL_HIGH+DIV_D1" if div_d1 else "VOL_HIGH+DIV_W1"

        if elevated:
            sig_type = "SUPER"

        # ── Adicionar campos ao dict ─────────────────────────────────
        sig["type"]             = sig_type          # pode ter sido elevado
        sig["type_base"]        = sig["type"] if not elevated else "COMUM"  # tipo original
        sig["elevated"]         = elevated
        sig["elevation_reason"] = elevation_reason
        sig["div_grade"]        = div_grade         # None | "4H" | "D1" | "W1"
        sig["div_4h"]           = div_4h
        sig["div_d1"]           = div_d1
        sig["div_w1"]           = div_w1
        sig["vol_ratio"]        = vol_ratio         # ex: 1.8 = 80% acima da média
        sig["vol_high"]         = vol_high
        sig["atr_ratio"]        = atr_ratio         # ex: 0.4 = ATR bem abaixo da média
        sig["atr_low"]          = atr_low           # True = range morto

        return sig

    except Exception:
        # Nunca deixa o enriquecimento bugar o sinal — retorna original intacto
        return sig

# ════════════════════════════════════════════════════════════════════════
# SISTEMA 2 — GEMS / MACRO (app.py + visualizer.py)
# ════════════════════════════════════════════════════════════════════════
def _rebuild_macro(logger):
    """
    Chama visualizer._build_macro_timing() via subprocess para manter
    o JSON atualizado sem importar o Streamlit ou tvDatafeed aqui.
    """
    import subprocess
    # Procurar visualizer.py em gems_system
    script = os.path.join(PROJECT_DIR, "gems_system", "visualizer.py")
    if not os.path.exists(script):
        logger.warning(f"[GEMS] visualizer.py nao encontrado em {script}")
        return False
    try:
        gems_path = os.path.join(PROJECT_DIR, "gems_system")
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0,r'{gems_path}'); "
             "import visualizer; visualizer._build_macro_timing()"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
        )
        if result.returncode == 0:
            logger.info("[GEMS] macro_timing.json atualizado")
            return True
        logger.warning(f"[GEMS] rebuild falhou: {result.stderr[:200]}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("[GEMS] rebuild timeout (>120s)")
        return False
    except Exception as e:
        logger.warning(f"[GEMS] rebuild erro: {e}")
        return False

def _read_macro():
    if not os.path.exists(MACRO_JSON): return None
    try:
        with open(MACRO_JSON,"r",encoding="utf-8") as f: return json.load(f)
    except: return None

def _gems_signal_type(macro):
    """
    Determina tipo de sinal — copia EXATA da logica _macro_gems_signal_type
    + get_macro_data do app.py.
    CORRECAO: buy_mode/sell_mode/capitulation_lock lidos de macro['regime']
    (nao de macro['monthly'] — erro original do daemon).
    """
    signal    = macro.get("signal", {})
    regime    = macro.get("regime", {})            # ← correto: igual ao app.py
    buy_mode  = regime.get("buy_mode",  False)     # ← corrigido
    sell_mode = regime.get("sell_mode", False)     # ← corrigido
    weekly_buy  = signal.get("weekly_buy_trigger",  False)
    weekly_sell = signal.get("weekly_sell_trigger", False)
    funding     = float(macro.get("funding_rate", 0.01))
    rebound       = signal.get("tactical_rebound",       False)
    rebound_super = signal.get("tactical_rebound_super", False)
    cap_lock      = regime.get("capitulation_lock", False)   # ← corrigido: de regime{}

    if buy_mode:
        if weekly_buy and funding < 0:  return "SUPER_BUY"
        if weekly_buy:                  return "BUY"
    if sell_mode:
        if weekly_sell and funding > 0.08: return "SUPER_SELL"
        if weekly_sell:                    return "SELL"
        if rebound_super and not cap_lock: return "SUPER_REPIQUE"
        if rebound and not cap_lock:       return "REPIQUE"
    return None

# ════════════════════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ════════════════════════════════════════════════════════════════════════
def run_daemon(logger, mode="all"):
    do_trading = mode in ("all","trading")
    do_gems    = mode in ("all","gems")

    logger.info("=" * 64)
    logger.info("  MONTREZOR DAEMON UNIFICADO")
    logger.info(f"  Modo: {mode.upper()}")
    logger.info(f"  Trading : {'ATIVO' if do_trading else 'INATIVO'}  (a cada {TRADING_SCAN_SEC}s | cooldown {TRADING_COOLDOWN_MIN}min)")
    logger.info(f"  Gems    : {'ATIVO' if do_gems else 'INATIVO'}  (a cada {GEMS_SCAN_SEC}s | cooldown {GEMS_COOLDOWN_MIN}min)")
    logger.info(f"  Log     : {LOG_FILE}")
    logger.info("=" * 64)

    # Validacoes de startup
    if do_trading:
        if not _MT5_OK:
            logger.error("MetaTrader5 nao instalado: pip install MetaTrader5")
            if mode == "trading": sys.exit(1)
            do_trading = False
        elif not _mt5_init():
            logger.error("MT5 nao conectou. Abra o terminal MT5 e logue no broker.")
            if mode == "trading": sys.exit(1)
            do_trading = False
        else:
            info = mt5.terminal_info()
            logger.info(f"MT5 conectado: {info.name if info else 'desconhecido'}")

    # ── Trava por candle — idêntica ao trading_system.py ────────────────
    # lock_key = "{sym}|{tf_menor}|{signal_ts}"
    # Garante que o mesmo candle 4H ou 1D não gera Telegram duas vezes,
    # independente de quantos ciclos de 60s o sinal continuar ativo.
    # Coexiste com t_state (cooldown por direção/tipo) — são travas distintas:
    #   signals_lock → por candle (trava permanente enquanto o daemon roda)
    #   t_state      → por direção+tipo (cooldown de 4h, reseta ao sinal sumir)
    signals_lock = set()

    t_state = AlertState(TRADING_COOLDOWN_MIN)
    g_state = AlertState(GEMS_COOLDOWN_MIN)

    last_t_scan    = 0.0
    last_g_scan    = 0.0
    last_rebuild   = 0.0
    prev_t_active  = set()
    prev_gems_sig  = None

    while True:
        now = time.time()

        # ── TRADING ──────────────────────────────────────────────────
        if do_trading and (now - last_t_scan) >= TRADING_SCAN_SEC:
            last_t_scan = now
            cfg = load_config()
            active = set()

            for sym in cfg["symbols"]:
                try:
                    raw = {}
                    for tf in ["1mo","1wk","1d","4h"]:
                        df = _mt5_fetch(sym, tf)
                        if df is not None and len(df) >= 30:
                            raw[tf] = _build_indicators(df)
                    if not raw: continue

                    sig = check_signals_trading(raw, sym, cfg["athena"])
                    if sig is None:
                        for k in list(prev_t_active):
                            if k[0] == sym: t_state.clear(*k)
                        continue

                    # Enriquecer sinal — divergência, volume, ATR (nunca bloqueia)
                    sig = enrich_signal(sig, raw)

                    sk = (sym, sig["direction"], sig["type"])
                    active.add(sk)
                    tfs_str  = " ".join(sig.get("touch_tfs", [])) or "-"
                    div_str  = f" DIV={sig.get('div_grade','—')}" if sig.get('div_grade') else ""
                    vol_str  = f" VOL={sig.get('vol_ratio',1.0):.1f}x" if sig.get('vol_ratio') else ""
                    atr_str  = " ⚠️RANGE" if sig.get('atr_low') else ""
                    elev_str = f" ↑{sig.get('elevation_reason','')}" if sig.get('elevated') else ""
                    logger.info(f"[TRADING] {sig['type']:<5} {sym:<12} {sig['direction']:<6} "
                                f"@ {sig['price']:.5f} [{sig['tf_menor'].upper()}] "
                                f"tfs={tfs_str}{div_str}{vol_str}{atr_str}{elev_str}")

                    # ── Trava por candle (idêntica ao trading_system) ─────
                    tf_menor   = sig.get("tf_menor", "")
                    signal_ts  = sig.get("signal_ts")
                    lock_key   = None
                    if tf_menor in {"1d", "4h"} and signal_ts is not None:
                        lock_key = f"{sym}|{tf_menor}|{signal_ts}"

                    if lock_key is not None and lock_key in signals_lock:
                        # Candle já processado — só loga, não envia Telegram
                        logger.debug(f"  🔒 Candle já processado: {lock_key}")
                    elif t_state.ok(*sk):
                        ok = send_trading_tg(sym, sig["direction"], sig["type"],
                                             sig["price"], cfg["tg_token"], cfg["tg_chat_id"],
                                             touch_tfs=sig.get("touch_tfs"),
                                             enrich=sig)
                        if ok:
                            logger.info(f"  ✅ Telegram -> {sym} {sig['direction']} {sig['type']}")
                            t_state.mark(*sk)
                            if lock_key is not None:
                                signals_lock.add(lock_key)
                        else:
                            logger.error(f"  ❌ Telegram falhou -> {sym}")
                    else:
                        logger.debug(f"  ⏳ Cooldown t_state: {sym}")

                except Exception as e:
                    logger.exception(f"[TRADING] Erro {sym}: {e}")

            for k in (prev_t_active - active):
                t_state.clear(*k)
                logger.info(f"[TRADING] ↩ Sinal encerrado: {k[0]} {k[1]} {k[2]}")
            prev_t_active = active

        # ── GEMS: rebuild macro_timing.json ──────────────────────────
        if do_gems and (now - last_rebuild) >= MACRO_REBUILD_SEC:
            last_rebuild = now
            _rebuild_macro(logger)

        # ── GEMS: avaliar sinal ───────────────────────────────────────
        if do_gems and (now - last_g_scan) >= GEMS_SCAN_SEC:
            last_g_scan = now
            cfg   = load_config()
            macro = _read_macro()

            if macro is None:
                logger.warning("[GEMS] macro_timing.json nao encontrado.")
            else:
                sig_type = _gems_signal_type(macro)
                funding  = float(macro.get("funding_rate", 0.0))

                if sig_type is None:
                    if prev_gems_sig is not None:
                        g_state.clear("BTC", prev_gems_sig)
                        logger.info(f"[GEMS] ↩ Sinal encerrado: BTC {prev_gems_sig}")
                    prev_gems_sig = None
                else:
                    logger.info(f"[GEMS] {sig_type:<15} BTC  funding={funding:.4f}%")
                    if g_state.ok("BTC", sig_type):
                        ok = send_gems_tg("BTC", sig_type, funding,
                                         cfg["tg_token"], cfg["tg_chat_id"])
                        if ok:
                            logger.info(f"  ✅ Telegram -> BTC {sig_type}")
                            g_state.mark("BTC", sig_type)
                        else:
                            logger.error(f"  ❌ Telegram falhou -> BTC {sig_type}")
                    else:
                        logger.debug(f"  ⏳ Cooldown: BTC {sig_type}")
                    prev_gems_sig = sig_type

        time.sleep(5)

# ════════════════════════════════════════════════════════════════════════
# INSTALADOR WINDOWS
# ════════════════════════════════════════════════════════════════════════
def install_service(logger, mode):
    import subprocess
    task = "MontrezorDaemon"; py = sys.executable; sc = os.path.abspath(__file__)
    r = subprocess.run(["schtasks","/Query","/TN",task],capture_output=True,text=True,encoding="utf-8",errors="replace")
    if r.returncode == 0:
        if input(f"Tarefa '{task}' existe. Recriar? (s/n): ").strip().lower() != "s": return
        subprocess.run(["schtasks","/Delete","/TN",task,"/F"],check=True)
    cmd = (f'schtasks /Create /TN "{task}" '
           f'/TR "\\"{py}\\" \\"{sc}\\" --silent --only {mode}" '
           f"/SC ONLOGON /DELAY 0001:00 /RL HIGHEST /F")
    r2 = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r2.returncode == 0:
        logger.info(f"✅ Tarefa '{task}' criada. Log: {LOG_FILE}")
        logger.info("   Para remover: schtasks /Delete /TN MontrezorDaemon /F")
    else:
        logger.error(f"❌ Falha: {r2.stderr}  (execute como Administrador)")

def remove_service(logger):
    import subprocess
    r = subprocess.run(["schtasks","/Delete","/TN","MontrezorDaemon","/F"],
                       capture_output=True,text=True,encoding="utf-8",errors="replace")
    logger.info("✅ Removida." if r.returncode==0 else f"❌ {r.stderr}")

# ════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════
def main():
    global TRADING_SCAN_SEC, GEMS_SCAN_SEC
    p = argparse.ArgumentParser(description="Montrezor Daemon Unificado")
    p.add_argument("--silent", action="store_true")
    p.add_argument("--only", choices=["all","trading","gems"], default="all")
    p.add_argument("--install-service", action="store_true")
    p.add_argument("--remove-service",  action="store_true")
    p.add_argument("--trading-interval", type=int, default=TRADING_SCAN_SEC)
    p.add_argument("--gems-interval",    type=int, default=GEMS_SCAN_SEC)
    args = p.parse_args()

    TRADING_SCAN_SEC = args.trading_interval
    GEMS_SCAN_SEC    = args.gems_interval

    logger = setup_logging(args.silent)

    if args.install_service: install_service(logger, args.only); return
    if args.remove_service:  remove_service(logger); return

    try:
        run_daemon(logger, mode=args.only)
    except KeyboardInterrupt:
        logger.info("Daemon interrompido (Ctrl+C).")
    except Exception as e:
        logger.exception(f"Erro fatal: {e}"); sys.exit(1)
    finally:
        if _MT5_OK:
            try: mt5.shutdown()
            except: pass
        logger.info("Daemon encerrado.")

if __name__ == "__main__":
    main()
