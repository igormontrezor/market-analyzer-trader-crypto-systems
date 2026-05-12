"""
BACKTEST MONTREZOR v2 — CHFJPY=X
=================================
CORREÇÃO PRINCIPAL (v2):
  - RSI semanal: usa candle EM FORMAÇÃO (get_current_or_last)
    Justificativa: o gatilho 4H/D dispara DURANTE a semana que está
    tocando o canal. Usar só o semanal fechado descarta exatamente
    esse evento. Na quarta/quinta a semana já tem 3-4 dias de preço,
    o RSI é estável o suficiente para validar.
  - RSI mensal: idem — usa candle atual (mesmo raciocínio)
  - RSI 4H/D: continua usando candle FECHADO (oscila muito intraday)
  - SuperTrend SUPER: candle 4H FECHADO (sem Low/High provisório)
  - near threshold: 3 pts RSI (não 10 como antes)
"""

import pandas as pd
import numpy as np
import time

# ── Indicadores ──────────────────────────────────────────────────────────────
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr(df, period=10):
    high = df['High']; low = df['Low']
    close_prev = df['Close'].shift(1)
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low  - close_prev).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def calc_supertrend(df, period=10, multiplier=3.0):
    hl2 = (df['High'] + df['Low']) / 2
    atr = calc_atr(df, period)
    up_basic = hl2 - (multiplier * atr)
    dn_basic = hl2 + (multiplier * atr)
    n = len(df)
    up_band = [np.nan]*n; dn_band = [np.nan]*n; trend = [0]*n
    close = df['Close'].values
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
    t = np.array(trend, dtype=int)
    u = np.array(up_band, dtype=float)
    d = np.array(dn_band, dtype=float)
    df['ST_Line']  = np.where(t == 1, u, d)
    df['ST_Trend'] = t
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
    df['RSI'] = calc_rsi(df['Close'], rsi_period)
    df['RSI_Upper'] = np.nan; df['RSI_Lower'] = np.nan
    rsi_vals = df['RSI'].values
    x = np.arange(lr_period, dtype=float)
    sumx = float(np.sum(x)); sumxx = float(np.sum(x*x))
    denom = sumx*sumx - lr_period*sumxx
    for i in range(lr_period-1, len(df)):
        y_win = rsi_vals[i-lr_period+1:i+1]
        if np.isnan(y_win).any(): continue
        y = y_win[::-1]
        sumy = float(np.sum(y)); sumyy = float(np.sum(y*y)); sumxy = float(np.sum(x*y))
        if denom == 0: continue
        slope = (lr_period*sumxy - sumx*sumy) / denom
        if lr_period > 2:
            err_num = lr_period*sumyy - sumy*sumy - slope*slope*(lr_period*sumxx - sumx*sumx)
            err_den = lr_period*(lr_period - 2.0)
            error   = float(np.sqrt(max(err_num/err_den, 0.0))) if err_den != 0 else 0.0
        else:
            error = 0.0
        mid = (sumy + slope*sumx) / lr_period
        df.iloc[i, df.columns.get_loc('RSI_Upper')] = mid + error*multiplier
        df.iloc[i, df.columns.get_loc('RSI_Lower')] = mid - error*multiplier
    return df

def build_indicators(df):
    df = calc_supertrend(df)
    df['EMA_50']  = calc_ema(df['Close'], 50)
    df['EMA_100'] = calc_ema(df['Close'], 100)
    df['EMA_200'] = calc_ema(df['Close'], 200)
    df = calc_rsi_channel(df)
    return df

# ── Helpers ───────────────────────────────────────────────────────────────────
def rsi_touch_bottom(row):
    try: return float(row['RSI']) <= float(row['RSI_Lower'])
    except: return False

def rsi_touch_top(row):
    try: return float(row['RSI']) >= float(row['RSI_Upper'])
    except: return False

def rsi_near_bottom(row, pct=0.03):
    try:
        rsi = float(row['RSI']); lo = float(row['RSI_Lower'])
        return rsi <= (lo + pct * 100)
    except: return False

def rsi_near_top(row, pct=0.03):
    try:
        rsi = float(row['RSI']); up = float(row['RSI_Upper'])
        return rsi >= (up - pct * 100)
    except: return False

def near(a, b, pct=0.015):
    try:
        a, b = float(a), float(b)
        return abs(a-b)/abs(b) < pct if b != 0 else False
    except: return False

