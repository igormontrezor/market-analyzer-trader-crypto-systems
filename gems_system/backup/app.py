import streamlit as st
import pandas as pd
import os
import glob
import json
import subprocess
import sys
import requests
from collections import Counter
from datetime import datetime
import time

# Importa as bibliotecas do sistema
import visualizer

# 1. CONFIGURAÇÃO DA PÁGINA (ESTILO PROFISSIONAL/DARK)
st.set_page_config(page_title="MONTREZOR - Mesa de Operações", layout="wide", page_icon="💎")

# 2. CSS PARA DESIGN DE ALTA PERFORMANCE E HUD
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 98%; }
    [data-testid="stAppViewContainer"] { background-color: #0b0e11; }

    /* Cards e Containers Principais */
    .stColumn > div {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
        height: 100%;
    }

    /* Blocos personalizados */
    .macro-card {
        background-color: #0d1117;
        padding: 15px;
        border-radius: 8px;
        border-left: 6px solid #238636;
        margin-bottom: 15px;
    }
    .record-card {
        background-color: #1c2128;
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #30363d;
        margin-top: 10px;
        color: #c9d1d9;
    }

    /* HUD Superior Customizado */
    .hud-box {
        background-color: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px 15px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 125px;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
    }
    .hud-title {
        color: #8b949e;
        font-size: 11px;
        text-transform: uppercase;
        font-weight: bold;
        letter-spacing: 1px;
        margin-bottom: 8px;
        margin-top: 0;
    }
    .hud-data-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
        font-size: 13px;
        color: #c9d1d9;
    }
    .hud-value {
        font-weight: bold;
        color: #58a6ff;
    }
    .hud-value-green { color: #3fb950; font-weight: bold; }
    .hud-value-red { color: #f85149; font-weight: bold; }

    /* Animação para Super Alertas */
    @keyframes blink {
        0% { opacity: 1; }
        50% { opacity: 0.3; }
        100% { opacity: 1; }
    }
    .super-buy-alert {
        background:#238636; color:white; padding:8px; border-radius:5px;
        text-align:center; font-weight:bold; margin-top:8px;
        border: 2px solid #fff; animation: blink 2s infinite;
    }
    .super-sell-alert {
        background:#da3633; color:white; padding:8px; border-radius:5px;
        text-align:center; font-weight:bold; margin-top:8px;
        border: 2px solid #fff; animation: blink 2s infinite;
    }
    .neutral-alert {
        background:#8b949e; color:white; padding:8px; border-radius:5px;
        text-align:center; font-weight:bold; margin-top:8px;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #1f6feb 0%, #111 100%);
        border: none; color: white; width: 100%; height: 3.5em; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

def get_btc_funding_rate_real():
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
        response = requests.get(url, timeout=5)
        rate = float(response.json().get('lastFundingRate', 0)) * 100

        # REGISTRO EM CSV (Histórico de 1 em 1 hora unificado)
        csv_path = os.path.join("data", "macro", "funding_rate_history.csv")
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        now = datetime.now()
        timestamp_hour = now.strftime("%Y-%m-%d %H:00:00") # Arredonda para a hora cheia

        # Verifica se já registrou essa hora para não duplicar
        already_logged = False
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines and timestamp_hour in lines[-1]:
                        already_logged = True
            except:
                pass

        if not already_logged:
            file_exists = os.path.exists(csv_path)
            with open(csv_path, 'a', encoding='utf-8') as f:
                if not file_exists:
                    f.write("timestamp,funding_rate\n")
                f.write(f"{timestamp_hour},{rate:.6f}\n")

        return rate
    except:
        return 0.01

def get_snapshots():
    path = os.path.join("data", "snapshots")
    if not os.path.exists(path): return []
    files = glob.glob(os.path.join(path, "*.csv"))
    return sorted(files, reverse=True)

@st.cache_data(ttl=60)
def get_macro_data():
    path = os.path.join("data", "macro", "macro_timing.json")

    res = {
        "status": "INDEFINIDO", "bb_value": 0.0, "others_val": 0.0, "usdtd_val": 0.0,
        "last_update": "N/A", "buy_trigger": False, "rebound": False,
        "funding_rate": 0.01, "funding_signal": "NEUTRAL", "super_alert": "OFF"
    }

    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                regime = data.get("regime", {})
                signal = data.get("signal", {})

                buy_mode = regime.get("buy_mode", False)
                sell_mode = regime.get("sell_mode", False)

                if buy_mode: res["status"] = "COMPRA"
                elif sell_mode: res["status"] = "VENDA"
                else: res["status"] = "NEUTRO"

                res["bb_value"] = data.get("monthly", {}).get("usdt_d_bbp", 0.0)
                res["others_val"] = data.get("weekly", {}).get("others_bbp", 0.0)
                res["usdtd_val"] = data.get("weekly", {}).get("usdt_d_bbp", 0.0)

                weekly_buy_trigger = signal.get("weekly_buy_trigger", False)
                weekly_sell_trigger = signal.get("weekly_sell_trigger", False)

                res["buy_trigger"] = weekly_buy_trigger
                res["rebound"] = signal.get("tactical_rebound", False)

                funding_rate = get_btc_funding_rate_real()
                res["funding_rate"] = funding_rate

                res["funding_signal"] = "NEUTRAL"
                res["super_alert"] = "OFF"

                # LÓGICA DE CONFLUÊNCIA EXATA (Regime -> Funding -> Semanal)
                if buy_mode:
                    if funding_rate < 0:
                        res["funding_signal"] = "BUY"
                        if weekly_buy_trigger:
                            res["super_alert"] = "SUPER_BUY"
                elif sell_mode:
                    if funding_rate > 0.08:
                        res["funding_signal"] = "SELL"
                        if weekly_sell_trigger:
                            res["super_alert"] = "SUPER_SELL"

                gen_at = data.get("generated_at", "")
                if gen_at:
                    try:
                        res["last_update"] = datetime.fromisoformat(gen_at.replace("Z", "+00:00")).strftime('%d/%m %H:%M')
                    except:
                        res["last_update"] = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%m %H:%M')
        except: pass
    return res

@st.cache_data(ttl=300)
def get_real_records(snapshots):
    if not snapshots: return "0 registros", "Nenhuma", "Nenhuma"
    all_symbols = []; symbol_scores = {}

    for f in snapshots[:20]:
        try:
            df = pd.read_csv(f)
            df.columns = [c.strip().lower() for c in df.columns]
            if 'symbol' in df.columns:
                all_symbols.extend(df['symbol'].dropna().tolist())
                score_col = next((c for c in df.columns if 'score' in c or 'final_score' in c), None)
                if score_col:
                    for _, row in df.iterrows():
                        sym = row['symbol']
                        if sym not in symbol_scores: symbol_scores[sym] = []
                        symbol_scores[sym].append(row[score_col])
        except: pass

    if all_symbols:
        counts = Counter(all_symbols)
        most_common = counts.most_common(1)[0]
        mais_aparicoes = f"{most_common[0]} ({most_common[1]}x)"
        valid_scores = {k: sum(v)/len(v) for k, v in symbol_scores.items() if len(v) >= 2}
        if valid_scores:
            best_avg = max(valid_scores.items(), key=lambda x: x[1])
            melhor_posicao = f"{best_avg[0]} ({best_avg[1]:.1f} pts)"
        else: melhor_posicao = f"{most_common[0]} (Recente)"
    else: mais_aparicoes = melhor_posicao = "N/A"

    return f"{len(snapshots)} registros reais", mais_aparicoes, melhor_posicao

# 4. PRÉ-CARREGAMENTO
snapshots_list = get_snapshots()
macro_data = get_macro_data()
last_snap_time = datetime.fromtimestamp(os.path.getmtime(snapshots_list[0])).strftime('%d/%m %H:%M') if snapshots_list else "Nenhum"
db_status = "Online" if os.path.exists("data/gems_cache.json") else "Aguardando"
db_color = "hud-value-green" if db_status == "Online" else "hud-value"

# --- CABEÇALHO HUD ---
col_left, col_logo, col_right = st.columns([1.2, 2, 1.2])

with col_left:
    st.markdown(f"""
        <div style="padding-top: 15px;">
            <div class="hud-box">
                <p class="hud-title">⚙️ SYSTEM & DATA HEALTH</p>
                <div class="hud-data-row"><span>Base de Dados:</span><span class="{db_color}">● {db_status}</span></div>
                <div class="hud-data-row"><span>Snapshots Salvos:</span><span class="hud-value">{len(snapshots_list)}</span></div>
                <div class="hud-data-row"><span>Último Scan:</span><span class="hud-value" style="color:#8b949e;">{last_snap_time}</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_logo:
    if os.path.exists("logo_mtrz.png"): st.image("logo_mtrz.png", width='stretch')
    elif os.path.exists("1000470148.png"): st.image("1000470148.png", width='stretch')
    else: st.markdown("<h1 style='text-align: center; color:white; margin-top: 20px;'>MONTREZOR</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8b949e; font-size: 14px; margin-top: -20px; letter-spacing: 2px;'>DATA ANALYST & FINANCIAL SYSTEMS CREATOR</p>", unsafe_allow_html=True)

with col_right:
    m = get_macro_data()
    f_rate = m['funding_rate']
    f_color = "#3fb950" if f_rate < 0 else ("#f85149" if f_rate > 0.08 else "#8b949e")

    # Exibição do Alerta com hierarquia visual e classes do CSS
    super_html = ""
    if m['super_alert'] == "SUPER_BUY":
        super_html = '<div class="super-buy-alert">⚡ SUPER ALERTA: COMPRA</div>'
    elif m['super_alert'] == "SUPER_SELL":
        super_html = '<div class="super-sell-alert">🚨 SUPER ALERTA: VENDA</div>'
    elif m['funding_signal'] == "BUY":
        super_html = '<div class="neutral-alert" style="background:#238636; border: 1px solid #3fb950; color: white;">🟢 SINAL DE COMPRA (Funding)</div>'
    elif m['funding_signal'] == "SELL":
        super_html = '<div class="neutral-alert" style="background:#da3633; border: 1px solid #f85149; color: white;">🔴 SINAL DE VENDA (Funding)</div>'
    else:
        super_html = '<div class="neutral-alert">⚪ NEUTRO / ESTÁVEL</div>'

    st.markdown(f"""
        <div style="padding-top: 0px;">
            <div class="hud-box" style="height: 185px;">
                <p class="hud-title">📡 MARKET INTELLIGENCE</p>
                <div class="hud-data-row"><span>Regime Macro:</span><span class="hud-value-green">{m['status']}</span></div>
                <div class="hud-data-row"><span>BTC Funding:</span><b style="color: {f_color};">{f_rate:.4f}%</b></div>
                <div class="hud-data-row"><span>Macro Sync:</span><span class="hud-value" style="color:#8b949e;">{m['last_update']}</span></div>
                {super_html}
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #58a6ff; font-weight: bold; margin-top: 10px;'>💎 Montrezor Central - Mesa de Operações</p>", unsafe_allow_html=True)
st.markdown("---")

# 5. GRID PRINCIPAL
col1, col2, col3 = st.columns([1.2, 1, 1.2], gap="medium")

with col1:
    st.markdown("### 📊 Snapshot Mais Recente")
    if snapshots_list:
        latest = snapshots_list[0]
        df = pd.read_csv(latest)
        df.columns = [c.strip().lower() for c in df.columns]
        c1, c2 = st.columns(2)
        c1.metric("Moedas Mapeadas", len(df))
        score_col = next((c for c in df.columns if 'score' in c or 'final_score' in c), None)
        avg_score = df[score_col].mean() if score_col else 0
        c2.metric("Score Médio", f"{avg_score:.2f}")
        if st.button("🖥️ GERAR SUPER DASHBOARD", type="primary"): visualizer.show_latest_csv(latest)
        st.markdown("---")
        st.markdown("**Preview Sinais (Top 10)**")
        disp_cols = [c for c in ['symbol', 'score', 'final_score', 'momentum', 'sector'] if c in df.columns]
        st.dataframe(df[disp_cols].head(10), width='stretch', height=350)
    else: st.error("Execute o Finder para gerar dados.")

with col2:
    st.markdown("### 📡 Status Macro")
    border_color = "#238636" if macro_data.get('status') == "COMPRA" else "#da3633"
    st.markdown(f"""
        <div class="macro-card" style="border-left: 6px solid {border_color};">
            <h4 style="margin:0; color: {border_color};">🟩 REGIME: {macro_data.get('status')}</h4>
            <p style="margin:5px 0 0 0; color: #8b949e; font-size: 13px;">
                USDT.D Mensal BB%B: <span style="color:white;">{macro_data.get('bb_value', 0):.4f}</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    acao_sugerida = "AGUARDANDO PONTO"
    if macro_data.get('status') == "COMPRA" and macro_data.get('others_val', 0) < 0.2: acao_sugerida = "PONTO DE ACUMULAÇÃO"

    st.markdown("### 🎯 Ação Sugerida")
    st.markdown(f"""
        <div style="background-color: #1c2128; padding: 15px; border-radius: 8px; border: 1px solid #30363d;">
            <h4 style="margin:0; color: #c9d1d9;">— {acao_sugerida}</h4>
            <hr style="margin:10px 0; border: 0.1px solid #30363d;">
            <p style="margin:0; font-size: 13px; color: #8b949e;">
                Semanal -> OTHERS: <span style="color:#58a6ff;">{macro_data.get('others_val', 0):.4f}</span> |
                USDT.D: <span style="color:#58a6ff;">{macro_data.get('usdtd_val', 0):.4f}</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 Records Históricos Reais")
    seq, aparicoes, melhor_pos = get_real_records(snapshots_list)
    st.markdown(f"""
        <div class="record-card">
            <b style="color: #8b949e; font-size: 11px;">🏆 Dados de Acumulação Local</b><br>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>👑 Base de Dados:</span> <b style="color: #58a6ff;">{seq}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>📈 Mais Aparições:</span> <b style="color: #58a6ff;">{aparicoes}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>🎯 Melhor Score Médio:</span> <b style="color: #3fb950;">{melhor_pos}</b>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("### 🏛️ Análise Histórica Global")
    st.write("Comparação Avançada e Tutoriais")
    snapshot_names = [os.path.basename(f) for f in snapshots_list]
    selected = st.multiselect("Comparar Evolução:", snapshot_names, default=snapshot_names[:min(2, len(snapshot_names))])
    if st.button("📊 GERAR DASHBOARD DE COMPARAÇÃO"):
        if len(selected) >= 1: visualizer._load_and_compare(selected)

    st.markdown("---")
    st.markdown("### ⚙️ Mesa de Comandos")
    c_cmd1, c_cmd2 = st.columns(2)
    with c_cmd1:
        if st.button("🚀 Rodar Gems Finder"):
            with st.spinner("Processando mercado..."): subprocess.run([sys.executable, "gems_finder.py"])
            st.rerun()
    with c_cmd2:
        if st.button("🕒 Atualizar Macro"):
            with st.spinner("Buscando dados macro..."): visualizer._build_macro_timing()
            st.rerun()

# TABELAS ADICIONAIS
st.markdown("---")
tab1, tab2 = st.tabs(["📁 Database de Arquivos", "📖 Guia do Sistema"])
with tab1:
    st.write("Lista completa de snapshots disponíveis:")
    for snap in snapshots_list: st.text(f"• {os.path.basename(snap)}")
with tab2:
    st.info("O sistema analisa o BB%B mensal do USDT.D para definir o Regime Macro e cruza com a Funding Rate para o Super Alerta.")

# RODAPÉ
st.markdown("<br><p style='text-align: center; color: #484f58; font-size: 12px;'>Montrezor Analysis System | Powered by Data 💎</p>", unsafe_allow_html=True)
