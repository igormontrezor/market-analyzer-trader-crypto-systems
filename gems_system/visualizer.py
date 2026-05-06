#!/usr/bin/env python3
"""
📊 Visualizador interativo com Plotly + Pandas - Versão Corrigida
Correção principal: bloco global (evolução histórica) agora aparece
em QUALQUER fluxo — snapshot único ou comparação múltipla.
"""

import os
import io
import sys
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime, timedelta, timezone
import webbrowser
import tempfile
import numpy as np
from tvDatafeed import TvDatafeed, Interval
from typing import Optional, Dict, Any
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError
from evolution_functions import (
    get_all_snapshots_for_evolution,
    analyze_historical_evolution,
    determine_evolution_status,
    create_evolution_timeline,
    create_hall_of_fame,
    get_evolution_color,
    get_evolution_emoji
)

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def _coingecko_get(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Any:
    key = os.environ.get('COINGECKO_API_KEY')

    def _pro_url(u: str) -> str:
        try:
            if u.startswith('https://api.coingecko.com/'):
                return u.replace('https://api.coingecko.com/', 'https://pro-api.coingecko.com/', 1)
            if u.startswith('http://api.coingecko.com/'):
                return u.replace('http://api.coingecko.com/', 'https://pro-api.coingecko.com/', 1)
        except Exception:
            return u
        return u

    def _do_request(extra_params: Dict[str, Any], extra_headers: Dict[str, str]) -> Any:
        p = dict(params or {})
        p.update(extra_params)
        q = urlencode(p)
        full = f"{url}?{q}" if q else url

        headers = {
            "User-Agent": "gems_system_visualizer/1.0",
            "Accept": "application/json",
        }
        headers.update(extra_headers)
        req = Request(full, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            return json.loads(raw)
        except HTTPError as e:
            try:
                body = e.read().decode('utf-8', errors='replace')
            except Exception:
                body = ''

            msg = str(getattr(e, 'msg', '') or '')
            if body:
                body_one_line = ' '.join(body.split())
                if len(body_one_line) > 800:
                    body_one_line = body_one_line[:800] + '...'
                msg = (msg + ' | ' if msg else '') + body_one_line

            raise HTTPError(getattr(e, 'url', full), e.code, msg, e.hdrs, e.fp)

    if not key:
        return _do_request({}, {})

    try:
        return _do_request(
            {"x_cg_demo_api_key": key, "x_cg_pro_api_key": key, "x_cg_api_key": key},
            {"x-cg-demo-api-key": key, "x-cg-pro-api-key": key, "x-cg-api-key": key}
        )
    except HTTPError as e:
        if getattr(e, 'code', None) != 401:
            raise

        try:
            return _do_request(
                {"x_cg_pro_api_key": key},
                {"x-cg-pro-api-key": key}
            )
        except HTTPError as e2:
            if getattr(e2, 'code', None) != 401:
                raise

            pro = _pro_url(url)
            if pro != url:
                try:
                    return _coingecko_get(pro, params=params, timeout=timeout)
                except Exception:
                    pass

            raise RuntimeError(
                "CoinGecko 401 Unauthorized. A API key informada parece inválida ou "
                "precisa ser usada na base URL PRO (pro-api.coingecko.com)."
            )

def _build_macro_timing(days: int = 730, bb_period: int = 20, bb_std: float = 2.0) -> dict:
    base_dir = os.path.dirname(__file__)
    macro_dir = os.path.join(base_dir, 'data', 'macro')
    os.makedirs(macro_dir, exist_ok=True)
    macro_path = os.path.join(macro_dir, 'macro_timing.json')
    now = datetime.now()

    try:
        tv = TvDatafeed()
        usdt_weekly = tv.get_hist(symbol='USDT.D', exchange='CRYPTOCAP', interval=Interval.in_weekly, n_bars=200)
        usdt_monthly = tv.get_hist(symbol='USDT.D', exchange='CRYPTOCAP', interval=Interval.in_monthly, n_bars=100)
        others_weekly = tv.get_hist(symbol='OTHERS', exchange='CRYPTOCAP', interval=Interval.in_weekly, n_bars=200)
    except Exception as e:
        raise RuntimeError(f"Erro TV: {e}")

    def _bb_percent(series: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.Series:
        ma = series.rolling(period).mean()
        sd = series.rolling(period).std(ddof=0)
        return (series - (ma - std_mult * sd)) / ((ma + std_mult * sd) - (ma - std_mult * sd))

    w_usdt_bbp = _bb_percent(usdt_weekly['close'], bb_period, bb_std).dropna()
    m_usdt_bbp = _bb_percent(usdt_monthly['close'], 20, bb_std).dropna()
    w_others_bbp = _bb_percent(others_weekly['close'], bb_period, bb_std).dropna()

    curr_m_usdt = m_usdt_bbp.iloc[-1]
    prev_m_usdt = m_usdt_bbp.iloc[-2]
    curr_w_usdt = w_usdt_bbp.iloc[-1]
    curr_w_others = w_others_bbp.iloc[-1]

    plot_usdt_debug_html(usdt_weekly['close'], w_usdt_bbp)

    # --- REGIME MENSAL ---
    buy_mode = (prev_m_usdt >= 1.0 and curr_m_usdt < 1.0) or (curr_m_usdt < 1.0 and curr_m_usdt > 0.2)
    sell_mode = (prev_m_usdt <= 0.0 and curr_m_usdt > 0.0) or (curr_m_usdt > 0.0 and curr_m_usdt < 0.8 and not buy_mode)

    capitulation_lock = bool(sell_mode and curr_m_usdt >= 0.8)

    weekly_state = {
        "date": w_usdt_bbp.index[-1].strftime('%Y-%m-%d'),
        "others_bbp": float(curr_w_others),
        "usdt_d_bbp": float(curr_w_usdt),
        "others_touch_low": bool(curr_w_others <= 0),
        "usdt_touch_high": bool(curr_w_usdt >= 1),
        "usdt_touch_low": bool(curr_w_usdt <= 0),
    }

    signal = {
        "weekly_buy_trigger": bool(buy_mode and (weekly_state["others_touch_low"] or weekly_state["usdt_touch_high"])),
        "tactical_rebound": bool(sell_mode and weekly_state["usdt_touch_high"] and not capitulation_lock),
        "weekly_sell_trigger": bool(sell_mode and (weekly_state["usdt_touch_low"] or curr_w_others >= 1)),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly": weekly_state,
        "monthly": {"usdt_d_bbp": float(curr_m_usdt)},
        "regime": {
            "buy_mode": bool(buy_mode),
            "sell_mode": bool(sell_mode),
            "capitulation_lock": capitulation_lock
        },
        "signal": signal,
    }

    # (No final da função _build_macro_timing, pouco ANTES da definição do dicionário 'payload')

    # --- LÓGICA E REGISTRO DO FUNDING RATE ---
    import requests
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT", timeout=2)
        if r.status_code == 200:
            funding_rate = float(r.json().get('lastFundingRate', 0)) * 100
        else:
            funding_rate = 0.02
    except:
        funding_rate = 0.02

    # Registrar no CSV de Histórico (Formato unificado com app.py)
    funding_csv_path = os.path.join(macro_dir, 'funding_rate_history.csv')

    now_dt = datetime.now()
    timestamp_hour = now_dt.strftime("%Y-%m-%d %H:00:00") # Arredonda para a hora cheia

    already_logged = False
    if os.path.exists(funding_csv_path):
        try:
            with open(funding_csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines and timestamp_hour in lines[-1]:
                    already_logged = True
        except:
            pass

    if not already_logged:
        file_exists = os.path.exists(funding_csv_path)
        with open(funding_csv_path, 'a', encoding='utf-8') as f:
            if not file_exists:
                f.write("timestamp,funding_rate\n")
            f.write(f"{timestamp_hour},{funding_rate:.6f}\n")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly": weekly_state,
        "monthly": {"usdt_d_bbp": float(curr_m_usdt)},
        "regime": {
            "buy_mode": bool(buy_mode),
            "sell_mode": bool(sell_mode),
            "capitulation_lock": capitulation_lock
        },
        "signal": signal,
        "funding_rate": funding_rate
    }

    with open(macro_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload

def _load_macro_timing() -> dict:
    """Load macro timing from cache or build fresh if expired."""
    try:
        base_dir = os.path.dirname(__file__)
        macro_path = os.path.join(base_dir, 'data', 'macro', 'macro_timing.json')

        if not os.path.exists(macro_path):
            print("🔄 No macro timing cache found, building fresh data...")
            return _build_macro_timing()

        with open(macro_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # --- Trecho a ser substituído dentro de _load_macro_timing ---
        generated_at = data.get('generated_at')
        if generated_at:
            # 1. Converte o texto para data (mantendo o fuso horário UTC)
            # O .replace('Z', '+00:00') ajuda o Python a ler o formato ISO
            cache_time = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)

            # 2. Calcula a idade em segundos (Sem remover o tzinfo, a conta é exata)
            age_seconds = (now - cache_time).total_seconds()

            if age_seconds > 3600:  # 1 hora
                print(f"🔄 Macro timing cache expired ({age_seconds/60:.1f} min old), refreshing...")
                return _build_macro_timing()
            else:
                print(f"✅ Using fresh macro timing cache ({age_seconds/60:.1f} min old)")
                return data
        return _build_macro_timing()
    except Exception as e:
        print(f"⚠️ Error loading macro timing cache: {e}")
        return _build_macro_timing()

def _macro_timing_panel_html() -> str:
    payload = _load_macro_timing()
    if not payload: return ""

    regime = payload['regime']
    signal = payload['signal']
    w = payload['weekly']
    m = payload['monthly']

    # Prevenção para valores nulos
    m_val = m.get('usdt_d_bbp', 0.0)
    funding_rate = payload.get('funding_rate', 0.02) # Utiliza o que foi cacheado

    # Lógica Visual Macro Original
    if regime['capitulation_lock']:
        r_label, r_border = "🚨 CAPITULAÇÃO ATIVA", "rgba(255, 69, 0, 1)"
        a_label, a_border = "🚫 COMPRAS EM PAUSA", "rgba(255, 69, 0, 0.6)"
    elif regime['buy_mode']:
        r_label, r_border = "🟩 REGIME: COMPRA (Bear Market)", "rgba(46, 204, 113, 0.6)"
        a_label = "✅ COMPRA ATIVA" if signal['weekly_buy_trigger'] else "— AGUARDANDO PONTO"
        a_border = "rgba(46, 204, 113, 0.5)" if signal['weekly_buy_trigger'] else "rgba(255, 255, 255, 0.2)"
    elif regime['sell_mode']:
        r_label, r_border = "🟥 REGIME: VENDA (Bull Market)", "rgba(231, 76, 60, 0.6)"
        a_label = "🟥 ALERTA DE SAÍDA"
        a_border = "rgba(231, 76, 60, 0.5)"
    else:
        r_label, r_border = "⬜ NEUTRO", "rgba(255, 255, 255, 0.3)"
        a_label, a_border = "—", "rgba(255, 255, 255, 0.2)"

    if signal.get('tactical_rebound') and not regime['capitulation_lock']:
        a_label, a_border = "🔵 REPIQUE TÁTICO", "rgba(52, 152, 219, 0.8)"

    # --- LÓGICA DO FUNDING RATE ALINHADA AO APP.PY ---
    mensal_compra = regime['buy_mode']
    semanal_compra = signal.get('weekly_buy_trigger', False)
    mensal_venda = regime['sell_mode']
    semanal_venda = signal.get('weekly_sell_trigger', False)

    funding_label = "⚪ NEUTRO"
    super_alert_label = "—"
    super_alert_color = "rgba(255, 255, 255, 0.2)"
    alert_animation = ""

    # Condições Exatas da Estratégia
    if mensal_compra:
        if funding_rate < 0:
            funding_label = "🟢 COMPRA (Funding < 0)"
            if semanal_compra:
                super_alert_label = "⚡ SUPER ALERTA DE COMPRA"
                super_alert_color = "#00e676" # Verde limão brilhante
                alert_animation = "animation: blink 1.5s infinite;"
    elif mensal_venda:
        if funding_rate > 0.08:
            funding_label = "🔴 VENDA (Funding > 0.08)"
            if semanal_venda:
                super_alert_label = "🚨 SUPER ALERTA DE VENDA"
                super_alert_color = "#ff1744" # Vermelho brilhante
                alert_animation = "animation: blink 1.5s infinite;"

    # Cor dinâmica do texto da porcentagem do Funding
    f_rate_color = "#e74c3c" if funding_rate > 0.08 else "#2ecc71" if funding_rate < 0 else "#f1c40f"

    # Injeção de CSS para o piscar do super alerta dentro do HTML do Plotly
    blink_css = """
    <style>
        @keyframes blink {
            0% { opacity: 1; text-shadow: 0 0 10px currentColor; }
            50% { opacity: 0.3; }
            100% { opacity: 1; text-shadow: 0 0 10px currentColor; }
        }
    </style>
    """

    return f"""
    {blink_css}
    <div style="margin-top: 14px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; color: white;">
        <div style="padding: 12px; border: 2px solid {r_border}; border-radius: 10px; background: rgba(0,0,0,0.3);">
            <div style="font-size: 11px; opacity: 0.7;">STATUS MACRO</div>
            <div style="font-weight: 900; font-size: 13px;">{r_label}</div>
            <div style="font-size: 11px; margin-top: 4px; opacity: 0.8;">USDT.D Mensal BB%B: {m_val:.4f}</div>
            <div style="font-size: 10px; margin-top: 5px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 4px;">
                Funding Rate BTC: <b style="color: {f_rate_color}">{funding_rate:.4f}%</b> | {funding_label}
            </div>
        </div>
        <div style="padding: 12px; border: 1px solid {a_border}; border-radius: 10px; background: rgba(0,0,0,0.2);">
            <div style="font-size: 11px; opacity: 0.7;">AÇÃO SUGERIDA</div>
            <div style="font-weight: 800; font-size: 13px;">{a_label}</div>
            <div style="font-size: 11px; margin-top: 4px; opacity: 0.8;">
                Semanal -> OTHERS: <b>{w['others_bbp']:.2f}</b> | USDT.D: <b>{w['usdt_d_bbp']:.2f}</b>
            </div>
            <div style="font-size: 11px; margin-top: 5px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 5px; font-weight: 800; color: {super_alert_color}; {alert_animation}">
                {super_alert_label}
            </div>
        </div>
    </div>
    """

def plot_usdt_debug_html(usdt_monthly, m_usdt_bbp):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import tempfile
    import webbrowser

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3]
    )

    # USDT.D
    fig.add_trace(
        go.Scatter(
            x=usdt_monthly.index,
            y=usdt_monthly,
            name="USDT.D",
            mode="lines"
        ),
        row=1, col=1
    )

    # BB%B
    fig.add_trace(
        go.Scatter(
            x=m_usdt_bbp.index,
            y=m_usdt_bbp,
            name="BB%B",
            mode="lines"
        ),
        row=2, col=1
    )

    # Linhas referência
    fig.add_hline(y=1, line_dash="dash", row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", row=2, col=1)
    fig.add_hline(y=0.5, line_dash="dot", row=2, col=1)

    fig.update_layout(
        height=700,
        title="USDT.D vs BB%B (Weekly)",
        template="plotly_dark"
    )

    # 🔥 salvar HTML e abrir
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    fig.write_html(temp_file.name, config={'displayModeBar': False})

    webbrowser.open(f"file://{temp_file.name}")


# ===========================================================================
# ✅ NOVO: Função central que monta o bloco global de evolução histórica.
# Antes ficava enterrada dentro de create_top10_comparison_chart() e só
# era atingida pelo fluxo de comparação múltipla. Agora é independente e
# pode ser chamada de qualquer lugar.
# ===========================================================================

def build_global_evolution_block(reference_dfs, snapshot_info):
    """
    Monta o bloco completo de análise histórica global.

    Parâmetros
    ----------
    reference_dfs   : lista de DataFrames dos snapshots selecionados pelo usuário
                      (usado apenas como âncora para score_change recente).
    snapshot_info   : lista de dicts com metadados dos snapshots selecionados.

    Retorna
    -------
    js_block  : string com o JavaScript Plotly para os gráficos globais.
    summary   : string HTML com tabela de resumo / tendências.
    hall      : string HTML com Hall da Fama.
    """

    # 1. Carregar TODOS os snapshots do disco
    all_snapshots_data = get_all_snapshots_for_evolution()
    global_dfs = [s['df'] for s in all_snapshots_data if isinstance(s, dict) and 'df' in s]

    if not global_dfs:
        empty = "<p style='color:#666;'>⚠️ Nenhum snapshot histórico encontrado em data/snapshots.</p>"
        return "", empty, empty

    # 2. Análise histórica completa
    historical_data = analyze_historical_evolution(all_snapshots_data, reference_dfs)

    # 3. Montar ranking global (baseado em TODOS os snapshots do disco)
    global_crypto_data = {}
    for i, df in enumerate(global_dfs):
        if 'final_score' in df.columns:
            sorted_df = df.sort_values('final_score', ascending=False)
            score_col = 'final_score'
        elif 'ratio' in df.columns:
            sorted_df = df.sort_values('ratio', ascending=False)
            score_col = 'ratio'
        else:
            sorted_df = df.sort_values('market_cap', ascending=False)
            score_col = 'market_cap'

        for _, row in sorted_df.head(20).iterrows():
            symbol = row.get('symbol')
            if not symbol:
                continue

            score   = float(row[score_col])                      if pd.notna(row.get(score_col))                         else 0
            mc      = float(row['market_cap'])                   if pd.notna(row.get('market_cap'))                      else 0
            volume  = float(row['total_volume'])                 if pd.notna(row.get('total_volume'))                    else 0
            change  = float(row['price_change_percentage_24h'])  if pd.notna(row.get('price_change_percentage_24h'))     else 0
            # ✅ CORREÇÃO RS: coletar rs_24h e rs_7d (necessário para Bubble Chart)
            rs_24h  = float(row['rs_24h']) if pd.notna(row.get('rs_24h')) else None
            rs_7d   = float(row['rs_7d'])  if pd.notna(row.get('rs_7d'))  else None
            sector  = row.get('sector', 'Unknown')
            category= row.get('category', row.get('timeframe_classification', 'Unknown'))

            if symbol not in global_crypto_data:
                global_crypto_data[symbol] = {
                    'scores': [], 'mcs': [], 'volumes': [], 'changes_24h': [],
                    'rs_24h': [], 'rs_7d': [],
                    'periods_present': [], 'total_periods': len(global_dfs),
                    'sector': sector, 'category': category
                }

            global_crypto_data[symbol]['scores'].append(score)
            global_crypto_data[symbol]['mcs'].append(mc)
            global_crypto_data[symbol]['volumes'].append(volume)
            global_crypto_data[symbol]['changes_24h'].append(change)
            if rs_24h is not None:
                global_crypto_data[symbol]['rs_24h'].append(rs_24h)
            if rs_7d is not None:
                global_crypto_data[symbol]['rs_7d'].append(rs_7d)
            global_crypto_data[symbol]['periods_present'].append(i)

    global_crypto_ranking = []
    for symbol, data in global_crypto_data.items():
        avg_score       = sum(data['scores']) / len(data['scores'])
        consistency     = len(data['periods_present']) / data['total_periods']
        avg_mc          = sum(data['mcs'])          / len(data['mcs'])
        avg_volume      = sum(data['volumes'])      / len(data['volumes'])
        avg_change      = sum(data['changes_24h'])  / len(data['changes_24h'])
        evolution_status= determine_evolution_status(symbol, historical_data, data['periods_present'])

        first_period = 0 in data['periods_present']
        last_period  = (len(global_dfs) - 1) in data['periods_present']

        if consistency == 1.0:
            presence_type = 'consistent'
        elif first_period and not last_period:
            presence_type = 'gone'
        elif not first_period and last_period:
            presence_type = 'new'
        else:
            presence_type = 'intermittent'

        if len(data['scores']) > 1:
            mean_s   = avg_score
            variance = sum((x - mean_s) ** 2 for x in data['scores']) / len(data['scores'])
            score_volatility = variance ** 0.5
        else:
            score_volatility = 0

        global_crypto_ranking.append({
            'symbol': symbol,
            'avg_score': avg_score,
            'consistency': consistency,
            'avg_mc': avg_mc,
            'avg_volume': avg_volume,
            'avg_change': avg_change,
            'score_volatility': score_volatility,
            'presence_type': presence_type,
            'evolution_status': evolution_status,
            'periods_present': data['periods_present'],
            'scores': data['scores'],
            'mcs': data['mcs'],
            'volumes': data['volumes'],
            'changes_24h': data['changes_24h'],
            'rs_24h': data.get('rs_24h', []),   # ✅ para Bubble Chart
            'rs_7d':  data.get('rs_7d',  []),   # ✅ para Bubble Chart
            'sector': data['sector'],
            'category': data['category']
        })

    global_crypto_ranking.sort(
        key=lambda x: (x['avg_score'], x['consistency'], x['avg_mc']),
        reverse=True
    )

    top15_global = global_crypto_ranking[:15]

    # 4. Injetar referências nos historical_data para hall_of_fame e tendências
    historical_data['crypto_ranking'] = global_crypto_ranking
    historical_data['global_dfs']     = global_dfs

    # 5. Calcular score_change para o último snapshot selecionado pelo usuário
    last_reference_df = reference_dfs[-1] if reference_dfs else None
    if last_reference_df is not None and len(global_dfs) >= 2:
        # ✅ CORREÇÃO 4: .get() não existe em DataFrame — usar verificação de colunas
        score_col_first = 'final_score' if 'final_score' in global_dfs[0].columns else 'ratio'
        score_col_last  = 'final_score' if 'final_score' in global_dfs[-1].columns else 'ratio'
        first_scores = dict(zip(global_dfs[0]['symbol'],  global_dfs[0][score_col_first]))
        last_scores  = dict(zip(global_dfs[-1]['symbol'], global_dfs[-1][score_col_last]))
        score_changes = []
        for _, row in last_reference_df.iterrows():
            sym = row['symbol']
            score_changes.append(last_scores.get(sym, 0) - first_scores.get(sym, 0))
        last_reference_df = last_reference_df.copy()
        last_reference_df['score_change'] = score_changes

    # 6. Gerar JS dos gráficos e HTML das seções
    # Usa global_dfs como base para os gráficos (histórico completo)
    js_block = create_all_comparison_charts(
        top15_global, snapshot_info, global_crypto_ranking, global_dfs, historical_data
    )

    summary  = create_advanced_summary_table(
        top15_global, global_crypto_ranking,
        len(global_dfs), historical_data, last_reference_df
    )

    hall     = create_hall_of_fame(historical_data, snapshot_info)

    return js_block, summary, hall


# ===========================================================================
# HTML base para o bloco global (divs + script).
# Usado tanto no dashboard de snapshot único quanto no de comparação.
# ===========================================================================

def _global_block_html(js_block, summary_html, hall_html):
    """Retorna o HTML completo do bloco global de evolução com tutoriais."""
    macro_panel = _macro_timing_panel_html()
    return f"""
    <div style="background: white; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.08);">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 12px 12px 0 0;">
            <h3 style="margin: 0; font-size: 1.4em;">📈 ANÁLISE HISTÓRICA GLOBAL</h3>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">Todos os snapshots • 6 gráficos • Tutoriais completos</p>
            {macro_panel}
        </div>

        <div style="padding: 20px;">

        <!-- Gráfico 1: Bubble Chart (MAIS IMPORTANTE) -->
        <div id="bubble-chart" style="margin-top: 30px;"></div>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #e74c3c;">
            <h4 style="margin-top: 0; color: #2c3e50;">🫧 <strong>Tutorial - Bubble Chart (O Mais Importante!)</strong></h4>
            <p style="margin-bottom: 10px;"><strong>O que mostra:</strong> Relação entre Market Cap, Ratio e Volume em 3D.</p>
            <p style="margin-bottom: 10px;"><strong>Eixos:</strong></p>
            <ul style="margin-left: 20px; margin-bottom: 10px;">
                <li><strong>X (horizontal):</strong> Market Cap - tamanho da moeda</li>
                <li><strong>Y (vertical):</strong> Ratio Volume/MC - interesse real</li>
                <li><strong>Tamanho da bolha:</strong> Volume total negociado</li>
                <li><strong>COR DA BOLHA:</strong> Força vs BTC (PROTEÇÃO CONTRA QUEDAS)</li>
            </ul>
            <p style="margin-bottom: 10px;"><strong>Cores - RS vs BTC:</strong></p>
            <ul style="margin-left: 20px; margin-bottom: 10px;">
                <li><strong>🟢 Verde forte:</strong> Muito forte vs BTC (+20% ou mais)</li>
                <li><strong>🟢 Verde:</strong> Forte vs BTC (+5% a +20%)</li>
                <li><strong>🟠 Laranja:</strong> Neutro vs BTC (±5%)</li>
                <li><strong>🟠 Laranja escuro:</strong> Fraco vs BTC (-5% a -20%)</li>
                <li><strong>🔴 Vermelho:</strong> Muito fraco vs BTC (-20% ou mais)</li>
            </ul>
            <p style="margin-bottom: 15px;"><strong>🎯 Como ler o Bubble Chart (Quadrantes de Oportunidade)</strong></p>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #1a7a3c;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#1a7a3c;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">💎 Superior Esquerdo (Fundo de Ouro):</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Características:</strong> MC Baixo + Ratio Alto + Verde.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>O que significa:</strong> O dinheiro institucional ou de grandes investidores está acumulando em segredo (Volume desproporcional ao tamanho). Maior assimetria de risco.
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #2ecc71;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#2ecc71;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">🛡️ Inferior Direito (Refúgio de Segurança):</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Características:</strong> MC Alto + Ratio Baixo + Verde.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>O que significa:</strong> Ativos mais consolidados que não caem em relação ao Bitcoin. Bom para proteger capital durante correções do mercado.
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #e74c3c;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#e74c3c;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">⚠️ Vermelhos / Laranjas Escuros (Zonas de Risco):</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Características:</strong> Força negativa vs BTC.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>O que significa:</strong> Desvalorização superior à do Bitcoin, risco de capitulação. Evitar a qualquer custo.
                </p>
            </div>

            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0 0 8px 0;">
                    <strong>🧠 Fórmula Final para Validação de um "Gem" (Gema)</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    Para validar a bolha antes de qualquer entrada, utilize o checklist:
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Estrutura:</strong> MC Baixo + Ratio em ascensão (sem picos isolados).<br>
                    <strong>Desempenho:</strong> Cor Verde (Forte ou Forte vs BTC).<br>
                    <strong>Persistência:</strong> A força deve se manter por pelo menos 7 a 14 dias.<br>
                    <strong>Volume:</strong> Tamanho da bolha crescendo gradualmente (indica entrada de capital institucional).
                </p>
            </div>
            <p style="margin-bottom: 0;"><strong>Exemplo prático:</strong> Bolhas que sobem gradualmente no eixo do ratio, aumentam de tamanho de forma consistente e mantêm posição ao longo do tempo indicam entrada sustentável de capital — candidatas reais a liderança.</p>
        </div>

        <!-- Gráfico 2: Acumulação Silenciosa (2º MAIS IMPORTANTE) -->
        <div id="accumulation-chart" style="margin-top: 30px;"></div>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #27ae60;">
            <h4 style="margin-top: 0; color: #2c3e50;">📊 <strong>Análise do Gráfico de Acumulação Silenciosa</strong></h4>
            <p style="margin-bottom: 10px;"><strong>Para tirar o máximo proveito dessa leitura, podemos categorizar os padrões que você observará no gráfico:</strong></p>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #27ae60;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#27ae60;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">1. A Escada da Acumulação (O Sinal Ideal)</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Como aparece:</strong> Valores subindo de forma gradual e constante (ex: $0.2 → 0.4 → 0.6 → 0.8).
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>O que significa:</strong> Grandes players ou fundos estão acumulando o ativo aos poucos no mercado de balcão (OTC) ou comprando na ponta compradora sem derreter o livro de ofertas. Esse é o momento em que a moeda acumula força silenciosamente.
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #e74c3c;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#e74c3c;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">2. O Pico Especulativo (A "Bomba e Despejo")</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Como aparece:</strong> Um salto de $0.2 direto para $1.5, seguido de uma queda brusca.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>O que significa:</strong> Aumento de volume gerado por varejo ou notícias, sem sustentação institucional. Não indica acumulação, mas sim especulação (muito risco de derretimento).
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #f39c12;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#f39c12;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">3. O Platô de Acumulação Consolidada</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Como aparece:</strong> O ratio estabiliza em um nível alto, sem perder volume.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>O que significa:</strong> O mercado absorveu a oferta, e a moeda está pronta para dar o próximo passo de valorização.
                </p>
            </div>

            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0 0 8px 0;">
                    <strong>🧠 Como combinar com o seu Sistema de Baixo Capital (Low Cap)</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Filtro Macro:</strong> Verifique o status da sua ferramenta (se o regime estiver em alta ou no momento em que o cadeado de capitulação não está bloqueando).
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Filtro Micro (Gráfico):</strong> Procure por ativos que apresentem a Escada de Acumulação.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Validação:</strong> Verifique se o Market Cap continua baixo e se o desempenho em relação ao Bitcoin permanece positivo.
                </p>
            </div>
        </div>

        <!-- Gráfico 3: Heatmap Setorial -->
        <div id="sector-heatmap" style="margin-top: 30px;"></div>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #16a085;">
            <h4 style="margin-top: 0; color: #2c3e50;">🏭 <strong>Análise do Heatmap Setorial</strong></h4>
            <p style="margin-bottom: 10px;"><strong>O mapa de calor ilustra a temperatura do capital dentro dos diferentes setores ao longo do tempo (representado pelos snapshots).</strong></p>
            <p style="margin-bottom: 10px;"><strong>Eixo X (Horizontal):</strong> Períodos / Snapshots cronológicos.</p>
            <p style="margin-bottom: 10px;"><strong>Eixo Y (Vertical):</strong> Setores do mercado.</p>
            <p style="margin-bottom: 15px;"><strong>Cor da Matriz:</strong> Temperatura de acordo com o ratio médio.</p>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #ffffff;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#ffffff;border:1px solid #ddd;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">⚪ Branco a Amarelo Claro (Frios / Baixo Interesse)</strong>
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Decisão Estratégica:</strong> Observação e Acumulação — O capital ainda não chegou, mas é a zona ideal para mapear projetos antes de dispararem.
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #f39c12;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#f39c12;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">🟡 Amarelo a Laranja (Aquecendo / Dinheiro Entrando)</strong>
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Decisão Estratégica:</strong> Momento de Entrada — O volume está subindo e mostrando que o setor está despertando o interesse do Smart Money.
                </p>
            </div>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #e74c3c;">
                <p style="margin: 0 0 8px 0;">
                    <span style="display:inline-block;width:14px;height:14px;background-color:#e74c3c;border-radius:50%;margin-right:10px;vertical-align:middle;"></span>
                    <strong style="vertical-align:middle;">🔴 Laranja a Vermelho Escuro (Quentes / Exaustão)</strong>
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Decisão Estratégica:</strong> Alerta de Lucro — Indica que o movimento já está maduro e pode estar próximo de uma zona de exaustão de curto prazo.
                </p>
            </div>

            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0 0 8px 0;">
                    <strong>🎯 Como Ler o Heatmap na Prática</strong>
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>Rotação de Capital:</strong> O dinheiro do mercado costuma girar entre os setores. Quando o setor mais "quente" atinge o pico de vermelho escuro (valores acima de 1.2), o capital geralmente migra para setores frios ou em aquecimento.
                </p>
                <p style="margin: 0 0 4px 0; font-size: 14px; color: #666;">
                    <strong>A "Janela de Ouro":</strong> As melhores oportunidades de entrada ocorrem nos setores que mudam do branco/amarelo claro para o amarelo/laranja.
                </p>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    <strong>Validação de Exaustão:</strong> Em setores superaquecidos (vermelho escuro), não é recomendado buscar novas compras (risco de topo); a prioridade é a realização de lucros ou a observação de novas entradas.
                </p>
            </div>
        </div>

        <!-- Gráfico 4: Heatmap de Persistência -->
        <div id="persistence-heatmap" style="margin-top: 30px;"></div>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #f39c12;">
            <h4 style="margin-top: 0; color: #2c3e50;">🔥 <strong>Tutorial - Heatmap de Persistência</strong></h4>
            <p style="margin-bottom: 10px;"><strong>O que mostra:</strong> Quais gems foram consistentes em cada snapshot.</p>
            <p style="margin-bottom: 10px;"><strong>Como interpretar:</strong></p>
            <ul style="margin-left: 20px; margin-bottom: 10px;">
                <li><strong>⚪ Branco:</strong> Gem ausente no snapshot</li>
                <li><strong>🟢 Verde claro:</strong> Gem aparecendo (ratio baixo, começando)</li>
                <li><strong>🟢 Verde escuro:</strong> Gem forte e consistente (ratio alto)</li>
                <li><strong>🟣 Gaps brancos:</strong> Gem que aparece e some (spike, não confiável)</li>
            </ul>
            <p style="margin-bottom: 0;"><strong>Exemplo prático:</strong> Uma linha verde horizontal contínua indica uma gem que nunca decepcionou - excelente para longo prazo!</p>
        </div>

        <!-- Gráfico 5: Evolução Temporal -->
        <div id="top10-comparison-chart" style="margin-top: 30px;"></div>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #3498db;">
            <h4 style="margin-top: 0; color: #2c3e50;">📊 <strong>Tutorial - Gráfico de Evolução Temporal</strong></h4>
            <p style="margin-bottom: 10px;"><strong>O que mostra:</strong> A evolução do Ratio Volume/MC das top 10 gems ao longo do tempo.</p>
            <p style="margin-bottom: 10px;"><strong>Como interpretar:</strong></p>
            <ul style="margin-left: 20px; margin-bottom: 10px;">
                <li><strong>Linhas subindo:</strong> Gems ganhando interesse e volume real</li>
                <li><strong>Linhas estáveis altas:</strong> Gems consolidadas com liquidez constante</li>
                <li><strong>Linhas caindo:</strong> Gems perdendo interesse/volume</li>
            </ul>
            <p style="margin-bottom: 0;"><strong>Exemplo prático:</strong> Se uma gem apresenta um pico de ratio (ex: 0.3 → 1.2), retorna e estabiliza em nível igual ou superior ao anterior, sem tendência de queda contínua, isso pode indicar retenção de interesse e possível acumulação — especialmente se combinado com força relativa contra o BTC.</p>
        </div>

        <!-- Gráfico 6: Consistência -->
        <div id="evolution-chart" style="margin-top: 30px;"></div>
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px; border-left: 4px solid #9b59b6;">
            <h4 style="margin-top: 0; color: #2c3e50;">📈 <strong>Tutorial - Gráfico de Consistência</strong></h4>
            <p style="margin-bottom: 10px;"><strong>O que mostra:</strong> Quantos dias cada gem manteve-se forte (ratio > 0.5).</p>
            <p style="margin-bottom: 10px;"><strong>Como interpretar:</strong></p>
            <ul style="margin-left: 20px; margin-bottom: 10px;">
                <li><strong>Barras altas:</strong> Gems persistentes (líderes de altseason)</li>
                <li><strong>Barras médias:</strong> Gems emergentes com potencial</li>
                <li><strong>Barras baixas:</strong> Gems com picos rápidos (spikes)</li>
            </ul>
            <p style="margin-bottom: 0;"><strong>Exemplo prático:</strong> Uma gem com 15+ dias de consistência é provavelmente uma líder real. Uma com 2-3 dias pode ser apenas um spike.</p>
        </div>

        <div id="ranking-summary"     style="margin-bottom: 20px;"></div>
        <div id="hall-of-fame"></div>
        </div>
    </div>

    <script>
        {js_block}
        document.getElementById('ranking-summary').innerHTML = `{summary_html.replace('`', chr(96))}`;
        document.getElementById('hall-of-fame').innerHTML    = `{hall_html.replace('`', chr(96))}`;
    </script>
    """


# ===========================================================================
# create_interactive_dashboard — CORRIGIDO
# Agora inclui o bloco global de evolução histórica.
# ===========================================================================

def create_interactive_dashboard(df, file_name):
    """Cria dashboard interativo com Plotly — inclui bloco global histórico."""

    if 'ratio' not in df.columns:
        df['ratio'] = df['total_volume'].fillna(0) / df['market_cap']

    # --- Gráficos do snapshot selecionado (comportamento original) ---
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '🏆 Top 15 Market Cap',       '📈 Top 15 Volume/MC Ratio',
            '🚀 Top 15 Variação 24h',     '🎯 Top 15 Final Score'
        ),
        specs=[[{"type": "bar"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "bar"}]]
    )

    top_mc = df.nlargest(15, 'market_cap')
    fig.add_trace(go.Bar(x=top_mc['symbol'], y=top_mc['market_cap'],
                         name='Market Cap', marker_color='#3498db'), row=1, col=1)

    top_ratio = df.nlargest(15, 'ratio')
    fig.add_trace(go.Bar(x=top_ratio['symbol'], y=top_ratio['ratio'],
                         name='Volume/MC Ratio', marker_color='#e74c3c'), row=1, col=2)

    top_change = df.nlargest(15, 'price_change_percentage_24h')
    bar_colors = ['#2ecc71' if x > 0 else '#e74c3c'
                  for x in top_change['price_change_percentage_24h']]
    fig.add_trace(go.Bar(x=top_change['symbol'], y=top_change['price_change_percentage_24h'],
                         name='Variação 24h', marker_color=bar_colors), row=2, col=1)

    score_col = 'final_score' if 'final_score' in df.columns else 'ratio'
    top_score = df.nlargest(15, score_col)
    fig.add_trace(go.Bar(x=top_score['symbol'], y=top_score[score_col],
                         name='Final Score', marker_color='#f39c12'), row=2, col=2)

    fig.update_layout(
        title=f'🚀 GEMS SYSTEM DASHBOARD - {file_name}',
        height=800, showlegend=False, template='plotly_white'
    )

    table_html = create_interactive_table(df)

    # --- ✅ Bloco global histórico ---
    snapshot_info = [{'file': file_name, 'date': datetime.now().strftime('%Y-%m-%d %H:%M'), 'index': 0, 'count': len(df)}]
    js_block, summary_html, hall_html = build_global_evolution_block([df], snapshot_info)
    global_html = _global_block_html(js_block, summary_html, hall_html)

    # --- HTML final com layout padronizado ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚀 GEMS SYSTEM - DASHBOARD PROFESSIONAL</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script src="https://kit.fontawesome.com/a076d05399.js" crossorigin="anonymous"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}

            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                transition: all 0.3s ease;
            }}

            body.dark-mode {{
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            }}

            .dashboard-container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }}

            .header {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                text-align: center;
            }}

            .header h1 {{
                font-size: 2.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }}

            .header .subtitle {{
                color: #666;
                font-size: 1.1rem;
                margin-bottom: 20px;
            }}

            .kpi-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}

            .kpi-card {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                transition: all 0.3s ease;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}

            .kpi-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
            }}

            .kpi-value {{
                font-size: 2rem;
                font-weight: 700;
                color: #2c3e50;
                margin-bottom: 5px;
            }}

            .kpi-label {{
                color: #7f8c8d;
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}

            .content-card {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }}

            .section-title {{
                font-size: 1.5rem;
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            .chart-container {{
                background: white;
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
                margin-bottom: 20px;
            }}

            .dark-mode-toggle {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(255, 255, 255, 0.9);
                border: none;
                border-radius: 50px;
                padding: 12px 20px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
                font-size: 1.2rem;
                transition: all 0.3s ease;
                z-index: 1000;
            }}

            .dark-mode-toggle:hover {{
                transform: scale(1.05);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
            }}

            @media (max-width: 768px) {{
                .dashboard-container {{
                    padding: 10px;
                }}
                .header h1 {{
                    font-size: 2rem;
                }}
                .kpi-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <button class="dark-mode-toggle" onclick="toggleDarkMode()">🌙</button>

        <div class="dashboard-container">
            <div class="header">
                <h1>🚀 GEMS SYSTEM DASHBOARD</h1>
                <div class="subtitle">
                    <strong>Arquivo:</strong> {file_name} |
                    <strong>Data:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
                    <strong>Gems:</strong> {len(df)}
                </div>
            </div>

            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-value">${df['market_cap'].mean():,.0f}</div>
                    <div class="kpi-label">Market Cap Médio</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">${df['total_volume'].sum():,.0f}</div>
                    <div class="kpi-label">Volume Total</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{(df['price_change_percentage_24h'] > 0).sum()}/{len(df)}</div>
                    <div class="kpi-label">Variações Positivas 24h</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{(df['price_change_percentage_24h'] > 0).mean()*100:.1f}%</div>
                    <div class="kpi-label">% Positivas 24h</div>
                </div>
            </div>

            <div class="content-card">
                <h2 class="section-title">📊 Análise do Snapshot</h2>
                <div class="chart-container">
                    <div id="dashboard"></div>
                </div>
            </div>

            <div class="content-card">
                <h2 class="section-title">📋 Tabela de Dados Interativa</h2>
                <div class="chart-container">
                    {table_html}
                </div>
            </div>

            <!-- ✅ Bloco global histórico (aparece sempre) -->
            {global_html}
        </div>

        <script>
            // Função de modo escuro
            function toggleDarkMode() {{
                document.body.classList.toggle('dark-mode');
                const isDark = document.body.classList.contains('dark-mode');
                localStorage.setItem('darkMode', isDark);
                document.querySelector('.dark-mode-toggle').textContent = isDark ? '☀️' : '🌙';
            }}

            // Restaurar preferência de modo escuro
            if (localStorage.getItem('darkMode') === 'true') {{
                document.body.classList.add('dark-mode');
                document.querySelector('.dark-mode-toggle').textContent = '☀️';
            }}

            // Renderizar gráficos
            {fig.to_html(div_id="dashboard", include_plotlyjs=False)}
        </script>
    </body>
    </html>
    """

    _open_in_browser(html_content)
    return df


# ===========================================================================
# create_advanced_dashboard — CORRIGIDO
# Agora usa build_global_evolution_block em vez de duplicar a lógica.
# ===========================================================================

def create_advanced_dashboard(dfs, snapshot_info):
    """Cria dashboard avançado com abas + bloco global histórico."""

    # ✅ Bloco global: usa build_global_evolution_block (lê TODOS os snapshots do disco)
    js_block, summary_html, hall_html = build_global_evolution_block(dfs, snapshot_info)
    global_html = _global_block_html(js_block, summary_html, hall_html)

    # Abas por período
    tabs_buttons = ""
    tabs_contents = ""
    for i, (df, info) in enumerate(zip(dfs, snapshot_info)):
        active = "active" if i == 0 else ""
        tabs_buttons  += f'<button class="tab {active}" onclick="showTab({i})">Período {i+1} - {info["date"]}</button>\n'
        tabs_contents += f'<div id="tab-{i}" class="tab-content {active}">{create_period_html(df, info, i)}</div>\n'

    # Calculate KPI metrics
    total_market_cap = sum(df['market_cap'].sum() for df in dfs)
    total_volume = sum(df['total_volume'].sum() for df in dfs)
    total_gems = sum(len(df) for df in dfs)
    avg_score = sum(df['final_score'].mean() for df in dfs) / len(dfs)
    positive_changes = sum((df['price_change_percentage_24h'] > 0).sum() for df in dfs)
    total_changes = sum(len(df) for df in dfs)
    positive_pct = (positive_changes / total_changes * 100) if total_changes > 0 else 0

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚀 GEMS SYSTEM - DASHBOARD PROFESSIONAL</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script src="https://kit.fontawesome.com/a076d05399.js" crossorigin="anonymous"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}

            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                transition: all 0.3s ease;
            }}

            body.dark-mode {{
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            }}

            .dashboard-container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }}

            .header {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                padding: 30px;
                border-radius: 20px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                margin-bottom: 30px;
                text-align: center;
                position: relative;
            }}

            .dark-mode .header {{
                background: rgba(30, 30, 46, 0.95);
                color: white;
            }}

            .theme-toggle {{
                position: absolute;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                border: none;
                color: white;
                padding: 10px 15px;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s ease;
            }}

            .theme-toggle:hover {{
                transform: scale(1.05);
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }}

            h1 {{
                font-size: 2.5em;
                font-weight: 700;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }}

            .dark-mode h1 {{
                background: linear-gradient(135deg, #64b5f6, #42a5f5);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .subtitle {{
                color: #666;
                font-size: 1.1em;
                margin-bottom: 20px;
            }}

            .dark-mode .subtitle {{
                color: #ccc;
            }}

            .kpi-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}

            .kpi-card {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                text-align: center;
                transition: all 0.3s ease;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}

            .dark-mode .kpi-card {{
                background: rgba(30, 30, 46, 0.95);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .kpi-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 8px 30px rgba(0,0,0,0.15);
            }}

            .kpi-icon {{
                font-size: 2em;
                margin-bottom: 10px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .dark-mode .kpi-icon {{
                background: linear-gradient(135deg, #64b5f6, #42a5f5);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .kpi-value {{
                font-size: 2em;
                font-weight: 700;
                color: #2c3e50;
                margin-bottom: 5px;
            }}

            .dark-mode .kpi-value {{
                color: #fff;
            }}

            .kpi-label {{
                color: #666;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}

            .dark-mode .kpi-label {{
                color: #ccc;
            }}

            .filters-section {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}

            .dark-mode .filters-section {{
                background: rgba(30, 30, 46, 0.95);
                color: white;
            }}

            .filters-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                align-items: end;
            }}

            .filter-group {{
                display: flex;
                flex-direction: column;
            }}

            .filter-group label {{
                font-weight: 600;
                margin-bottom: 5px;
                color: #2c3e50;
            }}

            .dark-mode .filter-group label {{
                color: #fff;
            }}

            .filter-group select, .filter-group input {{
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                transition: all 0.3s ease;
            }}

            .dark-mode .filter-group select,
            .dark-mode .filter-group input {{
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
                color: white;
            }}

            .filter-group select:focus,
            .filter-group input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}

            .filter-btn {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.3s ease;
            }}

            .filter-btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }}

            .content-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 30px;
            }}

            .main-content {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                padding: 30px;
                border-radius: 20px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            }}

            .dark-mode .main-content {{
                background: rgba(30, 30, 46, 0.95);
                color: white;
            }}

            .tabs {{
                display: flex;
                border-bottom: 3px solid #667eea;
                margin-bottom: 30px;
                flex-wrap: wrap;
                gap: 5px;
            }}

            .tab {{
                padding: 15px 25px;
                cursor: pointer;
                border: none;
                background: rgba(255, 255, 255, 0.5);
                border-radius: 10px 10px 0 0;
                font-weight: 600;
                transition: all 0.3s ease;
                color: #2c3e50;
            }}

            .dark-mode .tab {{
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }}

            .tab.active {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                transform: translateY(-2px);
            }}

            .tab:hover {{
                background: rgba(102, 126, 234, 0.1);
            }}

            .dark-mode .tab:hover {{
                background: rgba(255, 255, 255, 0.2);
            }}

            .tab-content {{
                display: none;
                animation: fadeIn 0.5s ease;
            }}

            .tab-content.active {{
                display: block;
            }}

            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}

            .chart-container {{
                background: white;
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}

            .dark-mode .chart-container {{
                background: rgba(30, 30, 46, 0.95);
            }}

            .insights-panel {{
                background: linear-gradient(135deg, #f8f9fa, #e9ecef);
                padding: 20px;
                border-radius: 15px;
                margin-top: 30px;
                border-left: 5px solid #667eea;
            }}

            .dark-mode .insights-panel {{
                background: linear-gradient(135deg, rgba(30, 30, 46, 0.8), rgba(20, 20, 36, 0.8));
            }}

            .insights-title {{
                font-size: 1.3em;
                font-weight: 700;
                color: #2c3e50;
                margin-bottom: 15px;
            }}

            .dark-mode .insights-title {{
                color: white;
            }}

            .insight-item {{
                display: flex;
                align-items: center;
                margin-bottom: 10px;
                padding: 10px;
                background: white;
                border-radius: 8px;
            }}

            .dark-mode .insight-item {{
                background: rgba(255, 255, 255, 0.1);
            }}

            .insight-icon {{
                margin-right: 10px;
                color: #667eea;
            }}

            @media (max-width: 768px) {{
                .dashboard-container {{ padding: 10px; }}
                .kpi-grid {{ grid-template-columns: 1fr; }}
                .filters-grid {{ grid-template-columns: 1fr; }}
                .tabs {{ flex-direction: column; }}
                .tab {{ border-radius: 8px; margin-bottom: 2px; }}
            }}
        </style>
    </head>
    <body>
        <div class="dashboard-container">
            <div class="header">
                <button class="theme-toggle" onclick="toggleTheme()">
                    <i class="fas fa-moon" id="theme-icon"></i>
                </button>
                <h1>🚀 GEMS SYSTEM</h1>
                <p class="subtitle">Dashboard Profissional de Análise de Criptoativos</p>
            </div>

            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-icon">💰</div>
                    <div class="kpi-value">${total_market_cap:,.0f}</div>
                    <div class="kpi-label">Market Cap Total</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon">📊</div>
                    <div class="kpi-value">${total_volume:,.0f}</div>
                    <div class="kpi-label">Volume Total 24h</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon">🔥</div>
                    <div class="kpi-value">{total_gems}</div>
                    <div class="kpi-label">Total de Gems</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon">⭐</div>
                    <div class="kpi-value">{avg_score:.3f}</div>
                    <div class="kpi-label">Score Médio</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon">📈</div>
                    <div class="kpi-value">{positive_pct:.1f}%</div>
                    <div class="kpi-label">Variações Positivas</div>
                </div>
            </div>

            <div class="filters-section">
                <div class="filters-grid">
                    <div class="filter-group">
                        <label>Filtrar por Score</label>
                        <select id="scoreFilter" onchange="applyFilters()">
                            <option value="">Todos os Scores</option>
                            <option value="high">Score ≥ 0.8</option>
                            <option value="medium">Score ≥ 0.5</option>
                            <option value="low">Score < 0.5</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Filtrar por Market Cap</label>
                        <select id="marketCapFilter" onchange="applyFilters()">
                            <option value="">Todos os Market Caps</option>
                            <option value="small"><$20M</option>
                            <option value="medium">$20M - $35M</option>
                            <option value="large">>$35M</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Filtrar por Variação 24h</label>
                        <select id="changeFilter" onchange="applyFilters()">
                            <option value="">Todas as Variações</option>
                            <option value="positive">Positivas (>0%)</option>
                            <option value="negative">Negativas (<0%)</option>
                            <option value="high">Alta (>10%)</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>&nbsp;</label>
                        <button class="filter-btn" onclick="resetFilters()">
                            <i class="fas fa-redo"></i> Resetar Filtros
                        </button>
                    </div>
                </div>
            </div>

            <div class="content-grid">
                <div class="main-content">
                    <div class="tabs">
                        {tabs_buttons}
                    </div>

                    <div class="tab-contents">
                        {tabs_contents}
                    </div>

                    <!-- ✅ Bloco global histórico (aparece sempre) -->
                    <div class="chart-container">
                        {global_html}
                    </div>

                    <div class="insights-panel">
                        <div class="insights-title">🎯 Smart Insights</div>
                        <div class="insight-item">
                            <div class="insight-icon">🔥</div>
                            <div><strong>Top Performers:</strong> {', '.join(df.nlargest(3, 'final_score')['symbol'].tolist())}</div>
                        </div>
                        <div class="insight-item">
                            <div class="insight-icon">📈</div>
                            <div><strong>Maior Variação 24h:</strong> {df.loc[df['price_change_percentage_24h'].idxmax(), 'symbol']} ({df['price_change_percentage_24h'].max():.1f}%)</div>
                        </div>
                        <div class="insight-item">
                            <div class="insight-icon">💎</div>
                            <div><strong>Gems com Score ≥ 0.8:</strong> {len(df[df['final_score'] >= 0.8])} de {len(df)} ({len(df[df['final_score'] >= 0.8])/len(df)*100:.1f}%)</div>
                        </div>
                        <div class="insight-item">
                            <div class="insight-icon">🎪</div>
                            <div><strong>Setores em Destaque:</strong> {', '.join(df['sector'].value_counts().head(3).index.tolist()) if 'sector' in df.columns else 'Dados setoriais não disponíveis'}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Theme Toggle
            function toggleTheme() {{
                const body = document.body;
                const icon = document.getElementById('theme-icon');

                if (body.classList.contains('dark-mode')) {{
                    body.classList.remove('dark-mode');
                    icon.className = 'fas fa-moon';
                    localStorage.setItem('theme', 'light');
                }} else {{
                    body.classList.add('dark-mode');
                    icon.className = 'fas fa-sun';
                    localStorage.setItem('theme', 'dark');
                }}
            }}

            // Load saved theme
            if (localStorage.getItem('theme') === 'dark') {{
                document.body.classList.add('dark-mode');
                document.getElementById('theme-icon').className = 'fas fa-sun';
            }}

            // Tab functionality
            function showTab(index) {{
                const tabs = document.querySelectorAll('.tab');
                const contents = document.querySelectorAll('.tab-content');

                tabs.forEach((tab, i) => {{
                    tab.classList.remove('active');
                    if (i === index) {{
                        tab.classList.add('active');
                    }}
                }});

                contents.forEach((content, i) => {{
                    content.classList.remove('active');
                    if (i === index) {{
                        content.classList.add('active');
                    }}
                }});
            }}

            // Filter functionality
            function applyFilters() {{
                const scoreFilter = document.getElementById('scoreFilter').value;
                const marketCapFilter = document.getElementById('marketCapFilter').value;
                const changeFilter = document.getElementById('changeFilter').value;

                // This would require implementing dynamic filtering logic
                console.log('Applying filters:', {{ scoreFilter, marketCapFilter, changeFilter }});
                alert('Funcionalidade de filtros em desenvolvimento. Dashboard atualizado com sucesso!');
            }}

            function resetFilters() {{
                document.getElementById('scoreFilter').value = '';
                document.getElementById('marketCapFilter').value = '';
                document.getElementById('changeFilter').value = '';
                console.log('Filters reset');
            }}

            // Initialize first tab
            showTab(0);

            // Add smooth scrolling
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                anchor.addEventListener('click', function (e) {{
                    e.preventDefault();
                    document.querySelector(this.getAttribute('href')).scrollIntoView({{
                        behavior: 'smooth'
                    }});
                }});
            }});

            // Export functionality
            function exportData(format) {{
                console.log('Exporting data in', format, 'format');
                alert('Exportação em desenvolvimento. Funcionalidade disponível em breve!');
            }}

            // Keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                if (e.ctrlKey || e.metaKey) {{
                    switch(e.key) {{
                        case 'd':
                            e.preventDefault();
                            toggleTheme();
                            break;
                        case 'r':
                            e.preventDefault();
                            resetFilters();
                            break;
                    }}
                }}
            }});

            // Auto-refresh simulation (every 5 minutes)
            setInterval(() => {{
                console.log('Auto-refresh check - implementar atualização automática');
            }}, 300000);
        </script>
    </body>
    </html>
    """

    _open_in_browser(html_content)


# ===========================================================================
# Utilitário: abrir no navegador e limpar arquivo temporário
# ===========================================================================

def _open_in_browser(html_content):
    import threading, time
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_file = f.name

    print("🌐 Abrindo visualização no navegador...")
    webbrowser.open(f'file://{temp_file}')

    def cleanup():
        time.sleep(5)
        try:
            os.unlink(temp_file)
        except:
            pass

    t = threading.Thread(target=cleanup, daemon=True)
    t.start()


# ===========================================================================
# Funções auxiliares
# ===========================================================================

def _fig_to_plotly_newplot_js(fig, div_id):
    fig_json    = fig.to_plotly_json()
    data_json   = json.dumps(fig_json.get('data',   []), ensure_ascii=False)
    layout_json = json.dumps(fig_json.get('layout', {}), ensure_ascii=False)
    return f"Plotly.newPlot('{div_id}', {data_json}, {layout_json}, {{responsive: true}});"


def create_all_comparison_charts(top10, snapshot_info, crypto_ranking, dfs, historical_data=None):
    """Gráficos comparativos: evolução temporal, consistência, bubble, persistência, acumulação e setor."""

    def get_top5_consistent_cryptos():
        crypto_appearances = {}
        for df_cur in dfs:
            if df_cur is None or df_cur.empty or 'final_score' not in df_cur.columns:
                continue
            df_sorted = df_cur.sort_values('final_score', ascending=False).reset_index(drop=True)
            for _, row in df_sorted.head(5).iterrows():
                sym = row.get('symbol')
                if sym:
                    crypto_appearances[sym] = crypto_appearances.get(sym, 0) + 1
        return sorted(crypto_appearances.items(), key=lambda x: x[1], reverse=True)[:5]

    top5_cryptos = get_top5_consistent_cryptos()

    # Gráfico 1: Evolução temporal
    fig1 = go.Figure()
    for symbol, appearances in top5_cryptos:
        scores_timeline  = []
        periods_timeline = []
        for i, df in enumerate(dfs):
            # ✅ CORREÇÃO 5: verificar coluna antes de usar
            score_col = 'final_score' if 'final_score' in df.columns else 'ratio'
            df_sorted = df.sort_values(score_col, ascending=False).reset_index(drop=True)
            df_sorted['_rank'] = df_sorted.index + 1
            row = df_sorted[df_sorted['symbol'] == symbol]
            if not row.empty and int(row.iloc[0]['_rank']) <= 5:
                scores_timeline.append(float(row.iloc[0][score_col]))
            else:
                scores_timeline.append(None)
            periods_timeline.append(f'P{i+1}')

        fig1.add_trace(go.Scatter(
            x=periods_timeline, y=scores_timeline,
            mode='lines+markers',
            name=f'{symbol} ({appearances}x)',
            line=dict(width=3), marker=dict(size=8),
            connectgaps=False
        ))

    fig1.update_layout(
        title='📈 EVOLUÇÃO TEMPORAL — TOP 5 MAIS CONSISTENTES (Histórico Completo)',
        xaxis_title='Períodos', yaxis_title='Score',
        height=500, template='plotly_white', hovermode='x unified'
    )

    # Gráfico 2: Consistência
    consistent_data = sorted(
        [item for item in crypto_ranking if item['consistency'] == 1.0],
        key=lambda x: x['avg_score'], reverse=True
    )
    bar_colors = ['#27ae60' if item['avg_score'] > 0.8 else '#95a5a6' for item in consistent_data]

    fig2 = go.Figure(data=[go.Bar(
        x=[item['symbol']    for item in consistent_data],
        y=[item['avg_score'] for item in consistent_data],
        marker_color=bar_colors,
        text=[f'{item["avg_score"]:.3f}' for item in consistent_data],
        textposition='auto',
        hovertext=[f'{item["symbol"]}<br>Score: {item["avg_score"]:.3f}' for item in consistent_data],
        hoverinfo='text'
    )])

    fig2.update_layout(
        title='💎 CRYPTOS 100% CONSISTENTES (Presentes em todos os períodos)',
        xaxis_title='Cryptomoedas', yaxis_title='Score Médio',
        height=400, template='plotly_white'
    )

    # Gráfico 3: Bubble Chart
    fig3 = create_bubble_chart(crypto_ranking)

    # Gráfico 4: Heatmap de Persistência
    fig4 = create_persistence_heatmap(crypto_ranking, dfs)

    # Gráfico 5: Acumulação Silenciosa
    fig5 = create_accumulation_chart(crypto_ranking, dfs)

    # Gráfico 6: Heatmap Setorial
    fig6 = create_sector_heatmap(crypto_ranking, dfs)

    return "\n".join([
        "// Gráfico 1: Evolução Temporal",
        _fig_to_plotly_newplot_js(fig1, "top10-comparison-chart"),
        "// Gráfico 2: Consistência",
        _fig_to_plotly_newplot_js(fig2, "evolution-chart"),
        "// Gráfico 3: Bubble Chart",
        _fig_to_plotly_newplot_js(fig3, "bubble-chart"),
        "// Gráfico 4: Heatmap de Persistência",
        _fig_to_plotly_newplot_js(fig4, "persistence-heatmap"),
        "// Gráfico 5: Acumulação Silenciosa",
        _fig_to_plotly_newplot_js(fig5, "accumulation-chart"),
        "// Gráfico 6: Heatmap Setorial",
        _fig_to_plotly_newplot_js(fig6, "sector-heatmap"),
    ])


def create_bubble_chart(crypto_ranking):
    """
    🫧 Bubble Chart — Ratio vs Market Cap vs RS vs BTC

    Eixo X  = Market Cap (escala log)
    Eixo Y  = Ratio Volume/MC
    Tamanho = Score médio
    Cor     = Força vs BTC (verde = forte, vermelho = fraca)
    """

    # ✅ CORREÇÃO 1+2+3: RS vs BTC como cor, categorização correta, sem debug print
    rs_btc_color_map = {
        'strong':    '#1a7a3c',   # verde escuro  — muito forte vs BTC (≥+20pp)
        'moderate':  '#2ecc71',   # verde         — forte vs BTC (+5 a +20pp)
        'neutral':   '#f39c12',   # laranja       — neutro (±5pp)
        'weak':      '#e67e22',   # laranja escuro — fraco (-5 a -20pp)
        'very_weak': '#e74c3c',   # vermelho       — muito fraco (≤-20pp)
        'unknown':   '#95a5a6',   # cinza          — sem dados RS
    }

    symbols, x_mc, y_ratio, sizes, colors, hover = [], [], [], [], [], []

    for item in crypto_ranking:
        avg_mc    = item.get('avg_mc',    0)
        avg_score = item.get('avg_score', 0)
        vols = item.get('volumes', [])
        mcs  = item.get('mcs',    [])
        if mcs and any(m > 0 for m in mcs):
            avg_ratio = sum(v / m for v, m in zip(vols, mcs) if m > 0) / sum(1 for m in mcs if m > 0)
        else:
            avg_ratio = 0

        if avg_mc <= 0 or avg_ratio <= 0:
            continue

        # RS vs BTC em pontos percentuais (gem_change - btc_change)
        rs_24h_array = item.get('rs_24h', [])
        rs_7d_array  = item.get('rs_7d',  [])
        if rs_24h_array and rs_24h_array[-1] != 1.0:
            rs_pp = rs_24h_array[-1]
        elif rs_7d_array and rs_7d_array[-1] != 1.0:
            rs_pp = rs_7d_array[-1]
        else:
            rs_pp = None

        # ✅ CORREÇÃO 1: bandas simétricas corretas, sem elif morto
        if rs_pp is None:
            rs_category = 'unknown'
        elif rs_pp >= 20.0:
            rs_category = 'strong'
        elif rs_pp >= 5.0:
            rs_category = 'moderate'
        elif rs_pp >= -5.0:
            rs_category = 'neutral'
        elif rs_pp >= -20.0:
            rs_category = 'weak'
        else:
            rs_category = 'very_weak'

        # ✅ CORREÇÃO 3: sem print de debug

        bubble_size = max(8, min(50, avg_score * 40))

        if avg_ratio >= 1.0:   zone = 'breakout'
        elif avg_ratio >= 0.5: zone = 'strong'
        elif avg_ratio >= 0.2: zone = 'early_accumulation'
        else:                  zone = 'unknown'

        symbols.append(item['symbol'])
        x_mc.append(avg_mc)
        y_ratio.append(avg_ratio)
        sizes.append(bubble_size)
        colors.append(rs_btc_color_map.get(rs_category, '#95a5a6'))
        # ✅ CORREÇÃO 2: mostrar % no hover
        rs_label = f'{rs_pp:+.2f}% vs BTC ({rs_category})' if rs_pp is not None else 'sem dados RS'
        hover.append(
            f"<b>{item['symbol']}</b><br>"
            f"MC médio: ${avg_mc:,.0f}<br>"
            f"Ratio médio: {avg_ratio:.2f} ({zone})<br>"
            f"Score médio: {avg_score:.3f}<br>"
            f"Consistência: {item['consistency']*100:.0f}%<br>"
            f"RS vs BTC: {rs_label}<br>"
            f"Presença: {len(item['periods_present'])} snapshots"
        )

    fig = go.Figure()

    for rs_label, rs_color in rs_btc_color_map.items():
        idx = [i for i, c in enumerate(colors) if c == rs_color]
        if not idx:
            continue
        fig.add_trace(go.Scatter(
            x=[x_mc[i]    for i in idx],
            y=[y_ratio[i] for i in idx],
            mode='markers+text',
            name=rs_label.replace('_', ' ').title(),
            text=[symbols[i] for i in idx],
            textposition='top center',
            textfont=dict(size=9),
            marker=dict(
                size=[sizes[i] for i in idx],
                color=rs_color,
                opacity=0.80,
                line=dict(width=1, color='white')
            ),
            hovertext=[hover[i] for i in idx],
            hoverinfo='text'
        ))

    if x_mc:
        x_range = [min(x_mc) * 0.8, max(x_mc) * 1.2]
        fig.add_shape(type='line', x0=x_range[0], x1=x_range[1], y0=1.0, y1=1.0,
                      line=dict(color='#e74c3c', width=1, dash='dash'))
        fig.add_annotation(x=x_range[1], y=1.0, text='Breakout ≥1.0',
                           showarrow=False, font=dict(color='#e74c3c', size=10), xanchor='right')
        fig.add_shape(type='line', x0=x_range[0], x1=x_range[1], y0=0.5, y1=0.5,
                      line=dict(color='#f39c12', width=1, dash='dot'))
        fig.add_annotation(x=x_range[1], y=0.5, text='Strong ≥0.5',
                           showarrow=False, font=dict(color='#f39c12', size=10), xanchor='right')

    fig.update_layout(
        title='🫧 BUBBLE CHART — Ratio vs Market Cap | Cor = RS vs BTC | Tamanho = Score',
        xaxis=dict(title='Market Cap (USD)', type='log', tickformat='$,.0f'),
        yaxis=dict(title='Ratio Volume/MC', rangemode='tozero'),
        height=600,
        template='plotly_white',
        hovermode='closest',
        legend=dict(title='RS vs BTC', orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    return fig


def create_persistence_heatmap(crypto_ranking, dfs):
    """
    📊 Heatmap de Persistência — Ratio por snapshot ao longo do tempo

    Linhas  = cryptos (ordenadas por score médio descendente, top 25)
    Colunas = snapshots em ordem cronológica (P1 → Pn)
    Cor     = ratio Volume/MC naquele snapshot (0 = ausente / branco)
    """

    top_items = sorted(crypto_ranking, key=lambda x: x['avg_score'], reverse=True)[:25]

    n_periods = len(dfs)
    period_labels = [f'P{i+1}' for i in range(n_periods)]
    symbol_labels = [item['symbol'] for item in top_items]

    matrix = []
    annotations = []

    for row_idx, item in enumerate(top_items):
        row_ratios = []
        vols_per_period = item.get('volumes', [])
        mcs_per_period  = item.get('mcs',     [])
        periods_present = item.get('periods_present', [])

        for col_idx in range(n_periods):
            if col_idx in periods_present:
                data_idx = periods_present.index(col_idx)
                v = vols_per_period[data_idx] if data_idx < len(vols_per_period) else 0
                m = mcs_per_period[data_idx]  if data_idx < len(mcs_per_period)  else 0
                ratio = v / m if m > 0 else 0
            else:
                ratio = 0

            row_ratios.append(ratio)

            if ratio > 0:
                annotations.append(dict(
                    x=col_idx, y=row_idx,
                    text=f'{ratio:.1f}',
                    font=dict(size=8, color='white' if ratio > 0.7 else 'black'),
                    showarrow=False
                ))

        matrix.append(row_ratios)

    colorscale = [
        [0.0,  'rgba(255,255,255,0)'],
        [0.01, '#f0f9e8'],
        [0.2,  '#bae4b3'],
        [0.5,  '#74c476'],
        [0.8,  '#31a354'],
        [1.0,  '#006d2c'],
    ]

    all_ratios = [r for row in matrix for r in row if r > 0]
    zmax = max(all_ratios) if all_ratios else 2.0
    zmax = min(zmax, 3.0)

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=period_labels,
        y=symbol_labels,
        colorscale=colorscale,
        zmin=0,
        zmax=zmax,
        colorbar=dict(
            title='Ratio V/MC',
            tickvals=[0, 0.5, 1.0, 1.5, 2.0],
            ticktext=['Ausente', '0.5', '1.0 🔥', '1.5', '2.0+']
        ),
        hoverongaps=False,
        hovertemplate='<b>%{y}</b><br>Período: %{x}<br>Ratio: %{z:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title='📊 HEATMAP DE PERSISTÊNCIA — Ratio Volume/MC por Snapshot (Top 25)',
        xaxis=dict(title='Snapshots (cronológico →)', side='top'),
        yaxis=dict(title='Cryptos (ordenado por Score ↓)', autorange='reversed'),
        height=max(400, 25 * len(top_items) + 100),
        template='plotly_white',
        annotations=annotations,
    )

    return fig


def create_accumulation_chart(crypto_ranking, dfs):
    """
    📈 Gráfico de Acumulação Silenciosa

    Barras horizontais ordenadas por accumulation_score.
    Verde = acumulando / Cinza = sem sinal.
    """

    items_with_score = []

    for item in crypto_ranking:
        symbol = item['symbol']

        acc_score  = 0.0
        acc_signal = 'none'
        acc_slope  = 0.0

        for df in dfs:
            if df is None or df.empty:
                continue
            row = df[df['symbol'] == symbol]
            if not row.empty:
                # ✅ CORREÇÃO 7: proteção contra None e NaN antes do float()
                def _safe_float(series_row, col, default):
                    val = series_row.get(col, default)
                    if val is None or (isinstance(val, float) and str(val) == 'nan'):
                        return default
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return default

                s = row.iloc[0]
                acc_score  = _safe_float(s, 'accumulation_score',  0.0)
                acc_signal = str(s.get('accumulation_signal', 'none') or 'none')
                acc_slope  = _safe_float(s, 'accumulation_slope',  0.0)
                break

        # Fallback: calcular slope da série de ratios do ranking global
        if acc_score == 0.0:
            vols = item.get('volumes', [])
            mcs  = item.get('mcs',    [])
            if len(vols) >= 3 and any(m > 0 for m in mcs):
                ratios = [v / m for v, m in zip(vols, mcs) if m > 0]
                n      = len(ratios)
                xs     = list(range(n))
                mean_x = sum(xs) / n
                mean_y = sum(ratios) / n
                num    = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ratios))
                den    = sum((x - mean_x) ** 2 for x in xs)
                slope  = num / den if den != 0 else 0.0
                acc_slope = slope
                if slope > 0.01:
                    acc_score  = min(slope / 0.05, 1.0) * 0.6
                    acc_signal = 'moderate' if acc_score >= 0.4 else 'weak'

        if acc_score > 0.05 or abs(acc_slope) > 0.005:
            items_with_score.append({
                'symbol':    symbol,
                'score':     acc_score,
                'signal':    acc_signal,
                'slope':     acc_slope,
                'avg_score': item.get('avg_score', 0)
            })

    if not items_with_score:
        fig = go.Figure()
        fig.add_annotation(
            text='Dados de acumulação ainda não disponíveis.<br>'
                 'Execute o gems_finder com o módulo accumulation_sector integrado.',
            xref='paper', yref='paper', x=0.5, y=0.5,
            showarrow=False, font=dict(size=14, color='#666')
        )
        fig.update_layout(title='📈 ACUMULAÇÃO SILENCIOSA', height=300, template='plotly_white')
        return fig

    items_with_score.sort(key=lambda x: x['score'], reverse=True)
    items_with_score = items_with_score[:20]

    symbols = [i['symbol'] for i in items_with_score]
    scores  = [i['score']  for i in items_with_score]
    slopes  = [i['slope']  for i in items_with_score]
    signals = [i['signal'] for i in items_with_score]

    signal_color_map = {
        'very_strong': '#006d2c',
        'strong':      '#31a354',
        'moderate':    '#74c476',
        'weak':        '#bae4b3',
        'none':        '#95a5a6',
    }
    bar_colors = [signal_color_map.get(s, '#95a5a6') for s in signals]

    hover = [
        f'<b>{i["symbol"]}</b><br>'
        f'Acc Score: {i["score"]:.3f}<br>'
        f'Slope ratio: {i["slope"]:+.4f}<br>'
        f'Sinal: {i["signal"]}<br>'
        f'Score médio geral: {i["avg_score"]:.3f}'
        for i in items_with_score
    ]

    fig = go.Figure(data=[go.Bar(
        x=scores,
        y=symbols,
        orientation='h',
        marker_color=bar_colors,
        text=[f'{s:+.4f}' for s in slopes],
        textposition='outside',
        hovertext=hover,
        hoverinfo='text'
    )])

    fig.add_vline(x=0.6, line_dash='dash', line_color='#31a354',
                  annotation_text='Confirmado ≥0.6', annotation_position='top')
    fig.add_vline(x=0.4, line_dash='dot',  line_color='#74c476',
                  annotation_text='Monitorar ≥0.4', annotation_position='top')

    fig.update_layout(
        title='📈 ACUMULAÇÃO SILENCIOSA — Score por Crypto (slope do ratio ao longo do tempo)',
        xaxis=dict(title='Accumulation Score (0–1)', range=[0, 1.05]),
        yaxis=dict(title='', autorange='reversed'),
        height=max(350, 30 * len(items_with_score) + 80),
        template='plotly_white',
        showlegend=False
    )

    return fig


def create_sector_heatmap(crypto_ranking, dfs):
    """
    🏭 Heatmap Setorial — Temperatura por setor ao longo dos snapshots
    """
    try:
        from accumulation_sector import get_sector, SectorCorrelationAnalyzer
    except ImportError:
        fig = go.Figure()
        fig.add_annotation(
            text='Módulo accumulation_sector.py não encontrado.<br>'
                 'Copie-o para a pasta do projeto.',
            xref='paper', yref='paper', x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color='#e74c3c')
        )
        fig.update_layout(title='🏭 ANÁLISE SETORIAL', height=300, template='plotly_white')
        return fig

    analyzer = SectorCorrelationAnalyzer()

    n_periods     = len(dfs)
    period_labels = [f'P{i+1}' for i in range(n_periods)]
    all_sectors   = set()
    snap_analyses = []

    for df in dfs:
        if df is None or df.empty:
            snap_analyses.append({})
            continue
        gems = df.to_dict(orient='records')
        for gem in gems:
            if 'sector' not in gem or not gem['sector']:
                gem['sector'] = get_sector(gem.get('symbol', '').lower())
        analysis = analyzer.analyze_snapshot(gems)
        snap_analyses.append(analysis.get('sectors', {}))
        all_sectors.update(analysis.get('sectors', {}).keys())

    if not all_sectors:
        fig = go.Figure()
        fig.add_annotation(
            text='Dados setoriais insuficientes.<br>Necessário pelo menos 1 snapshot com dados enriquecidos.',
            xref='paper', yref='paper', x=0.5, y=0.5,
            showarrow=False, font=dict(size=13, color='#666')
        )
        fig.update_layout(title='🏭 ANÁLISE SETORIAL', height=300, template='plotly_white')
        return fig

    sector_avg = {}
    for sector in all_sectors:
        vals = [s[sector]['avg_ratio'] for s in snap_analyses if sector in s]
        sector_avg[sector] = sum(vals) / len(vals) if vals else 0

    sorted_sectors = sorted(all_sectors, key=lambda s: sector_avg[s], reverse=True)

    matrix      = []
    annotations = []
    sector_labels = []

    for row_idx, sector in enumerate(sorted_sectors):
        row = []
        for col_idx, snap in enumerate(snap_analyses):
            if sector in snap:
                val = snap[sector]['avg_ratio']
            else:
                val = 0
            row.append(val)

            if val > 0:
                annotations.append(dict(
                    x=col_idx, y=row_idx,
                    text=f'{val:.2f}',
                    font=dict(size=8, color='white' if val > 0.5 else 'black'),
                    showarrow=False
                ))

        matrix.append(row)
        sector_labels.append(sector)

    colorscale = [
        [0.0,  '#f5f5f5'],
        [0.15, '#fee8c8'],
        [0.35, '#fdbb84'],
        [0.6,  '#e34a33'],
        [1.0,  '#7f0000'],
    ]

    all_vals = [v for row in matrix for v in row if v > 0]
    zmax     = min(max(all_vals) if all_vals else 1.5, 2.0)

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=period_labels,
        y=sector_labels,
        colorscale=colorscale,
        zmin=0,
        zmax=zmax,
        colorbar=dict(
            title='Ratio médio',
            tickvals=[0, 0.3, 0.5, 0.8, 1.2],
            ticktext=['Frio', '0.3', '0.5🔥', '0.8', '1.2🚨']
        ),
        hoverongaps=False,
        hovertemplate='<b>%{y}</b><br>Período: %{x}<br>Ratio médio: %{z:.3f}<extra></extra>'
    ))

    fig.update_layout(
        title='🏭 HEATMAP SETORIAL — Ratio médio por setor × snapshot (rotação de capital)',
        xaxis=dict(title='Snapshots (cronológico →)', side='top'),
        yaxis=dict(title='Setor (mais quente ↑)'),
        height=max(350, 40 * len(sorted_sectors) + 120),
        template='plotly_white',
        annotations=annotations
    )

    return fig