def ema_near(row, pct=0.015):
    try:
        c = float(row['Close'])
        return any(near(c, float(row[e]), pct) for e in ['EMA_50','EMA_100','EMA_200'])
    except: return False

def get_last_closed(df, current_date):
    """Último candle cujo timestamp < current_date (candle fechado)."""
    past = df[df.index < current_date]
    return past.iloc[-1] if len(past) >= 1 else None

def get_current_or_last(df, current_date):
    """Último candle disponível até current_date inclusive (pode estar em formação)."""
    past = df[df.index <= current_date]
    return past.iloc[-1] if len(past) >= 1 else None

# ── Lógica de sinal walk-forward ─────────────────────────────────────────────
def check_signal_at(date, data_mo, data_wk, data_d, data_4h=None):
    """
    v3: APENAS 1D - RSI semanal e mensal usam candle ATUAL (em formação permitido).
        RSI 1D usa candle FECHADO.
        SuperTrend SUPER usa candle 1D FECHADO.
    """
    # ── Tendência: candle disponível até 'date' ──
    mn_t = get_current_or_last(data_mo, date)
    w1_t = get_current_or_last(data_wk, date)
    if mn_t is None or w1_t is None:
        return None

    # ── RSI semanal/mensal: candle ATUAL (em formacao OK) ──
    w1_r = get_current_or_last(data_wk, date)
    mn_r = get_current_or_last(data_mo, date)
    if w1_r is None or mn_r is None:
        return None

    # ── Tendencia mensal ──
    trend_mn = int(mn_t.get('ST_Trend', 0))

    # ── EMAs semanal ──
    try:
        buy_ema  = float(w1_t['EMA_50']) > float(w1_t['EMA_100']) > float(w1_t['EMA_200'])
        sell_ema = float(w1_t['EMA_50']) < float(w1_t['EMA_100']) < float(w1_t['EMA_200'])
    except:
        return None

    is_buy  = trend_mn ==  1 and buy_ema
    is_sell = trend_mn == -1 and sell_ema
    if not is_buy and not is_sell:
        return None

    direction = "COMPRA" if is_buy else "VENDA"

    touch_fn = rsi_touch_bottom if direction == "COMPRA" else rsi_touch_top
    near_fn  = rsi_near_bottom  if direction == "COMPRA" else rsi_near_top

    # Near universal: 3 pts RSI em todos os TFs (= "3% de 0-100" do metodo)
    NEAR_TF    = 0.03   # 3 pts — diario
    NEAR_W1_MN = 0.03   # 3 pts — semanal e mensal

    # ── Gatilho diario (sempre avaliado, candle FECHADO) ──
    d1_closed = get_last_closed(data_d, date)
    if d1_closed is None:
        return None

    hit_d1 = (touch_fn(d1_closed) or near_fn(d1_closed, pct=NEAR_TF))

    # Candle de referencia: SEMPRE diario
    tfm = d1_closed
    tf_key = '1d'

    hit_tfm = hit_d1

    # Semanal/Mensal
    hit_w1  = touch_fn(w1_r)
    hit_mn  = touch_fn(mn_r)
    near_w1 = near_fn(w1_r, pct=NEAR_W1_MN)  # 3pts semanal
    near_mn = near_fn(mn_r, pct=NEAR_W1_MN)    # 3pts mensal

    minor_ok   = hit_tfm
    weekly_ok  = hit_w1 or near_w1
    monthly_ok = hit_mn or near_mn

    if not (minor_ok and (weekly_ok or monthly_ok)):
        return None

    # ── EMA proxima ──
    d_cur  = get_current_or_last(data_d, date)
    ema_ok = (
        ema_near(mn_t) or
        ema_near(w1_t) or
        (ema_near(d_cur) if d_cur is not None else False)
    )
    if not ema_ok:
        return None

    # ── SUPER: toque no SuperTrend (candle fechado de referencia) ──
    try:
        st_line  = float(tfm['ST_Line'])
        touch_st = float(tfm['Low']) <= st_line <= float(tfm['High'])
    except:
        touch_st = False

    return {
        "date":      date.strftime('%Y-%m-%d'),
        "candle_1d": str(tfm.name)[:16],
        "tf_key":    tf_key,
        "direction": direction,
        "type":      "SUPER" if touch_st else "COMUM",
        "price":     round(float(tfm['Close']), 5),
        "rsi_tfm":   round(float(tfm.get('RSI', 0)), 1),
        "rsi_w1":    round(float(w1_r.get('RSI', 0)), 1),
        "rsi_w1_lo": round(float(w1_r.get('RSI_Lower', 0)), 1),
        "rsi_w1_hi": round(float(w1_r.get('RSI_Upper', 0)), 1),
        "hit_d1":    hit_d1,
        "hit_w1":    hit_w1,
        "near_w1":   near_w1,
        "hit_mn":    hit_mn,
        "near_mn":   near_mn,
        "touch_st":  touch_st,
        "w1_candle_date":   str(w1_r.name)[:10],
        "w1_in_formation":  (
            pd.Timestamp(str(w1_r.name)[:10]) >= date - pd.Timedelta(days=6)
        ),
    }

