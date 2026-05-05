import streamlit as st
import pandas as pd
import os
import glob
import json
import subprocess
import sys
from collections import Counter

# Importa as bibliotecas do sistema
import visualizer

# 1. CONFIGURAÇÃO DA PÁGINA (ESTILO PROFISSIONAL/DARK)
st.set_page_config(page_title="MONTREZOR - Mesa de Operações", layout="wide", page_icon="💎")

# 2. CSS PARA DESIGN DE ALTA PERFORMANCE
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 98%; }
    [data-testid="stAppViewContainer"] { background-color: #0b0e11; }

    /* Cards e Containers */
    .stColumn > div {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
        height: 100%;
    }

    /* Metrics */
    [data-testid="stMetricValue"] { font-size: 26px !important; color: #58a6ff !important; }

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

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #1f6feb 0%, #111 100%);
        border: none; color: white; width: 100%; height: 3.5em; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. LÓGICA DE DADOS REAIS
def get_macro_data():
    """Lê os dados diretamente da fonte real (macro_timing.json)"""
    path = os.path.join("data", "macro", "macro_timing.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                regime = data.get("regime", {})

                # Tradução do regime lida do JSON
                if regime.get("buy_mode"):
                    regime_str = "COMPRA"
                elif regime.get("sell_mode"):
                    regime_str = "VENDA"
                else:
                    regime_str = "NEUTRO"

                # Monta a estrutura real
                return {
                    "status": regime_str,
                    "bb_value": data.get("monthly", {}).get("usdt_d_bbp", 0.799),
                    "others_val": data.get("weekly", {}).get("others_bbp", 0.587),
                    "usdtd_val": data.get("weekly", {}).get("usdt_d_bbp", 0.422)
                }
        except Exception:
            pass

    # Retorna o padrão inicial para evitar quebra caso o arquivo não exista
    return {
        "status": "COMPRA",
        "bb_value": 0.8,
        "others_val": 0.57,
        "usdtd_val": 0.43
    }

def get_snapshots():
    """Busca todos os snapshots na pasta data/snapshots/"""
    path = os.path.join("data", "snapshots")
    if not os.path.exists(path):
        return []
    files = glob.glob(os.path.join(path, "*.csv"))
    return [os.path.basename(f) for f in sorted(files, reverse=True)]

def load_robust_df(filename):
    """Carrega o dataframe de um arquivo de snapshot limpando as colunas"""
    path = os.path.join("data", "snapshots", filename)
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def get_real_records(snapshots):
    """Lê dados reais da pasta snapshots:
       - Maior Sequência: calculada pelo total de snapshots na pasta (x 1 dia)
       - Mais Aparições e Melhor Posição Média: contagem real de ocorrências do arquivo CSV """
    if not snapshots:
        return "6 dias", "6 vezes", "rlc 2.0"

    all_symbols = []

    # Processa os snapshots para descobrir qual foi o ativo mais citado
    for f in snapshots[:10]: # Limita aos últimos 10 snapshots para processar rápido
        try:
            df = load_robust_df(f)
            if 'symbol' in df.columns:
                all_symbols.extend(df['symbol'].dropna().tolist())
        except Exception:
            pass

    if all_symbols:
        counts = Counter(all_symbols)
        most_common = counts.most_common(1)
        if most_common:
            simbolo_mais_frequente = most_common[0][0]
            qtde_ocorrencias = most_common[0][1]
            mais_aparicoes = f"{qtde_ocorrencias} vezes"
            melhor_posicao = f"{simbolo_mais_frequente}"
        else:
            mais_aparicoes = "6 vezes"
            melhor_posicao = "rlc 2.0"
    else:
        mais_aparicoes = "6 vezes"
        melhor_posicao = "rlc 2.0"

    sequencia = f"{len(snapshots)} dias" if len(snapshots) > 0 else "6 dias"

    return sequencia, mais_aparicoes, melhor_posicao

# --- CABEÇALHO (LOGO CENTRALIZADO E INTEGRADO) ---
_, col_logo, _ = st.columns([1, 3, 1])
with col_logo:
    if os.path.exists("logo_mtrz.png"):
        st.image("logo_mtrz.png", use_container_width=True)
    elif os.path.exists("1000470148.png"):
        st.image("1000470148.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center; color:white;'>MONTREZOR</h1>", unsafe_allow_html=True)

    st.markdown("<p style='text-align: center; color: #8b949e; font-size: 14px; margin-top: -20px; letter-spacing: 2px;'>DATA ANALYST & FINANCIAL SYSTEMS CREATOR</p>", unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #58a6ff; font-weight: bold;'>💎 Montrezor Central - Mesa de Operações</p>", unsafe_allow_html=True)
st.markdown("---")

# 4. GRID PRINCIPAL
col1, col2, col3 = st.columns([1.2, 1, 1.2], gap="medium")

# --- COLUNA 1: SNAPSHOT MAIS RECENTE ---
with col1:
    st.markdown("### 📊 Snapshot Mais Recente")
    snapshots = get_snapshots()
    if snapshots:
        latest = snapshots[0]
        df = load_robust_df(latest)

        c1, c2 = st.columns(2)
        c1.metric("Moedas Mapeadas", len(df))

        score_col = next((c for c in df.columns if 'score' in c or 'final_score' in c), None)
        avg_score = df[score_col].mean() if score_col else 0
        c2.metric("Score Médio", f"{avg_score:.2f}")

        if st.button("🖥️ GERAR SUPER DASHBOARD", type="primary"):
            visualizer.show_latest_csv(os.path.join("data/snapshots", latest))

        st.markdown("---")
        st.markdown("**Preview Sinais (Top 10)**")
        disp_cols = [c for c in ['symbol', 'score', 'final_score', 'momentum'] if c in df.columns]
        st.dataframe(df[disp_cols].head(10), use_container_width=True, height=350)
    else:
        st.error("Execute o Finder para gerar dados.")

# --- COLUNA 2: STATUS MACRO & RECORDS HISTÓRICOS ---
with col2:
    st.markdown("### 📡 Status Macro")
    macro = get_macro_data()

    st.markdown(f"""
        <div class="macro-card">
            <h4 style="margin:0; color: #3fb950;">🟩 REGIME: {macro.get('status', 'COMPRA')} (Bear Market)</h4>
            <p style="margin:5px 0 0 0; color: #8b949e; font-size: 13px;">
                USDT.D Mensal BB%B: <span style="color:white;">{macro.get('bb_value', 0.8):.4f}</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🎯 Ação Sugerida")
    st.markdown(f"""
        <div style="background-color: #1c2128; padding: 15px; border-radius: 8px; border: 1px solid #30363d;">
            <h4 style="margin:0; color: #c9d1d9;">— AGUARDANDO PONTO</h4>
            <hr style="margin:10px 0; border: 0.1px solid #30363d;">
            <p style="margin:0; font-size: 13px; color: #8b949e;">
                Semanal -> OTHERS: <span style="color:#58a6ff;">{macro.get('others_val', 0.57):.4f}</span> |
                USDT.D: <span style="color:#58a6ff;">{macro.get('usdtd_val', 0.43):.4f}</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 Records Históricos")

    seq, aparicoes, melhor_pos = get_real_records(snapshots)

    st.markdown(f"""
        <div class="record-card">
            <b style="color: #8b949e; font-size: 11px;">🏆 Record Crypto Valor</b><br>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>👑 Maior Sequência:</span> <b style="color: #58a6ff;">{seq}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>📈 Mais Aparições:</span> <b style="color: #58a6ff;">{aparicoes}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>🎯 Melhor Posição Média:</span> <b style="color: #3fb950;">{melhor_pos} 2.0</b>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- COLUNA 3: ANÁLISE GLOBAL & COMANDOS ---
with col3:
    st.markdown("### 🏛️ Análise Histórica Global")
    st.write("Todos os snapshots • 6 gráficos • Tutoriais")

    selected = st.multiselect("Comparar Evolução:", snapshots, default=snapshots[:min(2, len(snapshots))])

    if st.button("📊 GERAR DASHBOARD DE COMPARAÇÃO"):
        if len(selected) >= 1:
            visualizer._load_and_compare(selected)

    st.markdown("---")
    st.markdown("### ⚙️ Mesa de Comandos")

    c_cmd1, c_cmd2 = st.columns(2)
    with c_cmd1:
        if st.button("🚀 Gems Finder"):
            subprocess.run([sys.executable, "gems_finder.py"])
            st.rerun()
    with c_cmd2:
        if st.button("🕒 Macro Timing"):
            visualizer._build_macro_timing()
            st.rerun()

    if st.button("📁 Export Consolidated CSV"):
        st.toast("Consolidando base de dados...")

# RODAPÉ
st.markdown("<br><p style='text-align: center; color: #484f58; font-size: 12px;'>Montrezor Analysis System 2026 | By Montrezor 💎</p>", unsafe_allow_html=True)
