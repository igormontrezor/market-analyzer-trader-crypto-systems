"""
MONTREZOR BACKTEST TAB — Fonte: CSV exportado do MT5
=====================================================
Arquivo separado — não altera trading_system.py.

Como exportar os CSVs do MT5:
  1. Abra o gráfico do ativo no MT5
  2. Mude para cada timeframe (MN1, W1, D1, H4)
  3. Menu: Arquivo → Salvar como → CSV
  4. Nomeie como: CHFJPY#_MN1.csv, CHFJPY#_W1.csv, CHFJPY#_D1.csv, CHFJPY#_H4.csv
  5. Coloque todos na pasta: montrezor_csv/ (mesma pasta do trading_system.py)

Como usar no trading_system.py:
    from backtest_tab import render_backtest_tab
    render_backtest_tab(st.session_state.tracked_symbols,
                        st.session_state.neuro_athena)
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import glob
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Importar indicadores do trading_system ──────────────────────────────────
try:
    from trading_system import _build_indicators, check_signals
    _TS_AVAILABLE = True
except ImportError as e:
    _TS_AVAILABLE = False
    _TS_ERROR = str(e)

# ── Config ──────────────────────────────────────────────────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))
CSV_DIR  = os.path.join(_HERE, "montrezor_csv")

TF_SUFFIX = {"MN1": "1mo", "W1": "1wk", "D1": "1d", "H4": "4h"}

BT_RESULTS_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_backtest.json")

# ── Persistência ─────────────────────────────────────────────────────────────
def _save_bt_results(r: dict):
    try:
        ex = _load_bt_results(); ex.update(r)
        with open(BT_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(ex, f, indent=2, default=str)
    except Exception: pass

def _load_bt_results() -> dict:
    try:
        if os.path.exists(BT_RESULTS_FILE):
            with open(BT_RESULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception: pass
    return {}

# ── Leitura de CSV do MT5 ────────────────────────────────────────────────────
def _load_mt5_csv(path: str) -> pd.DataFrame | None:
    try:
        # 1. Lê a primeira linha para identificar codificação e cabeçalho
        try:
            with open(path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
            encoding_used = 'utf-8'
        except UnicodeDecodeError:
            with open(path, 'r', encoding='utf-16') as f:
                first_line = f.readline().strip()
            encoding_used = 'utf-16'

        if not first_line:
            st.error(f"O arquivo {os.path.basename(path)} está vazio.")
            return None

        # Define o separador (vírgula ou tab)
        sep = ',' if ',' in first_line else '\t'

        # 2. A MÁGICA: Arquivos sem cabeçalho (como os seus) começam com número (ex: 1992)
        if first_line[0].isdigit():
            # Lê forçando que não tem cabeçalho (header=None)
            df = pd.read_csv(path, sep=sep, encoding=encoding_used, header=None)
            # Nomeia as colunas baseadas na posição padrão (0=Data, 1=Open, 2=High, 3=Low, 4=Close, 5=Vol)
            df = df.rename(columns={0: "DATE", 1: "OPEN", 2: "HIGH", 3: "LOW", 4: "CLOSE", 5: "VOLUME"})
        else:
            # Tem cabeçalho normal
            df = pd.read_csv(path, sep=sep, encoding=encoding_used)
            df.columns = [str(c).strip().strip("<>").upper() for c in df.columns]
            traducao_pt_en = {
                "DATA": "DATE", "HORA": "TIME",
                "ABERTURA": "OPEN", "MÁXIMA": "HIGH", "MAXIMA": "HIGH",
                "MÍNIMA": "LOW", "MINIMA": "LOW",
                "FECHAMENTO": "CLOSE", "VOLTICK": "VOLUME", "TICKVOL": "VOLUME"
            }
            df = df.rename(columns=traducao_pt_en)

        # 3. Formatar a data (junta DATE e TIME se estiverem separados)
        if "DATE" in df.columns and "TIME" in df.columns:
            df["_dt"] = pd.to_datetime(df["DATE"].astype(str) + " " + df["TIME"].astype(str), errors="coerce")
        elif "DATE" in df.columns:
            df["_dt"] = pd.to_datetime(df["DATE"], errors="coerce")
        else:
            st.error(f"Falha em {os.path.basename(path)}: Coluna DATE não encontrada.")
            return None

        # 4. Limpeza final e Indexação
        df = df.dropna(subset=["_dt"]).set_index("_dt").sort_index()
        df.index.name = "Date"

        # Garantir padrão interno de nomes (Open, High, Low, Close)
        df = df.rename(columns={"OPEN":"Open", "HIGH":"High", "LOW":"Low", "CLOSE":"Close", "VOLUME":"Volume"})

        if not all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
            st.error(f"Falha em {os.path.basename(path)}: Faltam colunas de Preço (OHLC).")
            return None

        if "Volume" not in df.columns:
            df["Volume"] = 0

        # 5. Validação de tamanho do histórico
        if len(df) <= 60:
            st.warning(f"Atenção: {os.path.basename(path)} tem apenas {len(df)} velas. O sistema exige > 60.")
            return None

        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    except Exception as e:
        st.error(f"Erro fatal ao ler {os.path.basename(path)}: {str(e)}")
        return None

def _find_csv(symbol: str, suffix: str) -> str | None:
    sym = symbol.replace("#","").upper()
    for p in [
        os.path.join(CSV_DIR, f"{symbol}_{suffix}.csv"),
        os.path.join(CSV_DIR, f"{sym}_{suffix}.csv"),
        os.path.join(CSV_DIR, f"{symbol.lower()}_{suffix.lower()}.csv"),
    ]:
        if os.path.exists(p): return p
    matches = glob.glob(os.path.join(CSV_DIR, f"*{sym}*{suffix}*.csv"))
    return matches[0] if matches else None

def _load_symbol_data(symbol: str) -> dict:
    data = {}
    for suffix, key in TF_SUFFIX.items():
        path = _find_csv(symbol, suffix)
        if path:
            df = _load_mt5_csv(path)
            if df is not None and len(df) > 60:
                data[key] = _build_indicators(df)
    return data

# ── Walk-forward ─────────────────────────────────────────────────────────────
def _run_backtest(symbol, athena_levels, rr=2.0, sl_atr_mult=1.5,
                  min_bars_between=5, start_date=None, end_date=None):

    raw = _load_symbol_data(symbol)
    missing = [tf for tf in ["1mo","1wk","1d"] if tf not in raw]
    if missing:
        return {"error": f"CSVs não encontrados: {', '.join(missing)} — verifique montrezor_csv/"}

    d1 = raw["1d"]
    if start_date: d1 = d1[d1.index >= pd.Timestamp(start_date)]
    if end_date:   d1 = d1[d1.index <= pd.Timestamp(end_date)]
    if len(d1) < 60:
        return {"error": "Período muito curto — mínimo 60 barras D1"}

    trades = []; last_i = -999

    for i in range(60, len(d1) - 1):
        if (i - last_i) < min_bars_between: continue
        bar_ts = d1.index[i]

        snap = {tf: df[df.index <= bar_ts] for tf, df in raw.items()
                if len(df[df.index <= bar_ts]) >= 14}
        if not all(tf in snap for tf in ["1mo","1wk","1d"]): continue

        sig = check_signals(snap, symbol, athena_levels)
        if sig is None: continue

        entry_px = float(d1.iloc[i]["Close"])
        atr_w    = d1.iloc[max(0,i-14):i+1]
        tr       = pd.concat([
            atr_w["High"] - atr_w["Low"],
            (atr_w["High"] - atr_w["Close"].shift(1)).abs(),
            (atr_w["Low"]  - atr_w["Close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr_val  = float(tr.mean()) if len(tr) > 0 else entry_px * 0.005
        sl_d     = atr_val * sl_atr_mult
        tp_d     = sl_d * rr
        buy      = sig["direction"] == "COMPRA"
        sl_px    = entry_px - sl_d if buy else entry_px + sl_d
        tp_px    = entry_px + tp_d if buy else entry_px - tp_d

        result = "ABERTO"; bars_out = 0; exit_px = None
        for j in range(i+1, min(i+61, len(d1))):
            f = d1.iloc[j]; bars_out += 1
            if buy:
                if float(f["Low"])  <= sl_px: result="LOSS"; exit_px=sl_px; break
                if float(f["High"]) >= tp_px: result="WIN";  exit_px=tp_px; break
            else:
                if float(f["High"]) >= sl_px: result="LOSS"; exit_px=sl_px; break
                if float(f["Low"])  <= tp_px: result="WIN";  exit_px=tp_px; break
        if result == "ABERTO":
            exit_px = float(d1.iloc[min(i+60, len(d1)-1)]["Close"])

        pnl_r = rr if result=="WIN" else (-1.0 if result=="LOSS" else 0.0)
        trades.append({
            "date": str(bar_ts)[:10], "direction": sig["direction"],
            "type": sig["type"], "entry": round(entry_px,5),
            "sl": round(sl_px,5), "tp": round(tp_px,5),
            "exit": round(exit_px,5) if exit_px else None,
            "result": result, "pnl_r": pnl_r, "bars_out": bars_out,
            "touch_tfs": sig.get("touch_tfs",[]),
        })
        last_i = i

    if not trades:
        return {"error": "Nenhum sinal gerado no período"}

    closed  = [t for t in trades if t["result"] != "ABERTO"]
    wins    = [t for t in closed if t["result"] == "WIN"]
    supers  = [t for t in closed if t["type"]   == "SUPER"]
    comuns  = [t for t in closed if t["type"]   == "COMUM"]

    wr      = len(wins)/len(closed)*100 if closed else 0
    total_r = sum(t["pnl_r"] for t in closed)

    equity = [0.0]
    for t in closed: equity.append(equity[-1] + t["pnl_r"])
    peak = 0.0; max_dd = 0.0
    for v in equity:
        if v > peak: peak = v
        if peak - v > max_dd: max_dd = peak - v

    swr = len([t for t in supers if t["result"]=="WIN"])/len(supers)*100 if supers else None
    cwr = len([t for t in comuns if t["result"]=="WIN"])/len(comuns)*100 if comuns else None

    return {
        "symbol": symbol, "total": len(closed),
        "wins": len(wins), "losses": len(closed)-len(wins),
        "win_rate": round(wr,1), "total_r": round(total_r,2),
        "avg_bars": round(np.mean([t["bars_out"] for t in closed]),1) if closed else 0,
        "max_dd_r": round(max_dd,2),
        "super_wr": round(swr,1) if swr is not None else None,
        "comum_wr": round(cwr,1) if cwr is not None else None,
        "n_super": len(supers), "n_comum": len(comuns),
        "equity": equity, "trades": trades,
        "rr": rr, "sl_atr_mult": sl_atr_mult,
        "period": f"{start_date or 'início'} → {end_date or 'hoje'}",
        "ran_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
    }

# ── UI ────────────────────────────────────────────────────────────────────────
def render_backtest_tab(tracked_symbols: list, neuro_athena: dict):

    if not _TS_AVAILABLE:
        st.error(f"trading_system.py não encontrado: {_TS_ERROR}")
        return

    saved = _load_bt_results()

    with st.expander("📂 Como preparar os CSVs do MT5",
                     expanded=not os.path.exists(CSV_DIR)):
        st.markdown(f"""