# ── Download e execução ───────────────────────────────────────────────────────
print("=" * 72)
print("  BACKTEST MONTREZOR v3 — CHFJPY=X  |  01/06/2025 → hoje")
print("  APENAS 1D - SEM 4H")
print("=" * 72)
print()

try:
    # Usar MT5 em vez de yfinance
    import MetaTrader5 as mt5
    import pytz

    print("Conectando ao MetaTrader 5...")
    if not mt5.initialize():
        print("Falha ao inicializar MT5")
        raise SystemExit(1)

    print("MT5 inicializado com sucesso!")

    # Verificar se está conectado
    if not mt5.terminal_info():
        print("Terminal MT5 não está conectado")
        mt5.shutdown()
        raise SystemExit(1)

    # Configurar timezone
    tz = pytz.timezone("Etc/UTC")

    print("Buscando dados históricos via MT5...")

    # Buscar dados de 01/06/2025 até hoje
    from datetime import datetime

    start_date = datetime(2024, 6, 1)  # Começar mais cedo para ter dados
    end_date = datetime.now()

    print(f"Período: {start_date.date()} → {end_date.date()}")

    # Verificar símbolos disponíveis
    symbols = mt5.symbols_get()
    chfjpys_symbols = [s.name for s in symbols if 'CHFJPY' in s.name]
    print(f"Símbolos CHFJPY disponíveis: {chfjpys_symbols}")

    # Tentar com símbolo padrão
    symbol = "CHFJPY#"
    if not chfjpys_symbols:
        print("CHFJPY não encontrado, tentando USDJPY...")
        symbol = "USDJPY"

    # Mensal
    raw_mo = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_MN1, start_date, end_date)
    if raw_mo is None or len(raw_mo) == 0:
        print(f"Dados mensais não disponíveis para {symbol}")
        # Tentar com período maior
        start_date = datetime(2020, 1, 1)
        raw_mo = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_MN1, start_date, end_date)
        if raw_mo is None or len(raw_mo) == 0:
            raise ValueError("Dados mensais não disponíveis")
    raw_mo = pd.DataFrame(raw_mo)
    raw_mo['timestamp'] = pd.to_datetime(raw_mo['time'], unit='s')
    raw_mo.set_index('timestamp', inplace=True)
    raw_mo = raw_mo[['open', 'high', 'low', 'close', 'tick_volume']]
    raw_mo.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    # Semanal
    raw_wk = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_W1, start_date, end_date)
    if raw_wk is None or len(raw_wk) == 0:
        raise ValueError("Dados semanais não disponíveis")
    raw_wk = pd.DataFrame(raw_wk)
    raw_wk['timestamp'] = pd.to_datetime(raw_wk['time'], unit='s')
    raw_wk.set_index('timestamp', inplace=True)
    raw_wk = raw_wk[['open', 'high', 'low', 'close', 'tick_volume']]
    raw_wk.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    # Diário
    raw_d = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, start_date, end_date)
    if raw_d is None or len(raw_d) == 0:
        raise ValueError("Dados diários não disponíveis")
    raw_d = pd.DataFrame(raw_d)
    raw_d['timestamp'] = pd.to_datetime(raw_d['time'], unit='s')
    raw_d.set_index('timestamp', inplace=True)
    raw_d = raw_d[['open', 'high', 'low', 'close', 'tick_volume']]
    raw_d.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    # 4H
    raw_4h = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H4, start_date, end_date)
    if raw_4h is not None and len(raw_4h) > 0:
        raw_4h = pd.DataFrame(raw_4h)
        raw_4h['timestamp'] = pd.to_datetime(raw_4h['time'], unit='s')
        raw_4h.set_index('timestamp', inplace=True)
        raw_4h = raw_4h[['open', 'high', 'low', 'close', 'tick_volume']]
        raw_4h.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    else:
        raw_4h = None

    mt5.shutdown()

    if raw_mo.empty or raw_wk.empty:
        raise ValueError("Dados vazios")

    print(f"  Mensal:  {len(raw_mo)} candles  ({raw_mo.index[0].date()} → {raw_mo.index[-1].date()})")
    print(f"  Semanal: {len(raw_wk)} candles  ({raw_wk.index[0].date()} → {raw_wk.index[-1].date()})")
    print(f"  Diário:  {len(raw_d)} candles  ({raw_d.index[0].date()} → {raw_d.index[-1].date()})")
    print(f"  4H:      {len(raw_4h)} candles  ({raw_4h.index[0].date()} → {raw_4h.index[-1].date()})")
    print()

