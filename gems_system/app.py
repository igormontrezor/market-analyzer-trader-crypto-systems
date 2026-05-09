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

# Importações para o Heatmap
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tvDatafeed import TvDatafeed, Interval

# Importa as bibliotecas do sistema
import visualizer

# 1. CONFIGURAÇÃO DA PÁGINA (ESTILO PROFISSIONAL/DARK)
st.set_page_config(page_title="MONTREZOR - Mesa de Operações", layout="wide", page_icon="💎")

# --- ADIÇÃO: NAVEGAÇÃO AUTOMÁTICA ---
with st.sidebar:
    st.markdown("### 🧭 Central de Controle")
    st.markdown("**💎 Mesa de Operações** (página atual)")
    st.markdown("---")

    st.markdown("### 📈 Trading System")

    # Botão para abrir automaticamente
    if st.button("🚀 Abrir Trading System", type="primary", use_container_width=True):
        import subprocess
        import sys
        import webbrowser
        import time
        import os

        try:
            st.info("🔄 Iniciando Trading System...")

            # Caminhos relativos genéricos
            current_dir = os.getcwd()
            trading_dir = os.path.abspath(os.path.join(current_dir, "..", "analysis_system", "trading"))
            trading_file = os.path.join(trading_dir, "trading_system.py")

            # Verificar se arquivo existe
            if not os.path.exists(trading_file):
                st.error(f"❌ Arquivo não encontrado: {trading_file}")
                st.stop()

            # Executar em background sem shell
            process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", trading_file, "--server.port", "8502"],
                cwd=trading_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Esperar e abrir no navegador
            time.sleep(3)
            webbrowser.open("http://localhost:8502")

            st.success("✅ Trading System aberto em http://localhost:8502")
            st.info("🌐 Sistema iniciado em background!")

        except Exception as e:
            st.error(f"❌ Erro: {e}")
            st.code(f"Python: {sys.executable}")
            st.code(f"Arquivo: {trading_file}")

    st.markdown("*Clique para abrir automaticamente*")
    st.markdown("---")
# --- FIM DA ADIÇÃO ---

# Título principal no topo
st.title("💎 Sistema de Macro e Gems - Igor Montrezor")
st.markdown("<p style='color: #8b949e; margin-top: -15px; margin-bottom: 30px;'>Método interativo passo a passo para execução de alta performance.</p>", unsafe_allow_html=True)

# Terminal session state e funções
if 'terminal_output' not in st.session_state:
    st.session_state.terminal_output = []

