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

def send_trading_tg(symbol, direction, sig_type, price, token, chat_id):
    token = _norm(token); chat_id = _norm(chat_id)
    if not token or not chat_id: return False
    icon = "COMPRA" == direction and "📈" or "📉"
    star = "⭐" if sig_type == "SUPER" else "•"
    e    = html.escape
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg  = (f"{icon} <b>SINAL {e(sig_type)}</b> {star}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Par</b>: {e(symbol)}\n<b>Direcao</b>: {e(direction)}\n"
            f"<b>Preco</b>: {price:.5f}\n<b>Hora</b>: {e(ts)}\n\nMontrezor Trading [daemon]")
    if _post(token, chat_id, msg): return True
    plain = f"SINAL {sig_type}\nPar: {symbol}\nDirecao: {direction}\nPreco: {price:.5f}\nHora: {ts}\nMontrezor [daemon]"
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

def _supertrend(df, period=10, mult=3.0):
    h=df["High"]; l=df["Low"]; cp=df["Close"].shift(1)
    tr=pd.concat([h-l,(h-cp).abs(),(l-cp).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/period,adjust=False).mean(); hl2=(h+l)/2
    ub0=hl2-(mult*atr); db0=hl2+(mult*atr)
    n=len(df); up=[np.nan]*n; dn=[np.nan]*n; tr_=[0]*n; cl=df["Close"].values
    for i in range(1,n):
        ub=ub0.iloc[i] if not np.isnan(ub0.iloc[i]) else 0
        db=db0.iloc[i] if not np.isnan(db0.iloc[i]) else 0
        pu=up[i-1] if not np.isnan(up[i-1]) else ub
        pd_=dn[i-1] if not np.isnan(dn[i-1]) else db
        up[i]=max(ub,pu) if cl[i-1]>pu else ub
        dn[i]=min(db,pd_) if cl[i-1]<pd_ else db
        if   tr_[i-1]==-1 and cl[i]>pd_: tr_[i]=1
        elif tr_[i-1]==1  and cl[i]<pu:  tr_[i]=-1
        else: tr_[i]=tr_[i-1] if tr_[i-1]!=0 else 1
    df=df.copy(); ta=np.array(tr_,dtype=int)
    df["ST_Line"]=np.where(ta==1,np.array(up,float),np.array(dn,float))
    df["ST_Trend"]=ta; return df

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
    df["RSI_Upper"]=np.nan; df["RSI_Lower"]=np.nan
    rv=df["RSI"].values; x=np.arange(lr_period,dtype=float)
    sx=float(np.sum(x)); sxx=float(np.sum(x*x)); denom=sx*sx-lr_period*sxx
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
        df.iloc[i,ul]=mid+err*mult; df.iloc[i,ll]=mid-err*mult
    return df

def _build_indicators(raw):
    df=_supertrend(raw); df["EMA_50"]=_ema(df["Close"],50)
    df["EMA_100"]=_ema(df["Close"],100); df["EMA_200"]=_ema(df["Close"],200)
    return _rsi_channel(df)

def _near(a,b,pct=0.015):
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

def _ema_near(r,pct=0.015):
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
    """Copia EXATA de check_signals do trading_system.py — sem alteracoes."""
    if "1mo" not in data or "1wk" not in data: return None
    mn_trend=data["1mo"].iloc[-1]; w1_trend=data["1wk"].iloc[-1]
    mn_rsi=data["1mo"].iloc[-1];   w1_rsi=data["1wk"].iloc[-1]
    if mn_rsi is None or w1_rsi is None: return None
    trend_mn=int(mn_trend.get("ST_Trend",0))
    if trend_mn==0: return None
    try:
        buy_ema =float(w1_trend["EMA_50"])>float(w1_trend["EMA_100"])>float(w1_trend["EMA_200"])
        sell_ema=float(w1_trend["EMA_50"])<float(w1_trend["EMA_100"])<float(w1_trend["EMA_200"])
    except: buy_ema=sell_ema=False
    if trend_mn==1:
        direction="COMPRA"
        if sell_ema: return None
    else:
        direction="VENDA"
        if buy_ema: return None
    tfn=_rsi_hit_bot if direction=="COMPRA" else _rsi_hit_top
    nfn=_rsi_near_bot if direction=="COMPRA" else _rsi_near_top
    NEAR=0.03
    d1_data=data.get("1d")
    d1_cur=_get_confirmed_row(d1_data,allow_current=True) if d1_data is not None else None
    hd1=(tfn(d1_cur) or nfn(d1_cur,NEAR)) if d1_cur is not None else False
    hh4=False; tfm4=None
    if "4h" in data:
        tfm4=_get_confirmed_row(data["4h"],allow_current=True)
        hh4=(tfn(tfm4) or nfn(tfm4,NEAR)) if tfm4 is not None else False
    if hh4 and tfm4 is not None: tfm=tfm4; tfk="4h"
    elif d1_cur is not None:     tfm=d1_cur; tfk="1d"
    else: return None
    hit_tfm=hd1 or hh4
    hw1=tfn(w1_rsi); hmn=tfn(mn_rsi)
    nw1=nfn(w1_rsi,NEAR); nmn=nfn(mn_rsi,NEAR)
    if not (hit_tfm and ((hw1 or nw1) or (hmn or nmn))): return None
    d1_cur=d1_data.iloc[-1] if d1_data is not None and not d1_data.empty else None
    if not (_ema_near(mn_trend) or _ema_near(w1_trend) or (_ema_near(d1_cur) if d1_cur else False)): return None
    c_price=float(tfm["Close"])
    na=athena_levels.get(symbol,{})
    try:
        st_line=float(tfm["ST_Line"]); c_low=float(tfm["Low"]); c_high=float(tfm["High"])
        touch_st=(c_low<=st_line<=c_high) or _near(c_price,st_line,pct=0.015)
    except: touch_st=False
    touch_na=False
    if direction=="COMPRA" and float(na.get("sell_entry",0))>0:
        touch_na=_near(c_price,na["sell_entry"],pct=0.012)
    elif direction=="VENDA" and float(na.get("buy_entry",0))>0:
        touch_na=_near(c_price,na["buy_entry"],pct=0.012)
    return {
        "symbol": symbol, "direction": direction,
        "type": "SUPER" if (touch_st or touch_na) else "COMUM",
        "price": c_price, "tf_menor": tfk,
    }

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
            capture_output=True, text=True, timeout=120
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

                    sk = (sym, sig["direction"], sig["type"])
                    active.add(sk)
                    logger.info(f"[TRADING] {sig['type']:<5} {sym:<12} {sig['direction']:<6} "
                                f"@ {sig['price']:.5f} [{sig['tf_menor'].upper()}]")

                    if t_state.ok(*sk):
                        ok = send_trading_tg(sym, sig["direction"], sig["type"],
                                             sig["price"], cfg["tg_token"], cfg["tg_chat_id"])
                        if ok:
                            logger.info(f"  ✅ Telegram -> {sym} {sig['direction']} {sig['type']}")
                            t_state.mark(*sk)
                        else:
                            logger.error(f"  ❌ Telegram falhou -> {sym}")
                    else:
                        logger.debug(f"  ⏳ Cooldown: {sym}")

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
    r = subprocess.run(["schtasks","/Query","/TN",task],capture_output=True,text=True)
    if r.returncode == 0:
        if input(f"Tarefa '{task}' existe. Recriar? (s/n): ").strip().lower() != "s": return
        subprocess.run(["schtasks","/Delete","/TN",task,"/F"],check=True)
    cmd = (f'schtasks /Create /TN "{task}" '
           f'/TR "\\"{py}\\" \\"{sc}\\" --silent --only {mode}" '
           f"/SC ONLOGON /DELAY 0001:00 /RL HIGHEST /F")
    r2 = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r2.returncode == 0:
        logger.info(f"✅ Tarefa '{task}' criada. Log: {LOG_FILE}")
        logger.info("   Para remover: schtasks /Delete /TN MontrezorDaemon /F")
    else:
        logger.error(f"❌ Falha: {r2.stderr}  (execute como Administrador)")

def remove_service(logger):
    import subprocess
    r = subprocess.run(["schtasks","/Delete","/TN","MontrezorDaemon","/F"],
                       capture_output=True,text=True)
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