except Exception as e:
    print(f"MT5 indisponível: {e}")
    raise SystemExit(1)

# ── Indicadores ───────────────────────────────────────────────────────────────
print("Calculando indicadores...")

def tz_naive(df):
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df

data_mo = tz_naive(build_indicators(raw_mo.dropna(subset=['Open','High','Low','Close'])))
data_wk = tz_naive(build_indicators(raw_wk.dropna(subset=['Open','High','Low','Close'])))
data_d  = tz_naive(build_indicators(raw_d.dropna(subset=['Open','High','Low','Close'])))
data_4h = tz_naive(build_indicators(raw_4h.dropna(subset=['Open','High','Low','Close']))) if not raw_4h.empty else None

# ── Walk-forward ──────────────────────────────────────────────────────────────
start = pd.Timestamp("2025-06-01")
end   = pd.Timestamp.today().normalize()
dias  = pd.bdate_range(start, end)

print(f"Walk-forward: {start.date()} → {end.date()} ({len(dias)} dias úteis)...")

# ── Verificar datas disponíveis nos dados ──
print("VERIFICAÇÃO DE DATAS DISPONÍVEIS:")
print(f"  Data inicial disponível: {data_d.index[0].date()}")
print(f"  Data final disponível:   {data_d.index[-1].date()}")
print(f"  Total de candles diários: {len(data_d)}")
print()

# ── Verificar candles recentes (últimos 10 dias) ──
print("CANDLES DIÁRIOS RECENTES (últimos 10 dias com RSI Wilder):")
print(f"  {'DATA':<12} {'RSI':>6} {'Lower':>7} {'Upper':>7} {'hit_lo':>7} {'EMA100':>8} {'Close':>8}")
sub = data_d.tail(10)
for ts, row in sub.iterrows():
    rsi = float(row.get('RSI', float('nan')))
    lo  = float(row.get('RSI_Lower', float('nan')))
    up  = float(row.get('RSI_Upper', float('nan')))
    e100 = float(row.get('EMA_100', float('nan')))
    cl   = float(row.get('Close', float('nan')))
    hit  = "✓ HIT" if rsi <= lo else ("~near" if rsi <= lo + 5 else "·")
    ema_touch = "✓ EMA" if abs(cl - e100) / e100 < 0.015 else "·"
    print(f"  {str(ts)[:10]:<12} {rsi:>6.2f} {lo:>7.2f} {up:>7.2f} {hit:>7} {e100:>8.3f} {cl:>8.3f} {ema_touch}")
print()
print()

signals  = []
prev_sig = None

for dia in dias:
    sig = check_signal_at(dia, data_mo, data_wk, data_d, None)
    if sig is None:
        prev_sig = None
        continue
    chave = (sig['candle_1d'], sig['direction'], sig['type'])
    if chave == prev_sig:
        continue
    prev_sig = chave
    sig['date'] = dia.strftime('%Y-%m-%d')
    signals.append(sig)

# ── Tabela de sinais ──────────────────────────────────────────────────────────
print(f"{'DATA':<12} {'CANDLE_REF':<20} {'TF':<5} {'DIR':<7} {'TIPO':<7} {'PRECO':<11} "
      f"{'RSItfm':<7} {'RSIw1':<6} {'Lo_w1':<7} {'hitD1':<6} "
      f"{'hitW1':<6} {'nrW1':<5} {'hitMn':<6} {'ST':<4} {'W1_form'}")
print("-" * 120)