def add_terminal_output(message, msg_type="info"):
    """Adiciona mensagem ao terminal com timestamp e cor"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    color_map = {
        "info": "#58a6ff",      # Azul
        "success": "#2ecc71",   # Verde
        "error": "#e74c3c",     # Vermelho
        "warning": "#f39c12",   # Laranja
        "command": "#c9d1d9"    # Branco
    }

    color = color_map.get(msg_type, "#c9d1d9")
    st.session_state.terminal_output.append({
        "timestamp": timestamp,
        "message": message,
        "type": msg_type,
        "color": color
    })

    # Manter apenas últimas 200 linhas
    if len(st.session_state.terminal_output) > 200:
        st.session_state.terminal_output = st.session_state.terminal_output[-200:]

def run_command_with_terminal(command, description=""):
    """Executa comando e mostra output em tempo real no terminal"""
    # Formatar comando para exibição mais limpa
    if isinstance(command, list):
        if len(command) == 3 and command[1] == '-c':
            # É um comando Python com -c
            cmd_display = f"python -c \"{command[2]}\""
        else:
            # Outra lista de comandos
            cmd_display = " ".join(command)
    else:
        cmd_display = str(command)

    add_terminal_output(f"$ {cmd_display}", "command")
    if description:
        add_terminal_output(f"# {description}", "info")

    # Executar comando e mostrar resultado final
    try:
        import subprocess
        import sys

        # Usar Popen para output em tempo real
        process = subprocess.Popen(
            command if isinstance(command, list) else command.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        output_lines = []
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                line = output.strip()
                output_lines.append(line)
                # Colorir baseado no conteúdo
                if "" in line or "success" in line.lower():
                    add_terminal_output(line, "success")
                elif "" in line or "error" in line.lower() or "failed" in line.lower():
                    add_terminal_output(line, "error")
                elif "" in line or "warning" in line.lower():
                    add_terminal_output(line, "warning")
                else:
                    add_terminal_output(line, "info")

        add_terminal_output("", "success")

    except Exception as e:
        add_terminal_output(f"Erro ao executar comando: {str(e)}", "error")

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

    /* Espaço no topo para evitar barra do Streamlit */
    .block-container {
        padding-top: 2rem;
        max-width: 95%;
    }
    [data-testid="stAppViewContainer"] {
        background-color: #0b0e11;
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

@st.cache_data(ttl=1800)
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

@st.cache_data(ttl=1800)
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
                res["capitulation_lock"] = regime.get("capitulation_lock", False) # ADIÇÃO

                if buy_mode: res["status"] = "COMPRA"
                elif sell_mode: res["status"] = "VENDA"
                else: res["status"] = "NEUTRO"

                res["bb_value"] = data.get("monthly", {}).get("usdt_d_bbp", 0.0)
                res["others_val"] = data.get("weekly", {}).get("others_bbp", 0.0)
                res["usdtd_val"] = data.get("weekly", {}).get("usdt_d_bbp", 0.0)

                weekly_buy_trigger = signal.get("weekly_buy_trigger", False)
                weekly_sell_trigger = signal.get("weekly_sell_trigger", False)

                res["buy_trigger"] = weekly_buy_trigger
                res["sell_trigger"] = weekly_sell_trigger # ← LINHA ADICIONADA AQUI
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

@st.cache_data(ttl=1800)
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
            melhor_posicao = f"{best_avg[0]} ({best_avg[1]:.1f})"
        else: melhor_posicao = f"{most_common[0]} (Recente)"
    else: mais_aparicoes = melhor_posicao = "N/A"

    return f"{len(snapshots)} registros", mais_aparicoes, melhor_posicao

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

st.code("💎 Montrezor Central - Mesa de Operações", language=None)

# Terminal logo abaixo do título
with st.expander("🖥️ Terminal (Tempo Real)", expanded=True):
    # Construir texto do terminal
    terminal_text = "🖥️ MONTREZOR TERMINAL\n" + "="*50 + "\n"

    for entry in st.session_state.terminal_output:
        terminal_text += f"[{entry['timestamp']}] {entry['message']}\n"

    # Mostrar como código
    st.code(terminal_text, language=None)

    # Botões do terminal
    col_term1, col_term2, col_term3 = st.columns([1, 1, 1])

    with col_term1:
        if st.button("📋 Mostrar Watchlist"):
            if os.path.exists("data/watchlist_selecionada.csv"):
                df_watchlist = pd.read_csv("data/watchlist_selecionada.csv")
                if not df_watchlist.empty:
                    add_terminal_output("📌 MINHA WATCHLIST ATUAL:", "info")
                    add_terminal_output("═" * 80, "info")
                    add_terminal_output(f"{'SYMBOL':<8} | {'MC':<8} | {'RATIO':<7} | {'SCORE':<6} | {'ZONE':<10} | {'VOL':<8} | {'24H':<8} | {'7D':<8} | {'30D':<8}", "info")
                    add_terminal_output("-" * 80, "info")

                    for _, row in df_watchlist.iterrows():
                        symbol = str(row.get('symbol', '')).upper()
                        mc = row.get('market_cap', 0)
                        ratio = row.get('ratio', 0)
                        score = row.get('final_score', 0)
                        zone = row.get('zone', 'N/A')
                        volume = row.get('total_volume', 0)
                        change_24h = row.get('price_change_percentage_24h', 0)
                        change_7d = row.get('price_change_percentage_7d_in_currency', 0)
                        change_30d = row.get('price_change_percentage_30d_in_currency', 0)

                        # Formatar valores
                        mc_formatted = f"{mc/1000000:.1f}M" if mc > 1000000 else f"{mc/1000:.1f}K"
                        ratio_formatted = f"{ratio:.2f}"
                        score_formatted = f"{score:.1f}"
                        zone_formatted = str(zone)[:8]
                        vol_formatted = f"{volume/1000000:.1f}M" if volume > 1000000 else f"{volume/1000:.1f}K"

                        # Formatar porcentagens com cores
                        def format_change(value):
                            if value is None or value == 0:
                                return "⚪0.0%"
                            color = "🟢" if value > 0 else "🔴"
                            return f"{color}{value:+.1f}%"

                        def safe_format(value, formatter, default="N/A"):
                            if value is None or value == 0:
                                return default
                            return formatter(value)

                        change_24h_formatted = safe_format(change_24h, format_change, "⚪0.0%")
                        change_7d_formatted = safe_format(change_7d, format_change, "N/A     ")
                        change_30d_formatted = safe_format(change_30d, format_change, "N/A     ")

                        add_terminal_output(f"{symbol:<8} | {mc_formatted:<8} | {ratio_formatted:<7} | {score_formatted:<6} | {zone_formatted:<10} | {vol_formatted:<8} | {change_24h_formatted:<8} | {change_7d_formatted:<8} | {change_30d_formatted:<8}", "success")

                    add_terminal_output("═" * 80, "info")
                    add_terminal_output(f"📊 Total: {len(df_watchlist)} moedas na watchlist", "success")
                else:
                    add_terminal_output("⚠️ Watchlist vazia!", "warning")
            else:
                pass  # Não mostrar mensagem se arquivo não existe

    with col_term2:
        # Verificar se há busca em andamento
        if st.session_state.get('updating_watchlist', False):
            st.info("🔄 Atualizando dados... aguarde!")
            st.progress(st.session_state.get('update_progress', 0))
        else:
            if st.button("🔄 ATUALIZAR DADOS DA WATCHLIST"):
                if os.path.exists("data/watchlist_selecionada.csv"):
                    df_watchlist = pd.read_csv("data/watchlist_selecionada.csv")
                    if not df_watchlist.empty:
                        # Marcar que está atualizando
                        st.session_state.updating_watchlist = True
                        st.session_state.update_progress = 0

                        add_terminal_output("🔄 ATUALIZANDO DADOS DA WATCHLIST...", "info")
                        add_terminal_output("═" * 50, "info")

                    # Importar biblioteca para buscar dados em tempo real
                    try:
                        import requests
                        from datetime import datetime

                        symbols = df_watchlist['symbol'].tolist()
                        add_terminal_output(f"📡 Buscando dados para {len(symbols)} moedas...", "info")

                        # Busca real de dados da CoinGecko API
                        updated_data = []
                        add_terminal_output("🔄 Conectando à CoinGecko API...", "info")

                        for i, symbol in enumerate(symbols, 1):
                            try:
                                # Atualizar progresso
                                progress = (i - 1) / len(symbols)
                                st.session_state.update_progress = progress

                                add_terminal_output(f"📡 [{i}/{len(symbols)}] Buscando {symbol.upper()}...", "info")

                                # Delay maior para evitar rate limit da API
                                if i > 1:
                                    time.sleep(5.0)  # Aumentar para 5 segundos

                                # Busca inteligente com endpoint /search
                                try:
                                    # 1. Buscar ID correto usando search
                                    search_url = f"https://api.coingecko.com/api/v3/search?query={symbol.lower()}"
                                    search_response = requests.get(search_url, timeout=10, headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                    })

                                    coin_id = None
                                    if search_response.status_code == 200:
                                        search_data = search_response.json()
                                        if search_data.get('coins') and len(search_data['coins']) > 0:
                                            coin_id = search_data['coins'][0]['id']  # Pegar o mais relevante
                                            add_terminal_output(f"   🔍 ID encontrado: {coin_id}", "info")

                                    if coin_id:
                                        # 2. Buscar dados com ID correto
                                        endpoints = [
                                            f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                                            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true&include_30d_change=true&include_market_cap=true&include_24hr_vol=true"
                                        ]
                                    else:
                                        # Fallback: tentar direto com symbol
                                        endpoints = [
                                            f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}",
                                            f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true&include_30d_change=true&include_market_cap=true&include_24hr_vol=true"
                                        ]
                                except:
                                    # Fallback em caso de erro no search
                                    endpoints = [
                                        f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}",
                                        f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true&include_30d_change=true&include_market_cap=true&include_24hr_vol=true"
                                    ]

                                data_found = False
                                retry_count = 0
                                max_retries = 50  # Máximo de tentativas por moeda

                                while not data_found and retry_count < max_retries:
                                    retry_count += 1
                                    add_terminal_output(f"   🔍 Tentativa {retry_count}/{max_retries} para {symbol.upper()}...", "info")

                                    for j, endpoint_url in enumerate(endpoints, 1):
                                        try:
                                            # Delay crescente a cada tentativa
                                            if retry_count > 1:
                                                delay = min(10, 2 + retry_count)  # 3s, 4s, 5s... até 10s
                                                time.sleep(delay)

                                            response = requests.get(endpoint_url, timeout=15, headers={
                                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                            })

                                            if response.status_code == 200:
                                                data = response.json()
                                                add_terminal_output(f"   ✅ Tentativa {retry_count} funcionou!", "success")

                                                if 'simple' in endpoint_url:
                                                    # Endpoint simples
                                                    check_id = coin_id if coin_id else symbol.lower()
                                                    if check_id in data:
                                                        coin_data = data[check_id]
                                                        current_data = {
                                                            'symbol': symbol.upper(),
                                                            'name': coin_data.get('name', symbol.upper()),
                                                            'current_price': coin_data.get('usd', 0),
                                                            'market_cap': coin_data.get('usd_market_cap', 0),
                                                            'total_volume': coin_data.get('usd_24h_vol', 0),
                                                            'price_change_percentage_24h': coin_data.get('usd_24h_change', 0),
                                                            'price_change_percentage_7d_in_currency': coin_data.get('usd_7d_change', 0),
                                                            'price_change_percentage_30d_in_currency': coin_data.get('usd_30d_change', 0),
                                                            'market_cap_rank': 0,
                                                            'last_updated': datetime.now().isoformat()
                                                        }
                                                        data_found = True
                                                        add_terminal_output(f"   📊 Dados: MC=${coin_data.get('usd_market_cap', 0):,.0f}, Vol=${coin_data.get('usd_24h_vol', 0):,.0f}", "info")
                                                else:
                                                    # Endpoint completo
                                                    market_data = data.get('market_data', {})
                                                    current_data = {
                                                        'symbol': symbol.upper(),
                                                        'name': data.get('name', ''),
                                                        'current_price': market_data.get('current_price', {}).get('usd', 0),
                                                        'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                                                        'total_volume': market_data.get('total_volume', {}).get('usd', 0),
                                                        'price_change_percentage_24h': market_data.get('price_change_percentage_24h', 0),
                                                        'price_change_percentage_7d_in_currency': market_data.get('price_change_percentage_7d', 0),
                                                        'price_change_percentage_30d_in_currency': market_data.get('price_change_percentage_30d', 0),
                                                        'market_cap_rank': market_data.get('market_cap_rank', 0),
                                                        'last_updated': data.get('last_updated', '')
                                                    }
                                                    data_found = True
                                                    add_terminal_output(f"   📊 Dados: MC=${market_data.get('market_cap', {}).get('usd', 0):,.0f}, Vol=${market_data.get('total_volume', {}).get('usd', 0):,.0f}", "info")

                                                if data_found:
                                                    # Manter dados antigos que não temos na API
                                                    old_row = df_watchlist[df_watchlist['symbol'] == symbol].iloc[0]
                                                    for col in ['ratio', 'final_score', 'momentum', 'zone', 'sector', 'accumulation_score']:
                                                        if col in old_row:
                                                            current_data[col] = old_row[col]

                                                    updated_data.append(current_data)
                                                    add_terminal_output(f"✅ {symbol.upper()} - Dados atualizados em tempo real (tentativa {retry_count})", "success")
                                                    break
                                            elif response.status_code == 429:
                                                add_terminal_output(f"   ⚠️ Rate limit, tentativa {retry_count}...", "warning")
                                                continue  # Próxima tentativa com delay crescente
                                            else:
                                                add_terminal_output(f"   ❌ HTTP {response.status_code}, tentativa {retry_count}", "warning")

                                        except Exception as e:
                                            add_terminal_output(f"   ❌ Erro tentativa {retry_count}: {str(e)[:30]}", "warning")
                                            continue

                                    if data_found:
                                        break

                                if not data_found:
                                    # Se todos os endpoints falharem, usar dados do CSV
                                    row = df_watchlist[df_watchlist['symbol'] == symbol].iloc[0]
                                    updated_data.append(row)
                                    add_terminal_output(f"⚠️ {symbol.upper()} - Usando dados cache (API indisponível)", "warning")

                            except Exception as e:
                                # Se der erro, usar dados do CSV
                                try:
                                    row = df_watchlist[df_watchlist['symbol'] == symbol].iloc[0]
                                    updated_data.append(row)
                                    add_terminal_output(f"⚠️ {symbol.upper()} - Usando dados cache (Erro: {str(e)[:50]})", "warning")
                                except:
                                    add_terminal_output(f"❌ {symbol.upper()} - Erro ao processar", "error")

                        # Atualizar CSV com novos dados
                        if updated_data:
                            df_updated = pd.DataFrame(updated_data)
                            df_updated.to_csv("data/watchlist_selecionada.csv", index=False)
                            add_terminal_output("💾 Watchlist atualizada com dados frescos!", "success")

                        # Mostrar dados atualizados
                        add_terminal_output("═" * 80, "info")
                        add_terminal_output(f"{'SYMBOL':<8} | {'MC':<8} | {'RATIO':<7} | {'SCORE':<6} | {'ZONE':<10} | {'VOL':<8} | {'24H':<8} | {'7D':<8} | {'30D':<8}", "info")
                        add_terminal_output("-" * 80, "info")

                        for _, row in df_updated.iterrows():
                            symbol = str(row.get('symbol', '')).upper()
                            mc = row.get('market_cap', 0)
                            ratio = row.get('ratio', 0)
                            score = row.get('final_score', 0)
                            zone = row.get('zone', 'N/A')
                            volume = row.get('total_volume', 0)
                            change_24h = row.get('price_change_percentage_24h', 0)
                            change_7d = row.get('price_change_percentage_7d_in_currency', 0)
                            change_30d = row.get('price_change_percentage_30d_in_currency', 0)


                            # Formatar valores
                            mc_formatted = f"{mc/1000000:.1f}M" if mc > 1000000 else f"{mc/1000:.1f}K"
                            ratio_formatted = f"{ratio:.2f}"
                            score_formatted = f"{score:.1f}"
                            zone_formatted = str(zone)[:8]
                            vol_formatted = f"{volume/1000000:.1f}M" if volume > 1000000 else f"{volume/1000:.1f}K"


                            def format_change(value):
                                if value is None or value == 0:
                                    return "⚪0.0%"
                                color = "🟢" if value > 0 else "🔴"
                                return f"{color}{value:+.1f}%"

                            def safe_format(value, formatter, default="N/A"):
                                if value is None or value == 0:
                                    return default
                                return formatter(value)

                            change_24h_formatted = safe_format(change_24h, format_change, "⚪0.0%")
                            change_7d_formatted = safe_format(change_7d, format_change, "N/A     ")
                            change_30d_formatted = safe_format(change_30d, format_change, "N/A     ")


                            add_terminal_output(f"{symbol:<8} | {mc_formatted:<8} | {ratio_formatted:<7} | {score_formatted:<6} | {zone_formatted:<10} | {vol_formatted:<8} | {change_24h_formatted:<8} | {change_7d_formatted:<8} | {change_30d_formatted:<8}", "success")

                        add_terminal_output("═" * 80, "info")
                        add_terminal_output(f"📊 {len(df_updated)} moedas atualizadas!", "success")

                    except Exception as e:
                        add_terminal_output(f"❌ Erro ao atualizar: {str(e)}", "error")
                    finally:
                        # Resetar estado de atualização
                        st.session_state.updating_watchlist = False
                        st.session_state.update_progress = 1.0
                        st.rerun()
                else:
                    add_terminal_output("⚠️ Watchlist vazia!", "warning")
                    st.session_state.updating_watchlist = False
            else:
                pass  # Não mostrar mensagem se arquivo não existe

    with col_term3:
        if st.button("🗑️ Limpar Terminal", key="clear_terminal"):
            st.session_state.terminal_output = []
            st.rerun()

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

    # --- NOVA LÓGICA ALINHADA AO VISUALIZER ---
    acao_sugerida = "AGUARDANDO PONTO"
    acao_cor = "#c9d1d9" # Cor padrão (branco/cinza)

    # 1. Trava de Capitulação (Prioridade Máxima)
    if macro_data.get('capitulation_lock'):
        acao_sugerida = "🚫 COMPRAS EM PAUSA"
        acao_cor = "#ff4500" # Laranja escuro

    # 2. Regime de Compra
    elif macro_data.get('status') == "COMPRA":
        if macro_data.get('buy_trigger'):
            acao_sugerida = "✅ COMPRA ATIVA"
            acao_cor = "#3fb950" # Verde
        elif macro_data.get('others_val', 0) < 0.2:
            acao_sugerida = "PONTO DE ACUMULAÇÃO"
            acao_cor = "#58a6ff" # Azul claro

    # 3. Regime de Venda (Lapidado)
    elif macro_data.get('status') == "VENDA":
        if macro_data.get('sell_trigger'):
            acao_sugerida = "🟥 ALERTA DE SAÍDA"
            acao_cor = "#f85149" # Vermelho
        else:
            acao_sugerida = "AGUARDANDO AÇÃO"
            acao_cor = "#c9d1d9" # Cinza

    # 4. Sobrescrita: Repique Tático (Se não houver capitulação)
    if macro_data.get('rebound') and not macro_data.get('capitulation_lock'):
        acao_sugerida = "🔵 REPIQUE TÁTICO"
        acao_cor = "#3498db" # Azul vibrante

    st.markdown("### 🎯 Ação Sugerida")
    st.markdown(f"""
        <div style="background-color: #1c2128; padding: 15px; border-radius: 8px; border: 1px solid #30363d;">
            <h4 style="margin:0; color: {acao_cor};">— {acao_sugerida}</h4>
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
            run_command_with_terminal(
                [sys.executable, "gems_finder.py"],
                "Executando busca de gems no mercado..."
            )
    with c_cmd2:
        if st.button("🕒 Atualizar Macro"):
            run_command_with_terminal(
                [sys.executable, "-c", "import visualizer; visualizer._build_macro_timing()"],
                "Atualizando dados macro timing..."
            )