def create_advanced_summary_table(top10, crypto_ranking, total_periods, historical_data=None, last_df=None):
    """Tabela de resumo com tendências globais e recentes."""

    global_dfs = historical_data.get('global_dfs', []) if historical_data else []

    delta_global_dict = {}
    delta_recent_dict = {}

    if len(global_dfs) >= 2:
        df_first = global_dfs[0]
        df_last  = global_dfs[-1]

        score_col_first = 'final_score' if 'final_score' in df_first.columns else 'ratio'
        score_col_last  = 'final_score' if 'final_score' in df_last.columns  else 'ratio'

        first_scores = dict(zip(df_first['symbol'], df_first[score_col_first]))
        last_scores  = dict(zip(df_last['symbol'],  df_last[score_col_last]))

        for sym in set(first_scores) | set(last_scores):
            delta_global_dict[sym] = last_scores.get(sym, 0) - first_scores.get(sym, 0)

        RECENT_WINDOW = 5
        recent_index  = max(len(global_dfs) - RECENT_WINDOW, 1)
        df_recent_ref = global_dfs[recent_index]
        score_col_rec = 'final_score' if 'final_score' in df_recent_ref.columns else 'ratio'
        recent_ref_scores = dict(zip(df_recent_ref['symbol'], df_recent_ref[score_col_rec]))
        for sym in set(recent_ref_scores) | set(last_scores):
            delta_recent_dict[sym] = last_scores.get(sym, 0) - recent_ref_scores.get(sym, 0)

    for item in crypto_ranking:
        item['delta_global'] = delta_global_dict.get(item['symbol'], 0)
        item['delta_recent'] = delta_recent_dict.get(item['symbol'], 0)

    top_growers_global = sorted([c for c in crypto_ranking if c['delta_global'] > 0],
                                 key=lambda x: x['delta_global'], reverse=True)[:5]
    top_fallers_global = sorted([c for c in crypto_ranking if c['delta_global'] < 0],
                                 key=lambda x: x['delta_global'])[:5]
    top_growers_recent = sorted([c for c in crypto_ranking if c['delta_recent'] > 0],
                                 key=lambda x: x['delta_recent'], reverse=True)[:5]
    top_fallers_recent = sorted([c for c in crypto_ranking if c['delta_recent'] < 0],
                                 key=lambda x: x['delta_recent'])[:5]

    def render_trend_block(title, growers, fallers, delta_key):
        growers_html = ''.join([f'<tr><td>{i["symbol"]}</td><td>+{i[delta_key]:.3f}</td></tr>' for i in growers])
        fallers_html = ''.join([f'<tr><td>{i["symbol"]}</td><td>{i[delta_key]:.3f}</td></tr>'  for i in fallers])
        no_data = '<tr><td colspan="2" style="text-align:center;color:#666;">Nenhum dado</td></tr>'
        return f"""
        <div style="background:#f8f9fa;padding:15px;border-radius:5px;margin:20px 0;">
            <h4>{title}</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                <div>
                    <h5>🚀 Maiores Crescimentos</h5>
                    <table style="width:100%;border-collapse:collapse;">
                        <tr style="background:#27ae60;color:white;"><th style="padding:6px;">Crypto</th><th style="padding:6px;">Δ Score</th></tr>
                        {growers_html or no_data}
                    </table>
                </div>
                <div>
                    <h5>⚠️ Maiores Quedas</h5>
                    <table style="width:100%;border-collapse:collapse;">
                        <tr style="background:#e74c3c;color:white;"><th style="padding:6px;">Crypto</th><th style="padding:6px;">Δ Score</th></tr>
                        {fallers_html or no_data}
                    </table>
                </div>
            </div>
        </div>"""

    trends_html = render_trend_block(
        f'📈 TENDÊNCIAS GLOBAIS (desde o 1º snapshot — {len(global_dfs)} snapshots no histórico)',
        top_growers_global, top_fallers_global, 'delta_global'
    )

    if len(global_dfs) >= 3:
        RECENT_WINDOW  = 5
        recent_index   = max(len(global_dfs) - RECENT_WINDOW, 1)
        snapshots_back = len(global_dfs) - recent_index
        trends_html += render_trend_block(
            f'⚡ TENDÊNCIAS RECENTES (últimos {snapshots_back} snapshots)',
            top_growers_recent, top_fallers_recent, 'delta_recent'
        )
    else:
        # ✅ CORREÇÃO 6: era """ sem f — {len(global_dfs)} aparecia literal no HTML
        n_global = len(global_dfs)
        trends_html += f"""
        <div style="background:#f8f9fa;padding:15px;border-radius:5px;margin:20px 0;">
            <h4>⚡ TENDÊNCIAS RECENTES</h4>
            <p style="text-align:center;color:#666;padding:20px;">
                Necessário pelo menos 3 snapshots para calcular tendências recentes.<br>
                Histórico atual: {n_global} snapshot(s).
            </p>
        </div>"""

    total_unique     = len(crypto_ranking)
    consistent_count = len([i for i in crypto_ranking if i['consistency'] == 1.0])
    new_count        = len([i for i in crypto_ranking if i['presence_type'] == 'new'])
    gone_count       = len([i for i in crypto_ranking if i['presence_type'] == 'gone'])
    avg_score_geral  = sum(i['avg_score'] for i in crypto_ranking) / total_unique if total_unique else 0
    rotatividade     = (new_count + gone_count) / total_unique * 100 if total_unique else 0

    top5_performers = sorted(crypto_ranking, key=lambda x: x['avg_score'], reverse=True)[:5]

    return f"""
    <div class="stats">
        <div style="background:#f8f9fa;padding:15px;border-radius:5px;margin:20px 0;">
            <h4>RESUMO GERAL — Histórico completo ({len(global_dfs)} snapshots)</h4>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-bottom:15px;">
                <div style="text-align:center;background:white;padding:10px;border-radius:5px;">
                    <strong>{total_unique}</strong><br><small>Total Cryptos</small>
                </div>
                <div style="text-align:center;background:white;padding:10px;border-radius:5px;">
                    <strong>{rotatividade:.1f}%</strong><br><small>Rotatividade</small>
                </div>
                <div style="text-align:center;background:white;padding:10px;border-radius:5px;">
                    <strong>{avg_score_geral:.3f}</strong><br><small>Score Médio Geral</small>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;">
                <div style="text-align:center;background:white;padding:10px;border-radius:5px;">
                    <strong>{consistent_count}</strong><br><small>100% Consistentes</small>
                </div>
                <div style="text-align:center;background:white;padding:10px;border-radius:5px;">
                    <strong>{new_count}</strong><br><small>Novas</small>
                </div>
                <div style="text-align:center;background:white;padding:10px;border-radius:5px;">
                    <strong>{gone_count}</strong><br><small>Saíram</small>
                </div>
            </div>
        </div>

        <div style="background:#f8f9fa;padding:15px;border-radius:5px;margin:20px 0;">
            <h4>TOP PERFORMERS (Score médio histórico)</h4>
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#27ae60;color:white;">
                    <th style="padding:8px;text-align:left;">Crypto</th>
                    <th style="padding:8px;text-align:center;">Score Médio</th>
                    <th style="padding:8px;text-align:center;">Consistência</th>
                    <th style="padding:8px;text-align:center;">Performance</th>
                </tr>
                {''.join([f"""
                <tr>
                    <td style="padding:8px;"><strong>{i['symbol']}</strong></td>
                    <td style="padding:8px;text-align:center;">{i['avg_score']:.3f}</td>
                    <td style="padding:8px;text-align:center;">{i['consistency']*100:.0f}%</td>
                    <td style="padding:8px;text-align:center;">{"🔥" if i['avg_score'] > 0.8 else "⭐" if i['avg_score'] > 0.6 else "📊"}</td>
                </tr>""" for i in top5_performers])}
            </table>
        </div>

        {trends_html}
    </div>
    """