**1.** Crie a pasta **`montrezor_csv/`** na mesma pasta do `trading_system.py`

**2.** No MT5: abra o gráfico → mude o timeframe → **Arquivo → Salvar como → CSV**

**3.** Nomeie assim:

| TF | Nome do arquivo |
|---|---|
| Mensal | `CHFJPY#_MN1.csv` |
| Semanal | `CHFJPY#_W1.csv` |
| Diário | `CHFJPY#_D1.csv` |
| 4H | `CHFJPY#_H4.csv` |

**4.** Repita para cada ativo · Pasta: `{CSV_DIR}`
        """)

    # Detectar símbolos disponíveis pelos CSVs
    available = []
    if os.path.exists(CSV_DIR):
        found = set()
        for f in glob.glob(os.path.join(CSV_DIR, "*.csv")):
            name = os.path.basename(f).upper()
            for suf in TF_SUFFIX:
                if f"_{suf}.CSV" in name:
                    found.add(name.replace(f"_{suf}.CSV",""))
        available = sorted(found)

    if not available:
        st.warning(f"Nenhum CSV em `{CSV_DIR}`. Siga o guia acima.")
        return

    # Controles
    c1,c2,c3,c4,c5 = st.columns([3,1,1,2,2])
    with c1: sym  = st.selectbox("Ativo", available, key="bt_sym")
    with c2: rr   = st.number_input("R:R", 1.0, 5.0, 2.0, 0.5, key="bt_rr")
    with c3: slm  = st.number_input("SL ATR×", 0.5, 4.0, 1.5, 0.5, key="bt_sl")
    with c4: sd   = st.date_input("De", pd.Timestamp.now()-pd.DateOffset(years=2), key="bt_sd")
    with c5: ed   = st.date_input("Até", pd.Timestamp.now(), key="bt_ed")

    b1,b2,b3 = st.columns([2,2,1])
    with b1: run1 = st.button("▶ Rodar Backtest", type="primary",
                               use_container_width=True, key="bt_run")
    with b2: rall = st.button("▶▶ Rodar Todos", use_container_width=True, key="bt_all")
    with b3:
        if st.button("🗑 Limpar", use_container_width=True, key="bt_clr"):
            if os.path.exists(BT_RESULTS_FILE): os.remove(BT_RESULTS_FILE)
            st.rerun()

    to_run = ([sym] if run1 else []) + (available if rall else [])
    to_run = list(dict.fromkeys(to_run))  # dedup mantendo ordem

    if to_run:
        prog = st.progress(0); ph = st.empty(); new = {}
        for idx, s in enumerate(to_run):
            ph.info(f"⏳ {s} ({idx+1}/{len(to_run)}) — walk-forward em andamento...")
            new[s] = _run_backtest(s, neuro_athena, rr=rr, sl_atr_mult=slm,
                                    start_date=str(sd), end_date=str(ed))
            prog.progress((idx+1)/len(to_run))
        _save_bt_results(new); saved = _load_bt_results()
        ph.empty(); prog.empty()
        st.success(f"✅ Concluído — {len(to_run)} ativo(s)")

    if not saved:
        st.info("Clique em Rodar Backtest para começar.")
        return

    # ── Resultado individual ─────────────────────────────────
    if sym in saved:
        res = saved[sym]
        if "error" in res:
            st.error(f"{sym}: {res['error']}")
        else:
            st.markdown(f"#### {sym} · R:R {res['rr']} · SL {res['sl_atr_mult']}×ATR · "
                        f"{res.get('period','')} · *{res.get('ran_at','')}*")

            m1,m2,m3,m4,m5,m6 = st.columns(6)
            m1.metric("Win Rate",  f"{res['win_rate']}%")
            m2.metric("Total R",   f"{res['total_r']:+.1f}R", delta=f"{res['total_r']:+.1f}R")
            m3.metric("Trades",    res['total'])
            m4.metric("Max DD",    f"-{res['max_dd_r']:.1f}R")
            m5.metric("SUPER WR",  f"{res['super_wr']}%" if res['super_wr'] is not None else "—",
                       delta=f"{res['n_super']} trades")
            m6.metric("COMUM WR",  f"{res['comum_wr']}%" if res['comum_wr'] is not None else "—",
                       delta=f"{res['n_comum']} trades")

            eq = res['equity']
            eq_x = ["Início"] + [t['date'] for t in res['trades'] if t['result'] != "ABERTO"]
            pnls = [t['pnl_r'] for t in res['trades'] if t['result'] != "ABERTO"]
            tdts = [t['date']  for t in res['trades'] if t['result'] != "ABERTO"]

            fig = make_subplots(rows=2, cols=1, row_heights=[0.7,0.3],
                                shared_xaxes=True, vertical_spacing=0.06)
            fig.add_trace(go.Scatter(
                x=eq_x[:len(eq)], y=eq, mode='lines+markers', name='Equity (R)',
                line=dict(color='#3fb950', width=2), marker=dict(size=4),
                fill='tozeroy', fillcolor='rgba(63,185,80,0.08)',
            ), row=1, col=1)
            fig.add_hline(y=0, line_dash="dot", line_color="#484f58", row=1, col=1)
            fig.add_trace(go.Bar(
                x=tdts, y=pnls, name='P&L (R)',
                marker_color=['#3fb950' if p>0 else '#f85149' for p in pnls],
                showlegend=False,
            ), row=2, col=1)
            fig.update_layout(height=480, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(0,0,0,0)',
                              font=dict(color='#8b949e', size=11),
                              legend=dict(bgcolor='rgba(0,0,0,0)'),
                              margin=dict(l=0,r=0,t=10,b=0))
            fig.update_xaxes(gridcolor='#21262d')
            fig.update_yaxes(gridcolor='#21262d')
            st.plotly_chart(fig, use_container_width=True)

            with st.expander(f"📋 Trades ({res['total']})", expanded=False):
                rows = [{
                    "Data":   t['date'],
                    "Dir":    "▲" if t['direction']=="COMPRA" else "▼",
                    "Tipo":   t['type'],
                    "Entrada":t['entry'], "SL":t['sl'], "TP":t['tp'],
                    "Result": ("✅ " if t['result']=="WIN" else "❌ " if t['result']=="LOSS" else "⏳ ") + t['result'],
                    "R":      f"{t['pnl_r']:+.1f}R",
                    "Barras": t['bars_out'],
                    "TFs":    " ".join(t.get('touch_tfs',[])),
                } for t in res['trades']]
                st.dataframe(rows, use_container_width=True, hide_index=True)
                st.download_button("📥 CSV", pd.DataFrame(res['trades']).to_csv(index=False),
                                   f"bt_{sym}.csv", "text/csv", key="bt_dl1")

    st.markdown("---")

    # ── Comparativo multi-ativo ──────────────────────────────
    valid = {s:r for s,r in saved.items() if "error" not in r}
    if len(valid) > 1:
        st.markdown("#### 📊 Comparativo — Todos os Ativos")
        colors = ['#3fb950','#58a6ff','#f78166','#d2a8ff','#ffa657','#79c0ff']
        summary = []; eqfig = go.Figure()

        for ci,(s,r) in enumerate(sorted(valid.items())):
            summary.append({
                "Ativo":s, "Período":r.get("period",""), "Trades":r['total'],
                "Win Rate":f"{r['win_rate']}%", "Total R":f"{r['total_r']:+.2f}R",
                "Max DD":f"-{r['max_dd_r']:.1f}R",
                "SUPER WR":f"{r['super_wr']}%" if r['super_wr'] is not None else "—",
                "COMUM WR":f"{r['comum_wr']}%" if r['comum_wr'] is not None else "—",
                "Avg Barras":r['avg_bars'],
            })
            xdts = ["Início"]+[t['date'] for t in r['trades'] if t['result']!="ABERTO"]
            eqfig.add_trace(go.Scatter(x=xdts[:len(r['equity'])], y=r['equity'],
                                        mode='lines', name=s,
                                        line=dict(color=colors[ci%len(colors)], width=1.5)))

        st.dataframe(summary, use_container_width=True, hide_index=True)

        wrs  = [r['win_rate'] for r in valid.values()]
        trs  = [r['total_r']  for r in valid.values()]
        dds  = [r['max_dd_r'] for r in valid.values()]
        swrs = [r['super_wr'] for r in valid.values() if r['super_wr'] is not None]
        cwrs = [r['comum_wr'] for r in valid.values() if r['comum_wr'] is not None]

        ma,mb,mc,md,me = st.columns(5)
        ma.metric("WR médio",       f"{np.mean(wrs):.1f}%")
        mb.metric("Total R médio",  f"{np.mean(trs):+.2f}R")
        mc.metric("Max DD médio",   f"-{np.mean(dds):.1f}R")
        md.metric("SUPER WR médio", f"{np.mean(swrs):.1f}%" if swrs else "—")
        me.metric("COMUM WR médio", f"{np.mean(cwrs):.1f}%" if cwrs else "—")

        eqfig.add_hline(y=0, line_dash="dot", line_color="#484f58")
        eqfig.update_layout(title="Curva de Capital (R)", height=350,
                             paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                             font=dict(color='#8b949e',size=11),
                             legend=dict(bgcolor='rgba(0,0,0,0)', orientation='h'),
                             margin=dict(l=0,r=0,t=32,b=0))
        eqfig.update_xaxes(gridcolor='#21262d')
        eqfig.update_yaxes(gridcolor='#21262d')
        st.plotly_chart(eqfig, use_container_width=True)

        all_t = [{"symbol":s,**t} for s,r in valid.items() for t in r['trades']]
        st.download_button("📥 Exportar todos CSV",
                           pd.DataFrame(all_t).to_csv(index=False),
                           "montrezor_backtest_completo.csv",
                           "text/csv", key="bt_dl_all")