# FUNÇÃO DO HEATMAP INSTITUCIONAL
def plot_institucional_chart():
    """
    Heatmap Institucional - BTC Price + Funding Rate + Macro Regime
    Usa dados reais do sistema
    """
    try:
        # 1. Carregar dados de Funding Rate
        funding_path = "data/macro/funding_rate_history.csv"
        if not os.path.exists(funding_path):
            st.warning("❌ Sem dados de funding rate históricos")
            return

        df_funding = pd.read_csv(funding_path)
        # Corrigir formato de data - handle diferentes formatos
        df_funding['timestamp'] = pd.to_datetime(df_funding['timestamp'], format='mixed')

        # Informar sobre quantidade de dados
        st.info(f"📊 Dados de Funding: {len(df_funding)} registros (de {df_funding['timestamp'].min().strftime('%d/%m %H:%M')} a {df_funding['timestamp'].max().strftime('%d/%m %H:%M')})")


        # 2. Obter dados do USDT.D semanal com BB%B
        try:
            st.info("🔄 Obtendo dados do USDT.D semanal...")
            tv = TvDatafeed()
            usdt_weekly = tv.get_hist(symbol='USDT.D', exchange='CRYPTOCAP', interval=Interval.in_weekly, n_bars=200)

            if usdt_weekly is None or usdt_weekly.empty:
                st.error("❌ Não foi possível obter dados do USDT.D")
                return

            # Calcular BB%B
            def _bb_percent(series: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.Series:
                ma = series.rolling(period).mean()
                sd = series.rolling(period).std(ddof=0)
                return (series - (ma - std_mult * sd)) / ((ma + std_mult * sd) - (ma - std_mult * sd))

            usdt_bbp = _bb_percent(usdt_weekly['close'], 20, 2.0).dropna()

            st.success("✅ Dados do USDT.D obtidos com sucesso")

        except Exception as e:
            st.error(f"❌ Erro ao obter dados do USDT.D: {e}")
            st.info("💡 Execute 'Atualizar Macro' para renovar a conexão")
            return

        # 3. Carregar dados macro para regime
        macro_data = visualizer._load_macro_timing()
        if not macro_data:
            st.warning("❌ Sem dados macro")
            return

        regime = macro_data.get('regime', {})
        buy_mode = regime.get('buy_mode', False)
        sell_mode = regime.get('sell_mode', False)

        # 4. Criar figura com 3 subplots (USDT.D, BB%B, Funding Rate)
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.4, 0.3, 0.3],
            subplot_titles=["USDT.D - Domínio do Mercado", "USDT.D - BB%B (Bollinger Bands Percent)", "Funding Rate - Histórico"]
        )

        # 5. Gráfico do USDT.D
        fig.add_trace(
            go.Scatter(
                x=usdt_weekly.index,
                y=usdt_weekly['close'],
                mode='lines',
                name='USDT.D',
                line=dict(color='#ffa500', width=2)
            ),
            row=1, col=1
        )

        # 6. Gráfico do BB%B do USDT.D com áreas coloridas
        fig.add_trace(
            go.Scatter(
                x=usdt_bbp.index,
                y=usdt_bbp,
                mode='lines',
                name='BB%B',
                line=dict(color='#00ffff', width=2)
            ),
            row=2, col=1
        )

        # 7. Linhas de referência no BB%B
        fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.8, row=2, col=1)
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.8, row=2, col=1)
        fig.add_hline(y=1, line_dash="dash", line_color="green", opacity=0.8, row=2, col=1)

        # 8. Definir regime label (sem fundo colorido)
        if buy_mode:
            regime_label = "🟩 REGIME: COMPRA (Bear Market)"
        elif sell_mode:
            regime_label = "🟥 REGIME: VENDA (Bull Market)"
        else:
            regime_label = "⬜ REGIME: NEUTRO"

        # 9. Gráfico de Barras do Funding Rate com fundo conectado
        colors = ['green' if val < 0 else 'red' for val in df_funding['funding_rate']]

        # Adicionar informações adicionais no hover
        hover_text = [
            f"Data: {ts.strftime('%d/%m %H:%M')}<br>Funding: {rate:.4f}%<br>Status: {'🟢 Oportunidade' if rate < 0 else '🔴 Alavancado'}"
            for ts, rate in zip(df_funding['timestamp'], df_funding['funding_rate'])
        ]

        # Adicionar área de fundo conectando as barras
        fig.add_trace(
            go.Scatter(
                x=df_funding['timestamp'],
                y=df_funding['funding_rate'],
                mode='lines',
                name='Funding Background',
                line=dict(color='rgba(128, 128, 128, 0.3)', width=1),
                fill='tozeroy',
                fillcolor='rgba(128, 128, 128, 0.2)',
                hoverinfo='skip'
            ),
            row=3, col=1
        )

        # Barras principais
        fig.add_trace(
            go.Bar(
                x=df_funding['timestamp'],
                y=df_funding['funding_rate'],
                marker_color=colors,
                name='Funding Rate',
                opacity=0.9,
                text=hover_text,
                hoverinfo='text',
                textposition='outside',
                width=7200000,  # 2 horas em milissegundos para barras mais compridas
                showlegend=True
            ),
            row=3, col=1
        )

        # 10. Linha de referência no funding
        fig.add_hline(y=0.08, line_dash="dash", line_color="red", opacity=0.8, row=3, col=1)

        # 8. Layout profissional
        fig.update_layout(
            title={
                'text': f"🏛️ MESA DE OPERAÇÕES INSTITUCIONAL | {regime_label}",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': 'white'}
            },
            template="plotly_dark",
            height=800,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            bargap=0.1,
            barmode='relative'
        )

        # 10. Configurar eixos
        fig.update_xaxes(title_text="Data", row=3, col=1)
        fig.update_yaxes(title_text="USDT.D (%)", row=1, col=1)
        fig.update_yaxes(title_text="BB%B (0-1)", row=2, col=1)
        fig.update_yaxes(title_text="Funding Rate (%)", row=3, col=1, range=[-0.02, 0.10])


        # 11. Exibir no Streamlit
        st.plotly_chart(fig, width='stretch')

        # 12. Informações adicionais
        with st.expander("📊 Análise do Heatmap"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "� USDT.D Atual",
                    f"{usdt_weekly['close'].iloc[-1]:.2f}%",
                    f"{((usdt_weekly['close'].iloc[-1] / usdt_weekly['close'].iloc[-2]) - 1) * 100:+.2f}%"
                )

            with col2:
                st.metric(
                    "💰 Funding Rate Atual",
                    f"{df_funding['funding_rate'].iloc[-1]:.4f}%",
                    "Negativo = Oportunidade" if df_funding['funding_rate'].iloc[-1] < 0 else "Positivo = Alavancado"
                )

            with col3:
                st.metric(
                    "📈 BB%B Atual",
                    f"{usdt_bbp.iloc[-1]:.4f}",
                    "Zona de Compra" if usdt_bbp.iloc[-1] < 0.2 else "Zona de Venda" if usdt_bbp.iloc[-1] > 0.8 else "Neutro"
                )

        # Métrica adicional do Regime
        st.markdown("---")
        col_regime = st.columns(1)[0]
        with col_regime:
            st.metric(
                "🎯 Regime Macro",
                regime_label.split(":")[1].strip(),
                "Foco em Compras" if buy_mode else "Cuidado com Vendas" if sell_mode else "Aguardando"
            )

        st.success("✅ Heatmap Institucional carregado com dados reais!")

    except Exception as e:
        st.error(f"❌ Erro ao gerar heatmap: {e}")
        st.write("Verifique se os dados de funding e macro estão atualizados.")