def create_interactive_table(df):
    """Tabela HTML estilizada igual à da comparação múltipla."""

    display_cols = ['symbol', 'name', 'market_cap', 'total_volume', 'price_change_percentage_24h']
    for col in ['ratio', 'final_score',
                'persistence_count_3d', 'persistence_count_7d', 'persistence_count_14d',
                'timeframe_classification', 'is_confirmed_leader',
                'zone', 'momentum', 'is_gold', 'rs_strong']:
        if col in df.columns:
            display_cols.append(col)

    table_df = df[[c for c in display_cols if c in df.columns]].copy()

    # Ordenar por score se disponível
    sort_col = 'final_score' if 'final_score' in table_df.columns else 'ratio' if 'ratio' in table_df.columns else None
    if sort_col:
        table_df = table_df.sort_values(sort_col, ascending=False)

    table_df['market_cap']                  = table_df['market_cap'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
    table_df['total_volume']                = table_df['total_volume'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
    table_df['price_change_percentage_24h'] = table_df['price_change_percentage_24h'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else 'N/A')
    if 'ratio'       in table_df.columns: table_df['ratio']       = table_df['ratio'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else 'N/A')
    if 'final_score' in table_df.columns: table_df['final_score'] = table_df['final_score'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else 'N/A')
    if 'is_confirmed_leader' in table_df.columns:
        table_df['is_confirmed_leader'] = table_df['is_confirmed_leader'].apply(lambda x: '👑 YES' if x else '❌ NO')

    column_mapping = {
        'symbol': 'Symbol', 'name': 'Name', 'market_cap': 'Market Cap', 'total_volume': 'Volume',
        'price_change_percentage_24h': '24h%', 'ratio': 'Ratio', 'final_score': 'Score',
        'persistence_count_3d': '3d', 'persistence_count_7d': '7d', 'persistence_count_14d': '14d',
        'timeframe_classification': 'Classification', 'is_confirmed_leader': 'Leader',
        'zone': 'Zone', 'momentum': 'Momentum', 'is_gold': 'Gold', 'rs_strong': 'RS'
    }
    table_df.rename(columns=column_mapping, inplace=True)

    # Create styled HTML table
    table_html = table_df.to_html(classes='table table-striped', index=False)

    # Add CSS styling igual à da comparação múltipla
    styled_html = f"""
    <style>
        .table {{
            width: 100%;
            border-collapse: collapse;
            font-family: Arial, sans-serif;
            font-size: 11px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            font-weight: bold;
            padding: 12px 6px;
            border: 1px solid #fff;
            font-size: 12px;
        }}
        .table td {{
            padding: 8px 6px;
            text-align: center;
            border: 1px solid #e0e0e0;
            font-weight: 500;
        }}
        .table-striped tbody tr:nth-of-type(odd) {{
            background-color: #f8f9fa;
        }}
        .table-striped tbody tr:nth-of-type(even) {{
            background-color: #ffffff;
        }}
        .table-striped tbody tr:hover {{
            background-color: #e3f2fd;
            transform: scale(1.01);
            transition: all 0.2s ease;
        }}
        /* Color for positive values */
        .table td:nth-child(5) {{
            color: #2e7d32;
            font-weight: bold;
        }}
        /* Color for negative values */
        .table td:nth-child(5):contains("-") {{
            color: #c62828;
        }}
        /* Highlight high scores */
        .table td:nth-child(7) {{
            background: linear-gradient(90deg,
                rgba(255,255,255,0) 0%,
                rgba(76,175,80,0.1) 50%,
                rgba(255,255,255,0) 100%);
        }}
        .table td:nth-child(7):contains("0.9"),
        .table td:nth-child(7):contains("1.0") {{
            background: linear-gradient(90deg,
                rgba(255,255,255,0) 0%,
                rgba(76,175,80,0.3) 50%,
                rgba(255,255,255,0) 100%);
            font-weight: bold;
            color: #2e7d32;
        }}
        /* Style boolean columns */
        .table td:nth-child(11),
        .table td:nth-child(14),
        .table td:nth-child(15) {{
            font-weight: bold;
        }}
        .table td:nth-child(11):contains("True") {{
            color: #2e7d32;
            background-color: #e8f5e8;
        }}
        .table td:nth-child(14):contains("True") {{
            color: #f57c00;
            background-color: #fff3e0;
        }}
        .table td:nth-child(15):contains("True") {{
            color: #1976d2;
            background-color: #e3f2fd;
        }}
    </style>
    {table_html}
    """

    # Retornar HTML puro para ser injetado diretamente no dashboard
    return styled_html


def create_period_html(df, snapshot_info, index):
    """HTML de um período específico (aba na comparação)."""

    display_cols = ['symbol', 'name', 'market_cap', 'total_volume', 'price_change_percentage_24h']
    for col in ['ratio', 'final_score',
                'persistence_count_3d', 'persistence_count_7d', 'persistence_count_14d',
                'timeframe_classification', 'is_confirmed_leader',
                'zone', 'momentum', 'is_gold', 'rs_strong']:
        if col in df.columns:
            display_cols.append(col)

    table_df = df[[c for c in display_cols if c in df.columns]].copy()

    sort_col = 'final_score' if 'final_score' in table_df.columns else 'ratio' if 'ratio' in table_df.columns else None
    if sort_col:
        table_df = table_df.sort_values(sort_col, ascending=False)

    table_df['market_cap']                  = table_df['market_cap'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
    table_df['total_volume']                = table_df['total_volume'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
    table_df['price_change_percentage_24h'] = table_df['price_change_percentage_24h'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else 'N/A')
    if 'ratio'       in table_df.columns: table_df['ratio']       = table_df['ratio'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else 'N/A')
    if 'final_score' in table_df.columns: table_df['final_score'] = table_df['final_score'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else 'N/A')
    if 'is_confirmed_leader' in table_df.columns:
        table_df['is_confirmed_leader'] = table_df['is_confirmed_leader'].apply(lambda x: '👑 YES' if x else '❌ NO')

    column_mapping = {
        'symbol': 'Symbol', 'name': 'Name', 'market_cap': 'Market Cap', 'total_volume': 'Volume',
        'price_change_percentage_24h': '24h%', 'ratio': 'Ratio', 'final_score': 'Score',
        'persistence_count_3d': '3d', 'persistence_count_7d': '7d', 'persistence_count_14d': '14d',
        'timeframe_classification': 'Classification', 'is_confirmed_leader': 'Leader',
        'zone': 'Zone', 'momentum': 'Momentum', 'is_gold': 'Gold', 'rs_strong': 'RS'
    }
    table_df.rename(columns=column_mapping, inplace=True)

    mc_mean = df['market_cap'].mean()
    vol_sum = df['total_volume'].sum()
    pos_pct = (df['price_change_percentage_24h'] > 0).mean() * 100
    pos_cnt = (df['price_change_percentage_24h'] > 0).sum()

    # Create styled HTML table
    table_html = table_df.to_html(classes='table table-striped', index=False)

    # Add CSS styling
    styled_html = f"""
    <style>
        .table {{
            width: 100%;
            border-collapse: collapse;
            font-family: Arial, sans-serif;
            font-size: 11px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            font-weight: bold;
            padding: 12px 6px;
            border: 1px solid #fff;
            font-size: 12px;
        }}
        .table td {{
            padding: 8px 6px;
            text-align: center;
            border: 1px solid #e0e0e0;
            font-weight: 500;
        }}
        .table-striped tbody tr:nth-of-type(odd) {{
            background-color: #f8f9fa;
        }}
        .table-striped tbody tr:nth-of-type(even) {{
            background-color: #ffffff;
        }}
        .table-striped tbody tr:hover {{
            background-color: #e3f2fd;
            transform: scale(1.01);
            transition: all 0.2s ease;
        }}
        /* Color for positive values */
        .table td:nth-child(5) {{
            color: #2e7d32;
            font-weight: bold;
        }}
        /* Color for negative values */
        .table td:nth-child(5):contains("-") {{
            color: #c62828;
        }}
        /* Highlight high scores */
        .table td:nth-child(7) {{
            background: linear-gradient(90deg,
                rgba(255,255,255,0) 0%,
                rgba(76,175,80,0.1) 50%,
                rgba(255,255,255,0) 100%);
        }}
        .table td:nth-child(7):contains("0.9"),
        .table td:nth-child(7):contains("1.0") {{
            background: linear-gradient(90deg,
                rgba(255,255,255,0) 0%,
                rgba(76,175,80,0.3) 50%,
                rgba(255,255,255,0) 100%);
            font-weight: bold;
            color: #2e7d32;
        }}
        /* Style boolean columns */
        .table td:nth-child(11),
        .table td:nth-child(14),
        .table td:nth-child(15) {{
            font-weight: bold;
        }}
        .table td:nth-child(11):contains("True") {{
            color: #2e7d32;
            background-color: #e8f5e8;
        }}
        .table td:nth-child(14):contains("True") {{
            color: #f57c00;
            background-color: #fff3e0;
        }}
        .table td:nth-child(15):contains("True") {{
            color: #1976d2;
            background-color: #e3f2fd;
        }}
    </style>
    {table_html}
    """

    return f"""
    <div class="stats">
        <h3>📊 Estatísticas — {snapshot_info['date']}</h3>
        <p><strong>Market Cap Médio:</strong> ${mc_mean:,.0f}</p>
        <p><strong>Volume Total:</strong> ${vol_sum:,.0f}</p>
        <p><strong>Variação 24h Positivas:</strong> {pos_cnt}/{len(df)} ({pos_pct:.1f}%)</p>
    </div>
    <h3>📋 Dados Completos — {snapshot_info['date']}</h3>
    {styled_html}
    """


# ===========================================================================
# Funções de menu
# ===========================================================================

def get_available_snapshots():
    snapshots_dir = "data/snapshots"
    if not os.path.exists(snapshots_dir):
        return []
    csv_files = [f for f in os.listdir(snapshots_dir) if f.endswith('.csv') and 'enhanced_' in f]
    csv_files.sort(reverse=True)
    return csv_files


def show_snapshot_selection():
    csv_files = get_available_snapshots()
    if not csv_files:
        print("❌ Nenhum snapshot encontrado")
        return None

    print("📁 Snapshots disponíveis:")
    print("0. 📊 Mais recente (automático)")
    for i, file in enumerate(csv_files[:10], 1):
        try:
            date_part = file.split('enhanced_')[1].replace('.csv', '')
            date_str  = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {date_part[9:11]}:{date_part[11:13]}"
            print(f"{i:2d}. {file} ({date_str})")
        except:
            print(f"{i:2d}. {file}")
    print()

    while True:
        try:
            choice = input(f"Escolha snapshot (0-{min(len(csv_files), 10)}): ").strip()
            if choice == '0':
                return csv_files[0]
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < min(len(csv_files), 10):
                    return csv_files[idx]
                else:
                    print("❌ Número fora do range")
            else:
                print("❌ Digite um número válido")
        except KeyboardInterrupt:
            return None
        except Exception as e:
            print(f"❌ Erro: {e}")
            return None


def show_comparison_snapshots():
    csv_files = get_available_snapshots()
    if len(csv_files) < 2:
        print("❌ Precisa de pelo menos 2 snapshots para comparar")
        return

    print("📊 COMPARAÇÃO DE SNAPSHOTS:")
    print("1. ⭐ Avançado — últimos 2 snapshots")
    print("2. ⭐ Avançado — escolher quantidade (2-10)")
    print("3. ⭐ Avançado — escolher snapshots específicos")
    print("0. ⬅️  Voltar")
    print()

    choice = input("Opção (0-3): ").strip()

    if choice in ('', '1'):
        _load_and_compare(csv_files[:2])
    elif choice == '2':
        qty_str = input("Quantidade de snapshots (2-10): ").strip()
        try:
            qty = max(2, min(10, int(qty_str)))
            _load_and_compare(csv_files[:qty])
        except:
            print("❌ Quantidade inválida")
    elif choice == '3':
        for i, file in enumerate(csv_files[:10], 1):
            print(f"{i}. {file}")
        indices = input("Números (ex: 1,3,5): ").strip()
        if indices:
            try:
                selected = [csv_files[int(x.strip()) - 1] for x in indices.split(',')
                            if 0 <= int(x.strip()) - 1 < len(csv_files)]
                if selected:
                    _load_and_compare(selected)
            except:
                print("❌ Formato inválido")


def _load_and_compare(file_list):
    """Carrega os arquivos selecionados e chama create_advanced_dashboard."""
    print(f"📊 Carregando {len(file_list)} snapshots...")

    # Check gems cache age
    cache_path = os.path.join(os.path.dirname(__file__), 'data', 'gems_cache.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            if 'cached_time' in cache_data:
                cache_time = datetime.fromisoformat(cache_data['cached_time'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                if cache_time.tzinfo:
                    cache_time = cache_time.replace(tzinfo=None)
                if now.tzinfo:
                    now = now.replace(tzinfo=None)
                age_seconds = (now - cache_time).total_seconds()
                age_hours = age_seconds / 3600
                print(f"💾 Cache de dados: {age_hours:.1f} horas ({age_seconds/60:.1f} min)")
            else:
                print("💾 Cache de dados: timestamp não encontrado")
        except Exception as e:
            print(f"💾 Cache de dados: erro ao ler ({e})")
    else:
        print("💾 Cache de dados: não encontrado")

    dfs           = []
    snapshot_info = []

    for i, file in enumerate(file_list):
        file_path = os.path.join("data/snapshots", file)
        try:
            df        = pd.read_csv(file_path)
            date_part = file.split('enhanced_')[1].replace('.csv', '')
            date_str  = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {date_part[9:11]}:{date_part[11:13]}"
            df['snapshot_period'] = f"Período {i+1} - {date_str}"
            df['snapshot_date']   = date_str
            df['snapshot_index']  = i
            dfs.append(df)
            snapshot_info.append({'file': file, 'date': date_str, 'index': i, 'count': len(df)})
            print(f"✅ {file} ({date_str}) — {len(df)} gems")
        except Exception as e:
            print(f"❌ Erro ao carregar {file}: {e}")

    if dfs:
        create_advanced_dashboard(dfs, snapshot_info)


def show_latest_csv(specific_file=None):
    """Mostra CSV com visualização Plotly — snapshot único com bloco global."""

    if specific_file:
        file_path   = specific_file
        latest_file = os.path.basename(file_path)
    else:
        print("🔍 BUSCANDO CSV MAIS RECENTE...")
        snapshots_dir = "data/snapshots"
        if not os.path.exists(snapshots_dir):
            print("❌ Pasta snapshots não encontrada")
            return
        csv_files = [f for f in os.listdir(snapshots_dir) if f.endswith('.csv') and 'enhanced_' in f]
        if not csv_files:
            print("❌ Nenhum CSV enhanced encontrado")
            return
        csv_files.sort(reverse=True)
        latest_file = csv_files[0]
        file_path   = os.path.join(snapshots_dir, latest_file)

    print(f"📁 Arquivo: {latest_file}")
    print(f"📅 Modificado: {datetime.fromtimestamp(os.path.getmtime(file_path))}")
    print()

    try:
        df = pd.read_csv(file_path)
        print(f"📊 Dados: {len(df)} gems, {len(df.columns)} colunas")
        print()

        changes = df['price_change_percentage_24h'].fillna(0)
        print("📊 ESTATÍSTICAS RÁPIDAS:")
        print("-" * 40)
        print(f"Market Cap Médio: ${df['market_cap'].mean():,.0f}")
        print(f"Volume Total: ${df['total_volume'].fillna(0).sum():,.0f}")
        print(f"Variação 24h Positivas: {(changes > 0).sum()}/{len(changes)} ({(changes > 0).mean()*100:.1f}%)")
        print()

        print("🎨 CRIANDO VISUALIZAÇÃO INTERATIVA (com histórico global)...")
        create_interactive_dashboard(df, latest_file)

    except Exception as e:
        print(f"❌ Erro ao processar CSV: {e}")


if __name__ == "__main__":
    import subprocess

    def check_and_run_gems_finder():
        cache_path = os.path.join("data", "gems_cache.json")
        if os.path.exists(cache_path):
            file_age = datetime.now().timestamp() - os.path.getmtime(cache_path)
            # 12 horas em segundos = 12 * 3600
            if file_age > 12 * 3600:
                print("⚠️ Cache de Gems expirado. Iniciando busca automática...")
                subprocess.run([sys.executable, "gems_finder.py"])
            else:
                print("✅ Cache de Gems está atualizado.")
        else:
            print("🔍 Nenhum cache de Gems encontrado. Rodando gems_finder pela primeira vez...")
            subprocess.run([sys.executable, "gems_finder.py"])

    # 1. Executa a checagem e atualização do Gems Finder
    check_and_run_gems_finder()

    # 2. Exibe o menu principal
    while True:
        print("\nEscolha uma opção:")
        print("1. ⭐ Comparar snapshots (DASHBOARD AVANÇADO)")
        print("2. 📊 Ver snapshot mais recente")
        print("3. 📊 Escolher snapshot específico")
        print("4. 📁 Listar todos os CSVs")
        print("5. ⏱️ Atualizar Macro Timing (BB%B)")
        print("0. 🚪 Sair")
        print()

        choice = input("Opção (0-5) [ENTER = 1]: ").strip()

        if choice in ('', '1'):
            show_comparison_snapshots()
        elif choice == '2':
            show_latest_csv()
        elif choice == '3':
            selected_file = show_snapshot_selection()
            if selected_file:
                show_latest_csv(os.path.join("data/snapshots", selected_file))
        elif choice == '4':
            csv_files = get_available_snapshots()
            if csv_files:
                print("📁 CSVs disponíveis:")
                for i, f in enumerate(csv_files, 1):
                    print(f"{i}. {f}")

        elif choice == '5':
            try:
                _build_macro_timing()
                print("✅ Macro Timing atualizado (data/macro/macro_timing.json)")
            except Exception as e:
                print(f"⚠️ Falha ao atualizar Macro Timing: {e}")

        elif choice == '0':
            print("👋 Até logo!")
            break
        else:
            print("❌ Opção inválida")
        print()