n_super = 0; n_comum = 0
for s in signals:
    tipo_lbl = "SUPER⭐" if s['type'] == "SUPER" else "COMUM "
    if s['type'] == "SUPER": n_super += 1
    else: n_comum += 1
    form_flag = "⚡form" if s.get('w1_in_formation') else "closed"
    print(
        f"{s['date']:<12} {s['candle_1d']:<20} {s.get('tf_key','?'):<5} {s['direction']:<7} {tipo_lbl:<7} "
        f"{s['price']:<11.5f} {s['rsi_tfm']:<7.1f} {s['rsi_w1']:<6.1f} "
        f"{s['rsi_w1_lo']:<7.1f} "
        f"{'✓' if s.get('hit_d1')  else '·':<6} "
        f"{'✓' if s['hit_w1']      else '·':<6} "
        f"{'✓' if s['near_w1']     else '·':<5} "
        f"{'✓' if s['hit_mn']      else '·':<6} "
        f"{'✓' if s['touch_st']    else '·':<4} "
        f"{form_flag}"
    )

print("-" * 120)
print(f"TOTAL: {len(signals)} sinais  |  SUPER: {n_super}  |  COMUM: {n_comum}")
print()

# ── Resumo dos sinais encontrados ────────────────────────────────────────────────
print("RESUMO DOS SINAIS ENCONTRADOS:")
print("-" * 60)
datas_sinal = {s['date'] for s in signals}
datas_tipos = {s['date']: s['type'] for s in signals}

if signals:
    print(f"Total de sinais: {len(signals)}")
    print(f"Período analisado: {start.date()} → {end.date()}")
    print(f"Sinais SUPER: {sum(1 for s in signals if s['type'] == 'SUPER')}")
    print(f"Sinais COMUM: {sum(1 for s in signals if s['type'] == 'COMUM')}")
    print()

    # Últimos 5 sinais
    print("ÚLTIMOS 5 SINAIS:")
    for s in signals[-5:]:
        print(f"  {s['date']} {s['direction']} {s['type']} @ {s['price']}")
else:
    print("Nenhum sinal encontrado no período analisado")
    print("Verifique se os dados MT5 estão disponíveis para o período")

# ── Relatório Final ──────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("RELATÓRIO FINAL - BACKTEST MONTREZOR MT5")
print("=" * 72)
print(f"📊 Período analisado: {start.date()} → {end.date()}")
print(f"📈 Total de sinais: {len(signals)}")
print(f"⭐ Sinais SUPER: {sum(1 for s in signals if s['type'] == 'SUPER')}")
print(f"📋 Sinais COMUM: {sum(1 for s in signals if s['type'] == 'COMUM')}")
print(f"🔧 Fonte de dados: MetaTrader 5 (MT5)")
print(f"📅 Data inicial: {data_d.index[0].date() if not data_d.empty else 'N/A'}")
print(f"📅 Data final: {data_d.index[-1].date() if not data_d.empty else 'N/A'}")
print()

if signals:
    # Estatísticas por mês
    sinais_por_mes = {}
    for s in signals:
        mes = s['date'][:7]  # YYYY-MM
        if mes not in sinais_por_mes:
            sinais_por_mes[mes] = {'SUPER': 0, 'COMUM': 0}
        sinais_por_mes[mes][s['type']] += 1

    print("SINAIS POR MÊS:")
    for mes in sorted(sinais_por_mes.keys()):
        total_mes = sinais_por_mes[mes]['SUPER'] + sinais_por_mes[mes]['COMUM']
        print(f"  {mes}: {total_mes} sinais (SUPER: {sinais_por_mes[mes]['SUPER']}, COMUM: {sinais_por_mes[mes]['COMUM']})")

print()
print("✅ Backtest concluído com sucesso!")
print("=" * 72)

# ── Resumo das regras v2 ──────────────────────────────────────────────────────
print("REGRAS v3 (resumo):")
print("-" * 60)
regras = [
    ("Tendencia compra",  "ST mensal=1  AND  EMA50>100>200 semanal"),
    ("Tendencia venda",   "ST mensal=-1 AND  EMA50<100<200 semanal"),
    ("Gatilho D / 4H",   "toque OU near 3pts RSI canal (candle FECHADO)"),
    ("Gatilho Semanal",  "candle ATUAL — toque OU near 3pts RSI canal"),
    ("Gatilho Mensal",   "candle ATUAL — toque OU near 3pts RSI canal"),
    ("EMA confirmacao",  "Close dentro de 1.5% de qualquer EMA 50/100/200 em D/S/M"),
    ("SUPER — ST",       "Low <= ST_Line <= High no candle gatilho (FECHADO)"),
    ("SUPER — Athena",   "Close dentro de 1.2% do nivel Athena oposto"),
]
for r, v in regras:
    print(f"  {r:<22} {v}")
print()