# TABELAS ADICIONAIS
st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📁 Database de Arquivos", "📖 Guia do Sistema", "🏛️ Heatmap Institucional", "📌 Watchlist"])
with tab1:
    st.write("Lista completa de snapshots disponíveis:")
    for snap in snapshots_list: st.text(f"• {os.path.basename(snap)}")
with tab2:
    st.info("O sistema analisa o BB%B mensal do USDT.D para definir o Regime Macro e cruza com a Funding Rate para o Super Alerta.")
with tab3:
    st.markdown("### 🏛️ Mesa de Operações Institucional")
    st.markdown("Análise visual combinando preço do USDT.D, BB%B, funding rate e regime macro do sistema.")
    plot_institucional_chart()
with tab4:
    st.markdown("### 📌 MINHA WATCHLIST")

    # Dataframe atualizado sempre que vem do gems_finder.py
    if snapshots_list:
        latest = snapshots_list[0]
        df = pd.read_csv(latest)
        df.columns = [c.strip().lower() for c in df.columns]

        st.markdown("**📊 Selecione as moedas para adicionar à Watchlist:**")

        # Preparar dataframe com colunas principais
        df_display = df.head(20).copy()

        # Adicionar coluna de seleção
        if 'total_volume' in df_display.columns and 'market_cap' in df_display.columns:
            df_display['Ratio'] = (df_display['total_volume'] / df_display['market_cap']).round(2)

        # Selecionar colunas para exibir
        display_cols = ['symbol', 'name']
        if 'market_cap' in df_display.columns:
            display_cols.append('market_cap')
        if 'total_volume' in df_display.columns:
            display_cols.append('total_volume')
        if 'Ratio' in df_display.columns:
            display_cols.append('Ratio')
        if 'final_score' in df_display.columns:
            display_cols.append('final_score')
        if 'momentum' in df_display.columns:
            display_cols.append('momentum')

        # Adicionar coluna de seleção com checkboxes
        df_display['Selecionar'] = False

        # Exibir dataframe com checkboxes
        selected_rows = []
        for i, row in df_display.iterrows():
            symbol = row.get('symbol', '')
            name = row.get('name', '')
            ratio = row.get('Ratio', 0)
            score = row.get('final_score', 0)

            # Dados de movimento
            price_change_24h = row.get('price_change_percentage_24h', 0)
            price_change_7d = row.get('price_change_percentage_7d_in_currency', 0)
            price_change_30d = row.get('price_change_percentage_30d_in_currency', 0)

            # Zone, volume e market cap
            zone = row.get('zone', 'N/A')
            volume = row.get('total_volume', 0)
            market_cap = row.get('market_cap', 0)

            # Formatar valores
            volume_formatted = f"{volume/1000000:.1f}M" if volume > 1000000 else f"{volume/1000:.1f}K"
            market_cap_formatted = f"{market_cap/1000000:.1f}M" if market_cap > 1000000 else f"{market_cap/1000:.1f}K"

            # Formatar porcentagens
            change_24h_str = f"{price_change_24h:+.2f}%" if price_change_24h != 0 else "0.00%"
            change_7d_str = f"{price_change_7d:+.2f}%" if price_change_7d != 0 else "N/A"
            change_30d_str = f"{price_change_30d:+.2f}%" if price_change_30d != 0 else "N/A"

            # Cor para 24h
            color_24h = "🟢" if price_change_24h > 0 else "🔴" if price_change_24h < 0 else "⚪"

            col_check, col_info = st.columns([1, 5])

            with col_check:
                selected = st.checkbox(f"**{symbol}**", key=f"select_{symbol}")
                if selected:
                    selected_rows.append(row)

            with col_info:
                # Montar string de informações
                info_parts = [
                    f"**{name[:30]}** ({market_cap_formatted})",
                    f"Ratio: {ratio:.2f}",
                    f"Score: {score:.1f}",
                    f"Zone: {zone}",
                    f"Vol: {volume_formatted}",
                    f"24h: {color_24h} {change_24h_str}"
                ]

                # Adicionar 7d e 30d se existirem
                if price_change_7d != 0:
                    info_parts.append(f"7d: {change_7d_str}")
                if price_change_30d != 0:
                    info_parts.append(f"30d: {change_30d_str}")

                st.markdown(" | ".join(info_parts))

        st.markdown("---")

        # Botões de gestão
        col_save, col_manage = st.columns([1, 1])

        with col_save:
            if st.button("💾 SALVAR SELEÇÃO EM CSV", type="primary"):
                if selected_rows:
                    # Salvar moedas selecionadas em CSV
                    watchlist_file = os.path.join("data", "watchlist_selecionada.csv")
                    os.makedirs(os.path.dirname(watchlist_file), exist_ok=True)

                    df_selected = pd.DataFrame(selected_rows)

                    # Verificar se já existe watchlist para adicionar em vez de sobreescrever
                    if os.path.exists(watchlist_file):
                        try:
                            df_existing = pd.read_csv(watchlist_file)
                            # Remover duplicatas pelos símbolos das novas seleções
                            new_symbols = [row.get('symbol', '') for row in selected_rows]
                            df_filtered = df_existing[~df_existing['symbol'].isin(new_symbols)]
                            # Combinar watchlist existente com novas seleções
                            df_final = pd.concat([df_filtered, df_selected], ignore_index=True)
                        except:
                            df_final = df_selected
                    else:
                        df_final = df_selected

                    df_final.to_csv(watchlist_file, index=False)

                    symbols = [row.get('symbol', '') for row in selected_rows]
                    st.success(f"✅ Adicionadas {len(selected_rows)} moedas à watchlist: {', '.join(symbols)}")
                else:
                    st.warning("⚠️ Selecione pelo menos uma moeda para salvar!")

        with col_manage:
            if st.button("🗑️ GERENCIAR WATCHLIST", type="secondary"):
                st.session_state.show_manage = not st.session_state.get('show_manage', False)
                st.rerun()

    # Área de gestão da watchlist
    if st.session_state.get('show_manage', False):
        st.markdown("---")
        st.markdown("### 🗑️ GERENCIAR WATCHLIST")

        # Carregar watchlist atual
        if os.path.exists("data/watchlist_selecionada.csv"):
            df_current = pd.read_csv("data/watchlist_selecionada.csv")

            if not df_current.empty:
                st.markdown("**📋 Watchlist atual:**")

                # Opção 1: Excluir por seleção
                st.markdown("**🔧 Excluir por seleção:**")
                symbols_to_remove = []
                for _, row in df_current.iterrows():
                    symbol = row.get('symbol', '')
                    name = row.get('name', '')
                    if st.checkbox(f"❌ {symbol} - {name[:30]}", key=f"remove_{symbol}"):
                        symbols_to_remove.append(symbol)

                # Opção 2: Excluir por nome digitado
                st.markdown("**✍️ Excluir por nome (separado por vírgula):**")
                symbols_input = st.text_input("Digite os symbols para excluir:", placeholder="BTC, ETH, DOGE")

                col_remove1, col_remove2 = st.columns(2)
                with col_remove1:
                    if st.button("🗑️ EXCLUIR SELECIONADOS", type="primary"):
                        all_to_remove = list(set(symbols_to_remove))
                        if all_to_remove:
                            # Remover do CSV
                            df_filtered = df_current[~df_current['symbol'].isin(all_to_remove)]
                            df_filtered.to_csv("data/watchlist_selecionada.csv", index=False)
                            st.success(f"✅ Removidas {len(all_to_remove)} moedas: {', '.join(all_to_remove)}")
                            st.session_state.show_manage = False
                            st.rerun()
                        else:
                            st.warning("⚠️ Nenhuma moeda selecionada para remover!")

                with col_remove2:
                    if st.button("🗑️ EXCLUIR POR NOME", type="primary"):
                        if symbols_input:
                            input_symbols = [s.strip().upper() for s in symbols_input.split(',')]
                            # Verificar quais existem na watchlist
                            existing_symbols = df_current['symbol'].str.upper().tolist()
                            to_remove = [s for s in input_symbols if s in existing_symbols]

                            if to_remove:
                                # Remover do CSV
                                df_filtered = df_current[~df_current['symbol'].str.upper().isin(to_remove)]
                                df_filtered.to_csv("data/watchlist_selecionada.csv", index=False)
                                st.success(f"✅ Removidas {len(to_remove)} moedas: {', '.join(to_remove)}")
                                st.session_state.show_manage = False
                                st.rerun()
                            else:
                                st.warning(f"⚠️ Nenhuma moeda encontrada: {symbols_input}")
                        else:
                            st.warning("⚠️ Digite pelo menos um symbol!")

                # Botão para limpar tudo
                if st.button("🧹 LIMPAR WATCHLIST INTEIRA", type="secondary"):
                    df_empty = pd.DataFrame()
                    df_empty.to_csv("data/watchlist_selecionada.csv", index=False)
                    st.success("✅ Watchlist limpa completamente!")
                    st.session_state.show_manage = False
                    st.rerun()
            else:
                st.info("📌 Watchlist vazia!")
        else:
            st.warning("⚠️ Watchlist não encontrada! Adicione moedas primeiro.")
    else:
        st.warning("⚠️ Execute o Gems Finder para carregar os dados mais recentes!")

# RODAPÉ
st.markdown("<br><p style='text-align: center; color: #484f58; font-size: 12px;'>Montrezor Analysis System | Powered by Data 💎</p>", unsafe_allow_html=True)
