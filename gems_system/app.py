import sys
import io
import streamlit as st
import pandas as pd
import os
import glob
import json
import subprocess
import requests
from collections import Counter
from datetime import datetime
import sys
import webbrowser
import time
from utils import get_exhaustion_status
from streamlit_autorefresh import st_autorefresh


# Importações para o Heatmap
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tvDatafeed import TvDatafeed, Interval
from subprocess import Popen, DEVNULL

# Importa as bibliotecas do sistema
import visualizer

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
try:
    from portfolio_tab import render_portfolio_tab
    _PORT_AVAILABLE = True
except ImportError:
    _PORT_AVAILABLE = False

try:
    import gems_ai_filter as _ai
    try:
        from ml_ranker import get_current_model_info
        _ML_AVAILABLE = True
    except ImportError:
        _ML_AVAILABLE = False
        def get_current_model_info():
            return None
    _AI_AVAILABLE = True
except ImportError:
    _AI_AVAILABLE = False
    def get_current_model_info():
        return None

try:
    from montrezor_alerts_integration import send_gems_alert, log_signal
except ImportError:
    def send_gems_alert(*args, **kwargs):
        return False

    def log_signal(*args, **kwargs):
        return None


def _macro_gems_signal_type(m):
    """Tipo de alerta Gems derivado do macro (mesma hierarquia do HUD)."""
    if m.get("super_alert") == "SUPER_BUY":
        return "SUPER_BUY"
    if m.get("super_alert") == "SUPER_SELL":
        return "SUPER_SELL"
    if m.get("rebound_super") and not m.get("capitulation_lock") and m.get("status") == "VENDA":
        return "SUPER_REPIQUE"
    if m.get("rebound") and not m.get("capitulation_lock") and m.get("status") == "VENDA":
        return "REPIQUE"
    if m.get("funding_signal") == "BUY":
        return "BUY"
    if m.get("funding_signal") == "SELL":
        return "SELL"
    return None


def maybe_telegram_macro_gems(m):
    """
    Telegram + log unificado quando o sinal macro muda.
    Evita repetir envio a cada rerun do Streamlit (só em transição de estado).
    """
    sig = _macro_gems_signal_type(m)
    if sig is None:
        st.session_state["gems_macro_telegram_last"] = None
        return
    if sig == st.session_state.get("gems_macro_telegram_last"):
        return
    fr = float(m.get("funding_rate") or 0)
    try:
        send_gems_alert("BTC", sig, market_cap=0, funding_rate=fr)
        log_signal(
            "GEMS",
            "BTC",
            {
                "type": sig,
                "funding_rate": fr,
                "macro_status": m.get("status"),
                "super_alert": m.get("super_alert"),
                "funding_signal": m.get("funding_signal"),
                "rebound": m.get("rebound"),
                "rebound_super": m.get("rebound_super"),
            },
        )
    except Exception:
        pass
    st.session_state["gems_macro_telegram_last"] = sig

# --- ADIÇÃO: NAVEGAÇÃO AUTOMÁTICA ---
with st.sidebar:
    st.markdown("### 🧭 Central de Controle")
    st.markdown("**💎 Mesa de Operações** (página atual)")
    st.markdown("---")

    st.markdown("### 📈 Trading System")

    # Botão para abrir automaticamente
    if st.button("🚀 Abrir Trading System", type="primary", width='stretch'):
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
                stdout=subprocess.DEVNULL,  # 🟢 MODIFICADO AQUI
                stderr=subprocess.DEVNULL   # 🟢 MODIFICADO AQUI
            )

            # Esperar o Streamlit abrir automaticamente
            time.sleep(3)

            st.success("✅ Trading System iniciado em http://localhost:8502")
            st.info("🌐 Sistema aberto automaticamente pelo Streamlit!")

        except Exception as e:
            st.error(f"❌ Erro: {e}")
            st.code(f"Python: {sys.executable}")
            st.code(f"Arquivo: {trading_file}")

    st.markdown("*Clique para abrir automaticamente*")
    st.markdown("---")

    st.markdown("### 📊 Market Analysis")

    # Botão para abrir automaticamente
    if st.button("📈 Abrir Market Analysis", type="primary", width='stretch'):
        try:
            st.info("🔄 Iniciando Market Analysis...")

            # Caminhos relativos genéricos
            current_dir = os.getcwd()
            market_dir = os.path.abspath(os.path.join(current_dir, "..", "analysis_system"))
            market_file = os.path.join(market_dir, "market_analysis_app.py")

            # Verificar se arquivo existe
            if not os.path.exists(market_file):
                st.error(f"❌ Arquivo não encontrado: {market_file}")
                st.stop()

            # Executar em background sem shell
            process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", market_file, "--server.port", "8503"],
                cwd=market_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Esperar o Streamlit abrir automaticamente
            time.sleep(3)

            st.success("✅ Market Analysis iniciado em http://localhost:8503")
            st.info("🌐 Sistema aberto automaticamente pelo Streamlit!")

        except Exception as e:
            st.error(f"❌ Erro: {e}")
            st.code(f"Python: {sys.executable}")
            st.code(f"Arquivo: {market_file}")

    st.markdown("*Clique para abrir automaticamente*")
    st.markdown("---")
# --- FIM DA ADIÇÃO ---

# Título principal no topo
st.title("Montrezor Financial Hub")
st.markdown("<p style='color: #8b949e; margin-top: -15px; margin-bottom: 30px;'>Plataforma integrada de análise, operação e gestão de mercado</p>", unsafe_allow_html=True)

# Terminal session state e funções
if 'terminal_output' not in st.session_state:
    st.session_state.terminal_output = []
if 'gems_macro_telegram_last' not in st.session_state:
    st.session_state.gems_macro_telegram_last = None

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

def run_command_with_terminal(command, description="Executando comando..."):
    """Executa comando assíncrono e redireciona para arquivo de log"""
    import subprocess
    import sys
    from datetime import datetime

    # Criar arquivo de log único
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"data/terminal_logs/command_{timestamp}.txt"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    add_terminal_output(f"🚀 {description}", "info")
    add_terminal_output(f"💻 Comando: {' '.join(command) if isinstance(command, list) else command}", "info")
    add_terminal_output(f"📝 Log: {log_file}", "info")
    add_terminal_output("─" * 80, "info")

    try:
        # Redirecionar saída para arquivo de forma assíncrona
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== {description} ===\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Comando: {' '.join(command) if isinstance(command, list) else command}\n")
            f.write("=" * 80 + "\n\n")

        # Iniciar processo em background
        process = subprocess.Popen(
            command if isinstance(command, list) else command.split(),
            stdout=open(log_file, 'a', encoding='utf-8'),
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        # Salvar PID para controle
        with open(f"data/terminal_logs/active_processes.json", 'a', encoding='utf-8') as f:
            import json
            json.dump({
                "pid": process.pid,
                "command": ' '.join(command) if isinstance(command, list) else command,
                "log_file": log_file,
                "timestamp": datetime.now().isoformat(),
                "description": description
            }, f)
            f.write('\n')

        add_terminal_output(f"🔄 Processo iniciado em background (PID: {process.pid})", "success")
        add_terminal_output(f"⏱️ Use o refresh automático para acompanhar a execução", "info")

        return process.pid

    except Exception as e:
        add_terminal_output(f"Erro ao iniciar processo: {str(e)}", "error")
        return None

def read_terminal_logs(log_file, max_lines=100):
    """Lê as últimas linhas do arquivo de log"""
    try:
        if not os.path.exists(log_file):
            return [("error", " Arquivo de log não encontrado...")]

        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Se max_lines for None, ler o arquivo completo
        if max_lines is None:
            recent_lines = lines
        else:
            # Pegar últimas max_lines linhas
            recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

        # Processar cores
        processed_lines = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue

            # Manter formatação de cores baseada no conteúdo
            if "✅" in line or "success" in line.lower():
                processed_lines.append(("success", line))
            elif "❌" in line or "error" in line.lower() or "failed" in line.lower():
                processed_lines.append(("error", line))
            elif "⚠️" in line or "warning" in line.lower():
                processed_lines.append(("warning", line))
            else:
                processed_lines.append(("info", line))

        return processed_lines

    except Exception as e:
        return [("error", f"Erro ao ler log: {str(e)}")]

def get_active_logs():
    """Retorna lista de arquivos de log ativos"""
    import glob
    log_pattern = "data/terminal_logs/command_*.txt"
    log_files = glob.glob(log_pattern)

    # Ordenar por data de modificação (mais recentes primeiro)
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    return log_files[:10]  # Últimos 10 logs

# 2. CSS PARA DESIGN DE ALTA PERFORMANCE E HUD
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
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 98%; }

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
        padding-top: 4rem;
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

    /* Novos estilos para AI Gems Filter */
    .pick-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 14px; position: relative; overflow: hidden; margin-bottom: 12px; }
    .pick-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; }
    .pick-card .rank { font-size: 20px; font-weight: 500; margin-bottom: 2px; }
    .pick-card .symbol { font-size: 18px; font-weight: 500; }
    .pick-card .potential { font-size: 12px; font-weight: 500; margin: 6px 0; color: #ef9f27; }
    .pick-card .rationale { font-size: 12px; color: #8b949e; line-height: 1.5; }
    .pick-card .flags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
    .pick-card .score { margin-top: 8px; font-size: 10px; color: #484f58; }
    .pick-card .ml { margin-top: 4px; font-size: 10px; color: #a371f7; }

    .flag { font-size: 10px; font-weight: 500; padding: 2px 6px; border-radius: 4px; background: #1c2128; color: #8b949e; border: 0.5px solid #30363d; }
    .flag-hot { background: #eeedfe; color: #534ab7; border-color: #afa9ec; }
    .flag-up { background: #e1f5ee; color: #0f6e56; border-color: #5dcaa5; }
    .flag-gold { background: #faeeda; color: #854f0b; border-color: #ef9f27; }

    .badge-ok { background: #e1f5ee; color: #0f6e56; display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 20px; font-size: 11px; }
    .badge-warn { background: #faeeda; color: #854f0b; display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 20px; font-size: 11px; }
    .badge-danger { background: #fcebeb; color: #a32d2d; }

    .macro-bar { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 12px 16px; margin-top: 20px; display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
    .macro-note { margin-top: 8px; background: #1c2128; border-left: 3px solid #378add; border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #8b949e; }
    .avoid-bar { margin-top: 8px; background: #2d0f0f; border: 1px solid #da3633; border-radius: 8px; padding: 8px 14px; font-size: 12px; display: flex; align-items: center; gap: 8px; }
    .avoid-pill { background: #f7c1c1; color: #791f1f; padding: 2px 8px; border-radius: 12px; font-size: 11px; }

    .cycle-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 12px 16px; }
    .progress-bar-bg { background: #0d1117; border-radius: 6px; height: 6px; margin: 8px 0; }
    .progress-fill { height: 6px; border-radius: 6px; }
    .metric-mini-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 150px; }
    </style>
    """, unsafe_allow_html=True)


def get_snapshots():
    path = os.path.join("data", "snapshots")
    if not os.path.exists(path): return []
    files = glob.glob(os.path.join(path, "*.csv"))
    return sorted(files, reverse=True)

@st.cache_data(ttl=visualizer.MACRO_TIMING_MAX_AGE_SEC)
def get_macro_data():
    path = os.path.join("data", "macro", "macro_timing.json")

    # Regenera JSON se generated_at estiver velho (mesmo critério que _load_macro_timing)
    try:
        visualizer._load_macro_timing()
    except Exception:
        pass

    res = {
        "status": "INDEFINIDO", "bb_value": 0.0, "others_val": 0.0, "usdtd_val": 0.0,
        "last_update": "N/A", "buy_trigger": False, "sell_trigger": False,
        "rebound": False, "rebound_super": False,
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
                res["capitulation_lock"] = regime.get("capitulation_lock", False)

                if buy_mode: res["status"] = "COMPRA"
                elif sell_mode: res["status"] = "VENDA"
                else: res["status"] = "NEUTRO"

                res["bb_value"] = data.get("monthly", {}).get("usdt_d_bbp", 0.0)
                res["others_val"] = data.get("weekly", {}).get("others_bbp", 0.0)
                res["usdtd_val"] = data.get("weekly", {}).get("usdt_d_bbp", 0.0)

                weekly_buy_trigger = signal.get("weekly_buy_trigger", False)
                weekly_sell_trigger = signal.get("weekly_sell_trigger", False)

                res["buy_trigger"] = weekly_buy_trigger
                res["sell_trigger"] = weekly_sell_trigger
                res["rebound"] = signal.get("tactical_rebound", False)
                res["rebound_super"] = signal.get("tactical_rebound_super", False)

                # Puxa o dado mastigado que o visualizer.py já salvou no JSON
                funding_rate = data.get("funding_rate", 0.01)
                res["funding_rate"] = funding_rate

                res["funding_signal"] = "NEUTRAL"
                res["super_alert"] = "OFF"

                # SUPER: regime + gatilho semanal + funding (confluência completa)
                # BUY/SELL (HUD / Telegram base): regime + weekly_* apenas (funding não exige)
                if buy_mode:
                    if weekly_buy_trigger and funding_rate < 0:
                        res["super_alert"] = "SUPER_BUY"
                    elif weekly_buy_trigger:
                        res["funding_signal"] = "BUY"
                elif sell_mode:
                    if weekly_sell_trigger and funding_rate > 0.08:
                        res["super_alert"] = "SUPER_SELL"
                    elif weekly_sell_trigger:
                        res["funding_signal"] = "SELL"

                gen_at = data.get("generated_at", "")
                if gen_at:
                    try:
                        res["last_update"] = datetime.fromisoformat(gen_at.replace("Z", "+00:00")).strftime('%d/%m %H:%M')
                    except:
                        res["last_update"] = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%m %H:%M')
        except: pass
    return res

@st.cache_data(ttl=900)  # 15 minutos para consistência e limite de requisições
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
    maybe_telegram_macro_gems(m)
    f_rate = m['funding_rate']
    f_color = "#3fb950" if f_rate < 0 else ("#f85149" if f_rate > 0.08 else "#8b949e")

    # Exibição do Alerta com hierarquia visual e classes do CSS
    super_html = ""
    if m['super_alert'] == "SUPER_BUY":
        super_html = '<div class="super-buy-alert">⚡ SUPER ALERTA: COMPRA</div>'
    elif m['super_alert'] == "SUPER_SELL":
        super_html = '<div class="super-sell-alert">🚨 SUPER ALERTA: VENDA</div>'
    elif m.get("rebound_super") and not m.get("capitulation_lock") and m.get("status") == "VENDA":
        super_html = (
            '<div class="neutral-alert" style="background:#6e40c9; border: 2px solid #a371f7; color: white;">'
            "⚡ SUPER REPIQUE (semanal + funding < 0)</div>"
        )
    elif m.get("rebound") and not m.get("capitulation_lock") and m.get("status") == "VENDA":
        super_html = (
            '<div class="neutral-alert" style="background:#1f6feb; border: 1px solid #58a6ff; color: white;">'
            "🔵 REPIQUE TÁTICO (regime venda + USDT.D sem. no topo)</div>"
        )
    elif m['funding_signal'] == "BUY":
        super_html = '<div class="neutral-alert" style="background:#238636; border: 1px solid #3fb950; color: white;">🟢 SINAL DE COMPRA (Semanal)</div>'
    elif m['funding_signal'] == "SELL":
        super_html = '<div class="neutral-alert" style="background:#da3633; border: 1px solid #f85149; color: white;">🔴 SINAL DE VENDA (Semanal)</div>'
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

st.code("Montrezor Central - Mesa de Operações", language=None)

# ── RESUMO DO PORTFÓLIO (topo da página, colapsável) ─────────────────────────
if "port_widget_open" not in st.session_state:
    st.session_state.port_widget_open = True

_btn_label = "▲ Ocultar Portfólio" if st.session_state.port_widget_open else "💼 Ver Portfólio"
if st.button(_btn_label, key="toggle_port_widget"):
    st.session_state.port_widget_open = not st.session_state.port_widget_open
    st.rerun()

if st.session_state.port_widget_open:
    try:
        import json, os
        _PF = os.path.join(os.path.expanduser("~"), ".montrezor_portfolio.json")
        _port_data = json.load(open(_PF, encoding="utf-8")) if os.path.exists(_PF) else {}
        _positions  = [p for p in _port_data.get("positions",[]) if p.get("status")=="OPEN"]
        _cash       = float(_port_data.get("cash_usd", 0.0))

        # Buscar preços atuais (cache de 60s já está no portfolio_tab)
        try:
            from portfolio_tab import _fetch_price, _calc_roe, _calc_pnl, _calc_liq_price, LIQ_WARN_PCT
            _enrich = True
        except ImportError:
            _enrich = False

        _total_margin = 0.0
        _total_pnl    = 0.0
        _pos_rows     = []
        for _p in _positions:
            _margin = float(_p.get("total_margin", 0))
            _total_margin += _margin
            if _enrich:
                _cg    = _fetch_price(_p["coin_id"])
                _px    = _cg.get("price", float(_p.get("entry_avg",0)))
                _roe   = _calc_roe(float(_p["entry_avg"]), _px, float(_p["leverage"]), _p.get("direction","LONG"))
                _pnl   = _calc_pnl(float(_p["entry_avg"]), _px, float(_p["position_size"]), _p.get("direction","LONG"))
                _liq   = _calc_liq_price(float(_p["entry_avg"]), float(_p["leverage"]), _p.get("direction","LONG"))
                _near  = (abs(_px - _liq) / _px) < LIQ_WARN_PCT if _px > 0 else False
                _total_pnl += _pnl
            else:
                _px = float(_p.get("entry_avg",0)); _roe = 0; _pnl = 0; _liq = 0; _near = False
            _pos_rows.append({"coin": _p["coin_id"].upper(), "px": _px, "roe": _roe,
                               "pnl": _pnl, "margin": _margin, "lev": _p.get("leverage",1),
                               "liq": _liq, "near_liq": _near, "exc": _p.get("exchange","")})

        _total_equity = _cash + _total_margin + _total_pnl

        # ── Cards de topo ──
        _pc1, _pc2, _pc3, _pc4 = st.columns(4)
        _pc1.metric("💵 Dolarizado", f"${_cash:,.2f}")
        _pc2.metric("📊 Investido", f"${_total_margin:,.2f}")
        _pc3.metric("📈 P&L Aberto", f"${_total_pnl:+,.2f}",
                    delta=f"{(_total_pnl/_total_margin*100) if _total_margin else 0:+.2f}%")
        _pc4.metric("🏦 Patrimônio", f"${_total_equity:,.2f}")

        # ── Cards de posições (linha horizontal) ──
        if _pos_rows:
            _cols = st.columns(min(len(_pos_rows), 4))
            for _ci, _row in enumerate(_pos_rows):
                with _cols[_ci % 4]:
                    _clr = "#3fb950" if _row["roe"] >= 0 else "#f85149"
                    _liq_html = (
                        "<div style='font-size:10px;color:#f85149;margin-top:4px'>🚨 ZONA LIQ.</div>"
                        if _row["near_liq"] else ""
                    )
                    st.markdown(
                        f"<div style='background:#161b22;border:1px solid "
                        f"{'#f85149' if _row['near_liq'] else '#30363d'};"
                        f"border-radius:8px;padding:10px 12px;'>"
                        f"<div style='font-size:13px;font-weight:700;color:#e6edf3;"
                        f"font-family:JetBrains Mono,monospace'>{_row['coin']}</div>"
                        f"<div style='font-size:11px;color:#8b949e;margin-bottom:4px'>"
                        f"{_row['exc']} · {_row['lev']}x</div>"
                        f"<div style='font-size:12px;color:#c9d1d9'>${_row['px']:,.4f}</div>"
                        f"<div style='font-size:14px;font-weight:700;color:{_clr}'>"
                        f"ROE {_row['roe']:+.2f}%</div>"
                        f"<div style='font-size:11px;color:{_clr}'>${_row['pnl']:+,.2f}</div>"
                        f"<div style='font-size:10px;color:#484f58;margin-top:2px'>"
                        f"Liq: ${_row['liq']:,.4f}</div>"
                        f"{_liq_html}</div>",
                        unsafe_allow_html=True)
        elif not _positions:
            st.markdown(
                "<div style='color:#484f58;font-size:12px;padding:4px 0'>"
                "Nenhuma posição aberta. Acesse a aba 💼 Portfólio para adicionar.</div>",
                unsafe_allow_html=True)

    except Exception as _e:
        st.markdown(
            f"<div style='color:#484f58;font-size:12px'>Portfólio: {_e}</div>",
            unsafe_allow_html=True)

st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)

# Terminal logo abaixo do título
with st.expander("🖥️ Terminal (Assíncrono - Auto Refresh)", expanded=True):
    # Configurar refresh automático a cada 1 minuto
    st_autorefresh(interval=120000, limit=None, key="terminal_refresh")

    # Aba para selecionar visualização
    tab1, tab2 = st.tabs(["📋 Logs Ativos", "🖥️ Terminal Principal"])

    with tab1:
        st.markdown("### 📝 Logs de Processos em Execução")

        # Obter logs ativos
        active_logs = get_active_logs()

        if active_logs:
            selected_log = st.selectbox(
                "Selecione um log para visualizar:",
                active_logs,
                format_func=lambda x: os.path.basename(x).replace('command_', '').replace('.txt', '')
            )

            if selected_log:
                # Opção para ver mais linhas do log
                col_view1, col_view2 = st.columns([2, 1])

                with col_view1:
                    view_mode = st.radio(
                        "🔍 Modo de Visualização:",
                        ["Últimas 100 linhas", "Últimas 500 linhas", "Log Completo"],
                        horizontal=True
                    )

                with col_view2:
                    if st.button("🔄 Atualizar Log"):
                        st.rerun()

                # Definir número de linhas baseado no modo
                max_lines = 100 if view_mode == "Últimas 100 linhas" else 500 if view_mode == "Últimas 500 linhas" else None

                # Ler linhas do log selecionado
                log_lines = read_terminal_logs(selected_log, max_lines=max_lines)

                # Obter informações do arquivo
                file_size = os.path.getsize(selected_log)
                file_size_mb = file_size / (1024 * 1024)

                # Contar linhas totais
                with open(selected_log, 'r', encoding='utf-8') as f:
                    total_lines = len(f.readlines())

                # Construir texto do log
                log_text = f"📄 {os.path.basename(selected_log)}\n"
                log_text += f"📊 Tamanho: {file_size_mb:.2f} MB | 🔢 Linhas totais: {total_lines}\n"
                log_text += f"👁️ Mostrando: {len(log_lines)} linhas ({'completo' if max_lines is None else f'últimas {max_lines}'})\n"
                log_text += "="*60 + "\n"

                for line_type, line_content in log_lines:
                    if isinstance(line_content, list):
                        for item in line_content:
                            log_text += f"{item}\n"
                    else:
                        # Adicionar cores baseadas no tipo
                        if line_type == "success":
                            log_text += f"✅ {line_content}\n"
                        elif line_type == "error":
                            log_text += f"❌ {line_content}\n"
                        elif line_type == "warning":
                            log_text += f"⚠️ {line_content}\n"
                        else:
                            log_text += f"ℹ️ {line_content}\n"

                st.code(log_text, language=None)

                # Botão para limpar logs antigos
                if st.button("🗑️ Limpar Logs Antigos", key="clean_logs"):
                    import glob
                    import shutil

                    log_dir = "data/terminal_logs"
                    old_logs = glob.glob(f"{log_dir}/command_*.txt")
                    old_logs.sort(key=lambda x: os.path.getmtime(x))

                    st.write(f"📊 Encontrados {len(old_logs)} logs no total:")

                    # Mostrar logs que serão mantidos vs removidos
                    if len(old_logs) > 5:
                        to_keep = old_logs[-5:]  # 5 mais recentes
                        to_remove = old_logs[:-5]  # mais antigos

                        st.write(f"✅ **Manter (5 mais recentes):**")
                        for log in to_keep:
                            st.write(f"   - {os.path.basename(log)} ({os.path.getsize(log)} bytes)")

                        st.write(f"🗑️ **Remover ({len(to_remove)} logs):**")
                        for log in to_remove:
                            st.write(f"   - {os.path.basename(log)} ({os.path.getsize(log)} bytes)")

                        # Confirmar remoção
                        if st.button("⚠️ Confirmar Remoção", key="confirm_remove"):
                            removed_count = 0
                            for old_log in to_remove:
                                try:
                                    if os.path.exists(old_log):
                                        os.remove(old_log)
                                        removed_count += 1
                                        st.write(f"   ✅ Removido: {os.path.basename(old_log)}")
                                    else:
                                        st.write(f"   ⚠️ Arquivo não encontrado: {old_log}")
                                except Exception as e:
                                    st.write(f"   ❌ Erro ao remover {old_log}: {str(e)}")

                            if removed_count > 0:
                                st.success(f"✅ {removed_count} logs antigos removidos com sucesso!")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.warning("⚠️ Nenhum log foi removido.")
                    else:
                        st.info(f"📝 Total de logs ({len(old_logs)}) é menor ou igual ao limite (5). Nada para remover.")
        else:
            st.info("📝 Nenhum log ativo encontrado. Execute um comando para gerar logs.")

    with tab2:
        # Terminal principal (mensagens do sistema)
        terminal_text = "🖥️ MONTREZOR TERMINAL\n" + "="*50 + "\n"

        for entry in st.session_state.terminal_output:
            terminal_text += f"[{entry['timestamp']}] {entry['message']}\n"

        st.code(terminal_text, language=None)

    # Botões do terminal
    col_term1, col_term2, col_term3 = st.columns([1, 1, 1])

    with col_term1:
        if st.button("📋 Mostrar Watchlist"):
            if os.path.exists("data/watchlist_selecionada.csv"):
                df_watchlist = pd.read_csv("data/watchlist_selecionada.csv")
                if not df_watchlist.empty:
                    add_terminal_output("📌 MINHA WATCHLIST ATUAL:", "info")
                    add_terminal_output("═" * 100, "info")
                    add_terminal_output(f"{'SYMBOL':<8} | {'MC':<8} | {'RATIO':<7} | {'SCORE':<6} | {'ZONE':<10} | {'STATUS':<12} | {'VOL':<8} | {'24H':<8} | {'7D':<8} | {'30D':<8} | {'DATA':<12}", "info")
                    add_terminal_output("-" * 100, "info")

                    for _, row in df_watchlist.iterrows():
                        symbol = str(row.get('symbol', '')).upper()
                        mc = row.get('market_cap', 0)
                        ratio = row.get('ratio', 0)
                        score = row.get('final_score', 0)
                        zone = row.get('zone', 'N/A')
                        status = get_exhaustion_status(row)  # Adicionar status
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

                        # Obter data de adição (se existir)
                        data_adicionada = row.get('data_adicionada', 'N/A')
                        if data_adicionada != 'N/A':
                            # Formatar data para MM-DD-AA
                            if isinstance(data_adicionada, str) and '-' in str(data_adicionada):
                                # Se for formato YYYY-MM-DD HH:MM ou YYYY-MM-DD
                                parts = str(data_adicionada).split('-')
                                if len(parts) >= 3:
                                    # Pegar ano (últimos 2 digits), mês e dia
                                    year_short = parts[0][-2:]  # Últimos 2 dígitos do ano
                                    day_part = parts[2].split(' ')[0]  # Pega só a parte do dia
                                    data_formatted = f"{parts[1]}-{day_part[:2]}-{year_short}"  # MM-DD-AA
                                elif len(parts) >= 2:
                                    data_formatted = f"{parts[1]}-??-??"  # MM-??-??
                                else:
                                    data_formatted = str(data_adicionada)[:8]
                            else:
                                data_formatted = str(data_adicionada)[:8]
                        else:
                            data_formatted = 'N/A'

                        add_terminal_output(f"{symbol:<8} | {mc_formatted:<8} | {ratio_formatted:<7} | {score_formatted:<6} | {zone_formatted:<10} | {status:<12} | {vol_formatted:<8} | {change_24h_formatted:<8} | {change_7d_formatted:<8} | {change_30d_formatted:<8} | {data_formatted:<12}", "success")

                    add_terminal_output("═" * 100, "info")
                    add_terminal_output(f"📊 Total: {len(df_watchlist)} moedas na watchlist", "success")
                else:
                    add_terminal_output("⚠️ Watchlist vazia!", "warning")
            else:
                pass  # Não mostrar mensagem se arquivo não existe

    with col_term2:
        # Verificar se há processo de atualização em andamento
        update_status_file = "data/watchlist_update_status.json"
        if os.path.exists(update_status_file):
            try:
                import json
                with open(update_status_file, 'r') as f:
                    status = json.load(f)

                if status.get('running', False):
                    st.info(f"🔄 Atualizando dados... {status.get('current_symbol', '')} ({status.get('progress', 0):.1%})")
                    st.progress(status.get('progress', 0))

                    # Mostrar últimas linhas do log
                    if os.path.exists("data/watchlist_update.log"):
                        with open("data/watchlist_update.log", 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if lines:
                                st.code("".join(lines[-5:]), language=None)
                else:
                    # Processo terminou, limpar status
                    if status.get('completed', False):
                        add_terminal_output("✅ Atualização em segundo plano concluída!", "success")
                        os.remove(update_status_file)
                        st.rerun()
            except:
                pass

        if st.button("🔄 ATUALIZAR DADOS DA WATCHLIST"):
            # Executar atualização em segundo plano
            if os.path.exists("data/watchlist_selecionada.csv"):
                df_watchlist = pd.read_csv("data/watchlist_selecionada.csv")
                if not df_watchlist.empty:
                    # Criar script de atualização
                    update_script = """
import sys
import os
import pandas as pd
import requests
import time
import json
from datetime import datetime

# Adicionar diretório atual ao path
sys.path.insert(0, os.getcwd())

def update_status(running, progress=0, current_symbol="", completed=False):
    status = {
        'running': running,
        'progress': progress,
        'current_symbol': current_symbol,
        'completed': completed,
        'last_update': datetime.now().isoformat()
    }
    with open("data/watchlist_update_status.json", 'w') as f:
        json.dump(status, f)

def add_terminal_output(message, msg_type="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open("data/watchlist_update.log", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\\n")

def update_watchlist():
    try:
        update_status(True, 0, "Iniciando...")
        add_terminal_output("🔄 ATUALIZANDO DADOS DA WATCHLIST...", "info")
        add_terminal_output("═" * 50, "info")

        df_watchlist = pd.read_csv("data/watchlist_selecionada.csv")
        symbols = df_watchlist['symbol'].tolist()
        add_terminal_output(f"📡 Buscando dados para {len(symbols)} moedas...", "info")

        updated_data = []
        add_terminal_output("🔄 Conectando à CoinGecko API...", "info")

        for i, symbol in enumerate(symbols, 1):
            try:
                progress = (i - 1) / len(symbols)
                update_status(True, progress, symbol.upper())

                add_terminal_output(f"📡 [{i}/{len(symbols)}] Buscando {symbol.upper()}...", "info")

                if i > 1:
                    time.sleep(5.0)

                # Busca inteligente
                try:
                    search_url = f"https://api.coingecko.com/api/v3/search?query={symbol.lower()}"
                    search_response = requests.get(search_url, timeout=10, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })

                    coin_id = None
                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        if search_data.get('coins') and len(search_data['coins']) > 0:
                            coin_id = search_data['coins'][0]['id']
                            add_terminal_output(f"   🔍 ID encontrado: {coin_id}", "info")

                    if coin_id:
                        endpoints = [
                            f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true&include_30d_change=true&include_market_cap=true&include_24hr_vol=true"
                        ]
                    else:
                        endpoints = [
                            f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}",
                            f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true&include_30d_change=true&include_market_cap=true&include_24hr_vol=true"
                        ]
                except:
                    endpoints = [
                        f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}",
                        f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true&include_30d_change=true&include_market_cap=true&include_24hr_vol=true"
                    ]

                data_found = False
                retry_count = 0
                max_retries = 50

                while not data_found and retry_count < max_retries:
                    retry_count += 1
                    add_terminal_output(f"   🔍 Tentativa {retry_count}/{max_retries} para {symbol.upper()}...", "info")

                    for j, endpoint_url in enumerate(endpoints, 1):
                        try:
                            if retry_count > 1:
                                delay = min(10, 2 + retry_count)
                                time.sleep(delay)

                            response = requests.get(endpoint_url, timeout=15, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            })

                            if response.status_code == 200:
                                data = response.json()
                                add_terminal_output(f"   ✅ Tentativa {retry_count} funcionou!", "success")

                                if 'simple' in endpoint_url:
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
                                    old_row = df_watchlist[df_watchlist['symbol'] == symbol].iloc[0]
                                    for col in ['ratio', 'final_score', 'momentum', 'zone', 'sector', 'accumulation_score', 'data_adicionada']:
                                        if col in old_row:
                                            current_data[col] = old_row[col]

                                    updated_data.append(current_data)
                                    add_terminal_output(f"✅ {symbol.upper()} - Dados atualizados em tempo real (tentativa {retry_count})", "success")
                                    break
                            elif response.status_code == 429:
                                add_terminal_output(f"   ⚠️ Rate limit, tentativa {retry_count}...", "warning")
                                continue
                            else:
                                add_terminal_output(f"   ❌ HTTP {response.status_code}, tentativa {retry_count}", "warning")

                        except Exception as e:
                            add_terminal_output(f"   ❌ Erro tentativa {retry_count}: {str(e)[:30]}", "warning")
                            continue

                    if data_found:
                        break

                if not data_found:
                    row = df_watchlist[df_watchlist['symbol'] == symbol].iloc[0]
                    updated_data.append(row)
                    add_terminal_output(f"⚠️ {symbol.upper()} - Usando dados cache (API indisponível)", "warning")

            except Exception as e:
                try:
                    row = df_watchlist[df_watchlist['symbol'] == symbol].iloc[0]
                    updated_data.append(row)
                    add_terminal_output(f"⚠️ {symbol.upper()} - Usando dados cache (Erro: {str(e)[:50]})", "warning")
                except:
                    add_terminal_output(f"❌ {symbol.upper()} - Erro ao processar", "error")

        # Atualizar CSV
        if updated_data:
            df_updated = pd.DataFrame(updated_data)
            df_updated.to_csv("data/watchlist_selecionada.csv", index=False)
            add_terminal_output("💾 Watchlist atualizada com dados frescos!", "success")

        add_terminal_output("═" * 80, "info")
        add_terminal_output(f"📊 {len(updated_data)} moedas atualizadas!", "success")
        add_terminal_output("✅ Processo concluído com sucesso!", "success")

        # Marcar como concluído
        update_status(False, 1.0, "Concluído", True)

    except Exception as e:
        add_terminal_output(f"❌ Erro ao atualizar: {str(e)}", "error")
        update_status(False, 0, f"Erro: {str(e)}", False)

if __name__ == "__main__":
    update_watchlist()
"""

                    # Salvar script temporário
                    with open("temp_watchlist_update.py", "w", encoding="utf-8") as f:
                        f.write(update_script)

                    # Limpar log anterior
                    if os.path.exists("data/watchlist_update.log"):
                        os.remove("data/watchlist_update.log")

                    # Executar em segundo plano
                    import subprocess
                    process = subprocess.Popen(
                        [sys.executable, "temp_watchlist_update.py"],
                        cwd=os.getcwd(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                    add_terminal_output(f"🚀 Atualização iniciada em segundo plano (PID: {process.pid})", "info")
                    add_terminal_output("📋 Acompanhe o progresso na interface ou no arquivo 'data/watchlist_update.log'", "info")
                    add_terminal_output("⏱️ O processo continuará rodando mesmo que você navegue por outras páginas", "info")
                    add_terminal_output("🔄 Auto-refresh configurado para 1 minuto", "info")

                    # Limpar script temporário após 1 segundo
                    import threading
                    def cleanup():
                        time.sleep(1)
                        try:
                            os.remove("temp_watchlist_update.py")
                        except:
                            pass

                    threading.Thread(target=cleanup, daemon=True).start()

                    # Forçar rerun para mostrar status imediatamente
                    st.rerun()

                else:
                    add_terminal_output("⚠️ Watchlist vazia!", "warning")
            else:
                add_terminal_output("⚠️ Arquivo watchlist_selecionada.csv não encontrado!", "warning")

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

    # 4. Sobrescrita: Super repique / repique (se não houver capitulação)
    if macro_data.get("rebound_super") and not macro_data.get("capitulation_lock"):
        acao_sugerida = "⚡ SUPER REPIQUE (funding < 0)"
        acao_cor = "#a371f7"
    elif macro_data.get("rebound") and not macro_data.get("capitulation_lock"):
        acao_sugerida = "🔵 REPIQUE TÁTICO (só semanal)"
        acao_cor = "#3498db"

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
            get_macro_data.clear()
            add_terminal_output("🔄 Dados macro atualizados — cache será renovado automaticamente.", "success")
            st.rerun()

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📁 Database de Arquivos", "📖 Guia do Sistema", "🏛️ Heatmap Institucional", "📌 Watchlist", "📡 Sinais", "💼 Portfólio", "🤖 AI Gems Filter"])
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
            status = get_exhaustion_status(row)  # Adicionar coluna Status
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
                selected = st.checkbox(f"**{symbol}**", key=f"select_{symbol}_{i}")
                if selected:
                    selected_rows.append(row)

            with col_info:
                # Montar string de informações
                info_parts = [
                    f"**{name[:30]}** ({market_cap_formatted})",
                    f"Ratio: {ratio:.2f}",
                    f"Score: {score:.1f}",
                    f"Zone: {zone}",
                    f"Status: {status}",
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

                    # Adicionar data de adição às novas seleções
                    from datetime import datetime
                    current_date = datetime.now().strftime('%Y-%m-%d %H:%M')

                    df_selected = pd.DataFrame(selected_rows)
                    df_selected['data_adicionada'] = current_date

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
                for idx, row in df_current.iterrows():
                    symbol = row.get('symbol', '')
                    name = row.get('name', '')
                    data_adicionada = row.get('data_adicionada', 'N/A')
                    if data_adicionada != 'N/A' and isinstance(data_adicionada, str) and '-' in str(data_adicionada):
                        # Formatar para MM-DD-AA
                        parts = str(data_adicionada).split('-')
                        if len(parts) >= 3:
                            # Pegar ano (últimos 2 digits), mês e dia
                            year_short = parts[0][-2:]  # Últimos 2 dígitos do ano
                            day_part = parts[2].split(' ')[0]  # Pega só a parte do dia
                            data_display = f" (adicionado: {parts[1]}-{day_part[:2]}-{year_short})"
                        elif len(parts) >= 2:
                            data_display = f" (adicionado: {parts[1]}-??-??)"
                        else:
                            data_display = f" (adicionado: {str(data_adicionada)[:8]})"
                    else:
                        data_display = ""
                    if st.checkbox(f"❌ {symbol} - {name[:30]}{data_display}", key=f"remove_{symbol}_{idx}"):
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

with tab5:
    st.markdown("### 📡 Guia de Sinais — Todos os Sistemas")
    st.markdown(
        "<p style='color:#8b949e;margin-top:-10px;margin-bottom:24px;font-size:13px;'>"
        "Referência completa da lógica de cada sinal emitido pelos três sistemas. "
        "Todas as condições são cumulativas na mesma hierarquia usada no código."
        "</p>",
        unsafe_allow_html=True
    )

    # ── 1. GEMS / MACRO (app.py) ──────────────────────────────────────
    st.markdown("#### 1 · Gems Finder — Sinais Macro (app.py)")
    st.markdown(
        "<p style='color:#8b949e;font-size:12px;margin-top:-8px;margin-bottom:12px;'>"
        "Fonte: USDT.D (Bollinger Band % mensal/semanal) + Others semanal + Funding Rate BTC. "
        "Avaliados em ordem de prioridade — o primeiro que bate é o sinal emitido."
        "</p>",
        unsafe_allow_html=True
    )
    st.markdown("""
<style>
.sig-table { width:100%; border-collapse:collapse; font-size:12px; margin-bottom:20px; }
.sig-table th { font-size:11px; font-weight:600; color:#8b949e; text-transform:uppercase;
                letter-spacing:.5px; padding:7px 12px; border-bottom:1px solid #30363d;
                text-align:left; background:#0d1117; }
.sig-table td { padding:8px 12px; border-bottom:1px solid #21262d; vertical-align:top; color:#c9d1d9; }
.sig-table tr:last-child td { border-bottom:none; }
.sig-table tr:hover td { background:#161b22; }
.badge { font-weight:600; padding:3px 9px; border-radius:4px; font-size:11px;
         white-space:nowrap; display:inline-block; }
.s-super-buy  { background:#0f2d1a; color:#3fb950; border:1px solid #238636; }
.s-super-sell { background:#2d0f0f; color:#f85149; border:1px solid #da3633; }
.s-buy        { background:#0a2a12; color:#56d364; border:1px solid #2ea043; }
.s-sell       { background:#2a0a0a; color:#ff7b72; border:1px solid #b62324; }
.s-repsuper   { background:#1a0a2d; color:#a371f7; border:1px solid #6e40c9; }
.s-repique    { background:#0a1a2d; color:#58a6ff; border:1px solid #1f6feb; }
.s-comum      { background:#1c2128; color:#8b949e; border:1px solid #30363d; }
.s-super      { background:#2d2200; color:#e3b341; border:1px solid #9e6a03; }
.pri { font-size:11px; color:#6e7681; font-weight:600; }
.cond-code { font-family:monospace; font-size:11px; background:#161b22;
             padding:2px 5px; border-radius:3px; color:#79c0ff; }
.fonte-txt { font-size:11px; color:#8b949e; }
</style>

<table class="sig-table">
  <thead>
    <tr>
      <th style="width:5%">#</th>
      <th style="width:14%">Sinal</th>
      <th style="width:36%">Condição (todas obrigatórias)</th>
      <th style="width:25%">Fonte dos dados</th>
      <th style="width:20%">O que significa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="pri">1º</td>
      <td><span class="badge s-super-buy">⚡ SUPER_BUY</span></td>
      <td>
        <span class="cond-code">buy_mode = True</span><br>
        <span class="cond-code">weekly_buy_trigger = True</span><br>
        <span class="cond-code">funding_rate &lt; 0</span>
      </td>
      <td class="fonte-txt">USDT.D BB%B mensal (baixo) + Others ou USDT.D semanal (toque) + Funding BTC negativo</td>
      <td class="fonte-txt">Confluência máxima de compra: regime macro favorável + gatilho semanal + mercado short demais (funding negativo = contrarian buy)</td>
    </tr>
    <tr>
      <td class="pri">2º</td>
      <td><span class="badge s-super-sell">🚨 SUPER_SELL</span></td>
      <td>
        <span class="cond-code">sell_mode = True</span><br>
        <span class="cond-code">weekly_sell_trigger = True</span><br>
        <span class="cond-code">funding_rate &gt; 0.08%</span>
      </td>
      <td class="fonte-txt">USDT.D BB%B mensal (alto) + Others ou USDT.D semanal (toque) + Funding BTC excessivo</td>
      <td class="fonte-txt">Confluência máxima de venda: regime macro defensivo + gatilho semanal + mercado long demais (funding alto = sobrecompra alavancada)</td>
    </tr>
    <tr>
      <td class="pri">3º</td>
      <td><span class="badge s-buy">🟢 BUY</span></td>
      <td>
        <span class="cond-code">buy_mode = True</span><br>
        <span class="cond-code">weekly_buy_trigger = True</span><br>
        <span style="font-size:11px;color:#6e7681;">(funding não exigido)</span>
      </td>
      <td class="fonte-txt">USDT.D BB%B mensal (baixo) + Others ou USDT.D semanal (toque)</td>
      <td class="fonte-txt">Regime favorável + gatilho semanal confirmado. Funding não confirmou ainda — sinal forte mas sem a terceira confluência</td>
    </tr>
    <tr>
      <td class="pri">4º</td>
      <td><span class="badge s-sell">🔴 SELL</span></td>
      <td>
        <span class="cond-code">sell_mode = True</span><br>
        <span class="cond-code">weekly_sell_trigger = True</span><br>
        <span style="font-size:11px;color:#6e7681;">(funding não exigido)</span>
      </td>
      <td class="fonte-txt">USDT.D BB%B mensal (alto) + Others ou USDT.D semanal (toque)</td>
      <td class="fonte-txt">Regime defensivo + gatilho semanal. Funding ainda não está excessivo — sinal de atenção</td>
    </tr>
    <tr>
      <td class="pri">5º</td>
      <td><span class="badge s-repsuper">⚡ SUPER_REPIQUE</span></td>
      <td>
        <span class="cond-code">rebound_super = True</span><br>
        <span class="cond-code">capitulation_lock = False</span><br>
        <span class="cond-code">status = "VENDA"</span><br>
        <span class="cond-code">funding_rate &lt; 0</span>
      </td>
      <td class="fonte-txt">Derivado do regime — USDT.D semanal no topo + funding negativo dentro de regime de venda</td>
      <td class="fonte-txt">Repique técnico com força extra: mercado em regime de venda mas com funding negativo indicando posicionamento contrarian. Movimento de recuperação tático com maior potencial</td>
    </tr>
    <tr>
      <td class="pri">6º</td>
      <td><span class="badge s-repique">🔵 REPIQUE</span></td>
      <td>
        <span class="cond-code">rebound = True</span><br>
        <span class="cond-code">capitulation_lock = False</span><br>
        <span class="cond-code">status = "VENDA"</span>
      </td>
      <td class="fonte-txt">Derivado do regime — USDT.D semanal tocando banda superior dentro de regime de venda</td>
      <td class="fonte-txt">Repique tático: o mercado está em regime de venda mas o USDT.D semanal chegou ao topo da banda, sinalizando possível alívio temporário do stress</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

    # ── Notas sobre capitulation_lock ─────────────────────────────────
    st.markdown(
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:6px;"
        "padding:10px 14px;font-size:12px;color:#8b949e;margin-bottom:20px;'>"
        "⚙️ <b style='color:#c9d1d9;'>capitulation_lock</b> — Bloqueia sinais de repique quando o mercado está "
        "em capitulação (queda acelerada sem recuperação confirmada). "
        "Evita entradas em repiques falsos durante movimentos de colapso."
        "</div>",
        unsafe_allow_html=True
    )

    # ── 2. TRADING SYSTEM (Forex / CFDs) ─────────────────────────────
    st.markdown("#### 2 · Trading System — Sinais Multi-TF (trading_system.py)")
    st.markdown(
        "<p style='color:#8b949e;font-size:12px;margin-top:-8px;margin-bottom:12px;'>"
        "Fonte: MetaTrader5 (OHLC idêntico ao terminal). "
        "Todos os timeframes avaliados simultaneamente — gatilho no menor TF, confirmação no maior."
        "</p>",
        unsafe_allow_html=True
    )
    st.markdown("""
<table class="sig-table">
  <thead>
    <tr>
      <th style="width:14%">Sinal</th>
      <th style="width:40%">Condição (todas obrigatórias, em ordem)</th>
      <th style="width:23%">Fonte</th>
      <th style="width:23%">O que significa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge s-comum">• COMUM</span></td>
      <td>
        <b style="color:#c9d1d9;font-size:11px;">1. Tendência Mensal</b><br>
        <span class="cond-code">ST_Trend mensal ≠ 0</span> (Supertrend ativo)<br><br>
        <b style="color:#c9d1d9;font-size:11px;">2. Tendência Semanal</b><br>
        <span class="cond-code">EMA50 &gt; EMA100 &gt; EMA200</span> (compra) ou inverso (venda) — não deve contradizer o mensal<br><br>
        <b style="color:#c9d1d9;font-size:11px;">3. Gatilho menor TF (4H ou D1)</b><br>
        <span class="cond-code">RSI toca ou near canal inferior</span> (compra) / superior (venda)<br><br>
        <b style="color:#c9d1d9;font-size:11px;">4. Confirmação Semanal ou Mensal</b><br>
        <span class="cond-code">RSI semanal OU mensal</span> tocando ou near o canal<br><br>
        <b style="color:#c9d1d9;font-size:11px;">5. EMA próxima</b><br>
        <span class="cond-code">Preço perto de EMA50/100/200</span> em qualquer TF (D1, W1 ou MN)
      </td>
      <td class="fonte-txt">MT5: Mensal, Semanal, Diário e 4H<br><br>Canal RSI: regressão linear (50 períodos, ×2 desvios)<br><br>RSI: Wilder 14 períodos (idêntico ao iRSI do MT5)</td>
      <td class="fonte-txt">Confluência multi-timeframe: tendência maior alinhada + pullback no RSI no TF menor + confirmação num TF superior. Ponto de entrada na direção do fluxo principal</td>
    </tr>
    <tr>
      <td><span class="badge s-super">⭐ SUPER</span></td>
      <td>
        <b style="color:#c9d1d9;font-size:11px;">Todas as condições do COMUM, mais:</b><br><br>
        <b style="color:#c9d1d9;font-size:11px;">ST toque real</b><br>
        <span class="cond-code">Low ≤ ST_Line ≤ High</span> (candle tocou a linha do Supertrend)<br><br>
        <b style="color:#c9d1d9;font-size:11px;">OU nível Athena oposto</b><br>
        <span class="cond-code">Preço near nível Athena</span> do lado contrário à direção (compra perto do sell_entry, venda perto do buy_entry)
      </td>
      <td class="fonte-txt">Supertrend: ATR 10 × 3.0<br><br>Nível Athena: definido manualmente na sidebar do Trading System</td>
      <td class="fonte-txt">Sinal COMUM com confluência extra: preço tocou o Supertrend (suporte/resistência dinâmico) ou chegou ao nível Athena oposto. Maior precisão de entrada</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

    # ── Canal RSI explicado ───────────────────────────────────────────
    st.markdown(
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:6px;"
        "padding:10px 14px;font-size:12px;color:#8b949e;margin-bottom:20px;'>"
        "📐 <b style='color:#c9d1d9;'>Canal RSI (Regressão Linear)</b> — "
        "O canal não é fixo (30/70). É calculado dinamicamente sobre os últimos 50 candles do RSI "
        "usando regressão linear + desvio padrão ×2. O toque na borda inferior em tendência de alta "
        "indica pullback no fluxo — compra contra-tendência de curto prazo na direção do fluxo maior. "
        "Lógica idêntica ao indicador <i>Rsi_slope_divergence_mtf.mq5</i>."
        "</div>",
        unsafe_allow_html=True
    )

    # ── 3. MARKET ANALYSIS ───────────────────────────────────────────
    st.markdown("#### 3 · Market Analysis — Sinais Macro/Risco (market_analysis_app.py)")
    st.markdown(
        "<p style='color:#8b949e;font-size:12px;margin-top:-8px;margin-bottom:12px;'>"
        "Fonte: yfinance (BTC-USD, SPY, par Forex). Detecta o sinal mais recente de cada gráfico "
        "comparando os indicadores do último candle com os thresholds definidos. "
        "Cooldown de 24h por sinal — não reenvia entre reinicializações."
        "</p>",
        unsafe_allow_html=True
    )
    st.markdown("""
<table class="sig-table">
  <thead>
    <tr>
      <th style="width:22%">Gráfico</th>
      <th style="width:20%">Indicadores</th>
      <th style="width:35%">Condição BUY / SELL</th>
      <th style="width:23%">O que significa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b style="color:#c9d1d9;">Risk-Return Weekly<br>(BTC+SPY Macro)</b></td>
      <td class="fonte-txt">Sharpe (52sem, 60per)<br>Sortino (52sem, 60per)</td>
      <td class="fonte-txt"><span class="cond-code">macro_sig_btc(sh, so)</span> — confluência Sharpe ≥ −1.5/2.0 e Sortino ≥ −1.5/4.5</td>
      <td class="fonte-txt">Regime macro BTC favorável ou defensivo no semanal</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">BTC Daily</b></td>
      <td class="fonte-txt">RSI 14<br>StochRSI 14,3<br>BB%B 20,2</td>
      <td class="fonte-txt"><span class="cond-code">combined([RSI, Stoch, BB], pesos [0.5, 0.5, 2.0], th=3.0)</span></td>
      <td class="fonte-txt">Momentum diário com peso maior no BB%B — entrada tática</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">BTC Weekly</b></td>
      <td class="fonte-txt">Sharpe (52sem, 60per)<br>Sortino (52sem, 60per)</td>
      <td class="fonte-txt"><span class="cond-code">confirmed(sharpe_sig, sortino_sig)</span> — ambos confirmam simultaneamente</td>
      <td class="fonte-txt">Risco/retorno semanal BTC com dupla confirmação</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">BTC Monthly</b></td>
      <td class="fonte-txt">Sharpe (12m, 60per)<br>Sortino (12m, 60per)</td>
      <td class="fonte-txt"><span class="cond-code">macro_sig_btc(sh, so)</span> — mensal</td>
      <td class="fonte-txt">Regime macro BTC de longo prazo</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">SPY Weekly</b></td>
      <td class="fonte-txt">Sharpe (52sem, 60per)<br>Sortino (52sem, 60per)</td>
      <td class="fonte-txt"><span class="cond-code">macro_sig_spy(sh, so)</span> — thresholds SPY (sell=2.19 / 4.7)</td>
      <td class="fonte-txt">Regime risco/retorno S&amp;P500 semanal</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">SPY Monthly</b></td>
      <td class="fonte-txt">Sharpe (12m, 60per)<br>Sortino (12m, 60per)</td>
      <td class="fonte-txt"><span class="cond-code">macro_sig_spy(sh, so)</span> — mensal</td>
      <td class="fonte-txt">Regime macro S&amp;P500 de longo prazo</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">Forex Daily</b></td>
      <td class="fonte-txt">RSI 14<br>StochRSI 14,3<br>BB%B 20,2</td>
      <td class="fonte-txt"><span class="cond-code">combined([RSI, Stoch, BB], pesos [0.5, 0.5, 2.0], th=3.0)</span></td>
      <td class="fonte-txt">Momentum diário do par Forex selecionado</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">Forex Weekly</b></td>
      <td class="fonte-txt">RSI 14<br>StochRSI 14,3</td>
      <td class="fonte-txt"><span class="cond-code">combined([RSI, Stoch], pesos [1, 1], th=2.0)</span></td>
      <td class="fonte-txt">Momentum semanal do par Forex — confirmação de tendência</td>
    </tr>
    <tr>
      <td><b style="color:#f85149;">⚠️ BTC Overextended<br>(Mensal)</b></td>
      <td class="fonte-txt">Sharpe (12m)<br>Sortino (12m)</td>
      <td class="fonte-txt">
        <span class="cond-code">Sharpe ≥ 6.0</span> OU <span class="cond-code">Sortino ≥ 8.0</span><br>
        <span style="font-size:11px;color:#6e7681;">Sempre gera SELL — euforia mensal BTC</span>
      </td>
      <td class="fonte-txt">BTC em território de euforia: Sharpe ou Sortino mensal muito acima dos padrões históricos — alerta de reversão iminente</td>
    </tr>
    <tr>
      <td><b style="color:#f85149;">⚠️ SPY Overextended<br>(Mensal)</b></td>
      <td class="fonte-txt">Sharpe (12m)<br>Sortino (12m)</td>
      <td class="fonte-txt">
        <span class="cond-code">Sharpe ≥ 6.0</span> OU <span class="cond-code">Sortino ≥ 5.0</span><br>
        <span style="font-size:11px;color:#6e7681;">Sempre gera SELL — euforia mensal SPY</span>
      </td>
      <td class="fonte-txt">S&amp;P500 em euforia: thresholds mais conservadores que BTC por ser um índice menos volátil</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

    st.markdown(
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:6px;"
        "padding:10px 14px;font-size:12px;color:#8b949e;margin-bottom:20px;'>"
        "⏱ <b style='color:#c9d1d9;'>Cooldown 24h</b> — Cada sinal é identificado pela chave "
        "<span style='font-family:monospace;background:#0d1117;padding:1px 4px;border-radius:3px;color:#79c0ff;'>"
        "chart_DIRECTION</span>. Uma vez enviado, não reenvia por 24h mesmo que o sistema reinicie "
        "(persiste em <span style='font-family:monospace;background:#0d1117;padding:1px 4px;"
        "border-radius:3px;color:#79c0ff;'>~/.montrezor_ma_cooldown.json</span>)."
        "</div>",
        unsafe_allow_html=True
    )

    # ── 4. Fluxo de dados ─────────────────────────────────────────────
    st.markdown("#### 4 · Fluxo de dados entre os sistemas")
    st.markdown("""
<table class="sig-table">
  <thead>
    <tr>
      <th style="width:20%">Sistema</th>
      <th style="width:25%">Gera</th>
      <th style="width:25%">Consome</th>
      <th style="width:30%">Como chega ao Telegram</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b style="color:#c9d1d9;">visualizer.py</b></td>
      <td class="fonte-txt"><span class="cond-code">macro_timing.json</span><br>Rebuilt a cada 5 min (ou on-demand)</td>
      <td class="fonte-txt">TvDatafeed (USDT.D, Others) + CoinGecko (funding BTC)</td>
      <td class="fonte-txt">Não envia Telegram diretamente — fornece dados</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">app.py (Gems)</b></td>
      <td class="fonte-txt">Sinais SUPER_BUY, SUPER_SELL, BUY, SELL, SUPER_REPIQUE, REPIQUE</td>
      <td class="fonte-txt"><span class="cond-code">macro_timing.json</span> gerado pelo visualizer</td>
      <td class="fonte-txt">Via <span class="cond-code">montrezor_alerts_integration</span> → <span class="cond-code">send_gems_alert()</span>. Cooldown por transição de estado (não reenvia enquanto o sinal for o mesmo)</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">trading_system.py</b></td>
      <td class="fonte-txt">Sinais COMUM e SUPER por par forex/CFD</td>
      <td class="fonte-txt">MT5 direto (OHLC idêntico ao gráfico)</td>
      <td class="fonte-txt">Via <span class="cond-code">send_telegram_alert()</span> a cada ciclo com sinal ativo</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">market_analysis_app.py</b></td>
      <td class="fonte-txt">8 sinais macro/risco + 2 alertas overextended (BTC e SPY)</td>
      <td class="fonte-txt">yfinance (BTC-USD, SPY, par Forex) direto</td>
      <td class="fonte-txt">Via <span class="cond-code">_send_tg_ma()</span>. Cooldown 24h persistido em disco — não reenvia entre reinicializações</td>
    </tr>
    <tr>
      <td><b style="color:#c9d1d9;">montrezor_daemon.py</b></td>
      <td class="fonte-txt">Todos os sinais acima, 24/7</td>
      <td class="fonte-txt">MT5 + <span class="cond-code">macro_timing.json</span> + <span class="cond-code">.montrezor_data.json</span> + <span class="cond-code">market_analysis_app.py</span></td>
      <td class="fonte-txt">Telegram direto com cooldown. Independente do browser — roda em background mesmo com o Streamlit fechado</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

with tab7:
    st.markdown("### 🤖 AI Gems Filter")
    st.markdown(
        "<p style='color:#8b949e;font-size:13px;margin-top:-10px'>"
        "O Claude analisa todos os snapshots do Gems Finder e retorna as moedas "
        "com maior probabilidade de valorização. Ciclo semanal (top 10) e mensal (top 3)."
        "</p>", unsafe_allow_html=True)

    if not _AI_AVAILABLE:
        st.error("gems_ai_filter.py não encontrado. Coloque na mesma pasta do app.py.")
        st.stop()

    with st.expander("⚙️ Configuração", expanded=False):
        ai_key_input = st.text_input(
            "Anthropic API Key", type="password",
            value=os.environ.get("ANTHROPIC_API_KEY",""),
            help="Obtenha em console.anthropic.com. O plano gratuito é suficiente.")
        if ai_key_input:
            _clean_key = ai_key_input.strip().strip('"').strip("'").strip()
            os.environ["ANTHROPIC_API_KEY"] = _clean_key
            try:
                cfg_file = os.path.join(os.path.expanduser("~"), ".montrezor_ai.json")
                json.dump({"anthropic_key": _clean_key}, open(cfg_file,"w", encoding="utf-8"))
            except Exception:
                pass
            # Validação rápida do formato
            if not _clean_key.startswith("sk-ant-"):
                st.warning("⚠️ Key salva mas formato inesperado — keys Anthropic começam com sk-ant-")
            else:
                st.success(f"✅ API Key salva ({_clean_key[:12]}...)")
        st.markdown(
            "<div style='font-size:11px;color:#8b949e'>"
            "Modelo: <b>claude-haiku-4-5</b> — rápido, econômico, gratuito no free tier. "
            "Cada análise usa ~2000 tokens.</div>", unsafe_allow_html=True)

    api_key = _ai._get_api_key()

    # Auto-update performance ao carregar a aba (silencioso)
    if "perf_auto_updated" not in st.session_state:
        try:
            n = _ai.auto_update_performance()
            if n > 0:
                st.toast(f"📈 {n} picks atualizadas automaticamente via CoinGecko")
        except Exception:
            pass
        st.session_state.perf_auto_updated = True

    weekly_result  = _ai.get_latest("weekly")
    monthly_result = _ai.get_latest("monthly")

    # Banner automático se ciclo vencido
    if api_key:
        if _ai.should_run("weekly"):
            st.warning("⏰ **Análise semanal vencida** — clique em 'Rodar Análise Semanal' para atualizar.")
        if _ai.should_run("monthly"):
            st.info("📅 **Análise mensal disponível** — clique em 'Rodar Análise Mensal (Top 3)'.")

    # --- Cards de ciclos com barra de progresso ---
    def _cycle_progress(last_run_str, period_days):
        if not last_run_str or last_run_str == "Nunca rodou":
            return 0.0, "Nunca"
        try:
            last = datetime.strptime(last_run_str.split()[0], "%Y-%m-%d")
            days_passed = (datetime.now() - last).days
            progress = min(days_passed / period_days, 1.0)
            remaining = max(0, period_days - days_passed)
            return progress, f"{remaining}d restantes" if remaining > 0 else "Vencido"
        except:
            return 0.0, "?"

    w_ts = weekly_result.get("generated_at", "Nunca rodou") if weekly_result else "Nunca rodou"
    m_ts = monthly_result.get("generated_at", "Nunca rodou") if monthly_result else "Nunca rodou"
    w_prog, w_rem = _cycle_progress(w_ts, 7)
    m_prog, m_rem = _cycle_progress(m_ts, 30)

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
        <div class="cycle-card">
            <div><span>📅</span> <b>Ciclo semanal</b></div>
            <div style="font-size:12px;color:#8b949e">Último run: {w_ts[:10] if w_ts != 'Nunca rodou' else '—'}</div>
            <div class="progress-bar-bg"><div class="progress-fill" style="width:{w_prog*100}%;background:#3fb950"></div></div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#8b949e">
                <span>{w_rem}</span>
                <span class="badge-ok">✅ Atualizado</span>
            </div>
        </div>
        <div class="cycle-card">
            <div><span>📅</span> <b>Ciclo mensal</b></div>
            <div style="font-size:12px;color:#8b949e">Último run: {m_ts[:10] if m_ts != 'Nunca rodou' else '—'}</div>
            <div class="progress-bar-bg"><div class="progress-fill" style="width:{m_prog*100}%;background:#e3b341"></div></div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#8b949e">
                <span>{m_rem}</span>
                <span class="badge-warn">⏳ Vencendo</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    btn_col1, btn_col2, btn_col3 = st.columns([2,2,1])
    with btn_col1:
        run_weekly  = st.button("🔍 Rodar Análise Semanal",  type="primary",
                                width='stretch', disabled=not bool(api_key))
    with btn_col2:
        run_monthly = st.button("🏆 Rodar Análise Mensal (Top 3)",
                                width='stretch', disabled=not bool(api_key))
    with btn_col3:
        force_run = st.checkbox("Forçar", value=False,
                                help="Rodar mesmo que o ciclo ainda não tenha vencido")

    if not api_key:
        st.warning("Configure a Anthropic API Key acima para usar o filtro AI.")

    for cycle, trigger in [("weekly", run_weekly), ("monthly", run_monthly)]:
        if not trigger:
            continue
        with st.spinner(f"Claude analisando dados... {'semanal' if cycle=='weekly' else 'mensal'}"):
            try:
                result = _ai.run_analysis(cycle, api_key, force=force_run)
                st.success(f"✅ Análise {'semanal' if cycle=='weekly' else 'mensal'} concluída!")
                if cycle == "weekly":
                    weekly_result = result
                else:
                    monthly_result = result
            except Exception as e:
                st.error(f"Erro: {e}")

    # ── Exibir versão do modelo ML ─────────────────────────────────
    if _ML_AVAILABLE:
        model_info = get_current_model_info()
        if model_info:
            acc_str = f"{model_info['accuracy']*100:.1f}%" if model_info['accuracy'] is not None else "N/A"
            st.markdown(f"""
            <div style="background:#0d1117; border:1px solid #30363d; border-radius:8px; padding:8px 12px; margin:10px 0;">
                <span style="font-size:12px; color:#8b949e;">🧠 Modelo ML ativo:</span>
                <span style="font-size:12px; font-weight:500; color:#a371f7;"> versão {model_info['version']} </span>
                <span style="font-size:11px; color:#8b949e;"> (acurácia {acc_str} | {model_info['n_samples']} amostras)</span>
                <span style="font-size:11px; color:#484f58;"> treinado em {model_info['date'][:10] if model_info['date'] else '?'}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("🧠 Nenhum modelo ML treinado ainda. Aguardando 30 picks avaliados.")
    else:
        st.info("🧠 Módulo ml_ranker não disponível.")

    # ========== DASHBOARD DE PERFORMANCE GERAL ==========
    try:
        perf_dash = _ai.get_performance_dashboard(lookback_picks=60)
        if "error" not in perf_dash:
            st.markdown("---")
            st.markdown("### 📊 PERFORMANCE GERAL DO SISTEMA")
            st.markdown(f"*Base: últimas {perf_dash['total_picks']} picks do Claude*")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Win rate", f"{perf_dash['win_rate']}%")
            c2.metric("Ganho médio (WIN)", f"+{perf_dash['avg_win']}%")
            c3.metric("Perda média (LOSS)", f"{perf_dash['avg_loss']}%")
            c4.metric("Risk / reward", f"{perf_dash['risk_reward']:.2f}x")

            # ML Performance
            ml_perf = _ai.get_ml_performance()
            if "error" not in ml_perf:
                ml_acc = ml_perf['accuracy']
                ml_correct = ml_perf['correct']
                ml_total = ml_perf['total']
            else:
                ml_acc = 0
                ml_correct = 0
                ml_total = 0

            # Win rate por rank
            wr1 = perf_dash['rank_stats'].get('1', {}).get('win_rate', 0)
            wr2 = perf_dash['rank_stats'].get('2', {}).get('win_rate', 0)
            wr3 = perf_dash['rank_stats'].get('3', {}).get('win_rate', 0)
            wr23 = (wr2 + wr3) / 2 if wr3 else wr2

            st.markdown(f"""
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px">
                <div class="metric-mini-card">
                    <div style="font-size:12px;color:#8b949e">🧠 ML Confidence</div>
                    <div style="font-size:22px;font-weight:500">{ml_acc}%</div>
                    <div style="font-size:11px;color:#8b949e">{ml_correct}/{ml_total} picks</div>
                </div>
                <div class="metric-mini-card">
                    <div style="font-size:12px;color:#8b949e">Win rate rank #1</div>
                    <div style="font-size:22px;font-weight:500">{wr1:.0f}%</div>
                </div>
                <div class="metric-mini-card">
                    <div style="font-size:12px;color:#8b949e">Win rate rank #2-3</div>
                    <div style="font-size:22px;font-weight:500">{wr23:.0f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"**🏷️ Classificação:** {perf_dash['quality']}")

            st.markdown("---")
            st.markdown("### 📡 Winrate dos Sinais (7 dias)")
            try:
                macro_stats = _ai.get_macro_signal_performance(days_window=7)
                if macro_stats:
                    import pandas as pd
                    df_macro = pd.DataFrame([
                        {"Regime": r, "Acertos": s["wins"], "Total": s["total"], "Winrate": f"{s['winrate']:.0f}%"}
                        for r, s in macro_stats.items() if s["total"] >= 1
                    ])
                    st.dataframe(df_macro, hide_index=True, width='stretch')
                    # Gráfico de barras
                    chart_data = {r: s["winrate"] for r, s in macro_stats.items() if s["total"] >= 1}
                    if chart_data:
                        st.bar_chart(chart_data)
                else:
                    st.info("Nenhum sinal macro avaliado ainda. Aguarde 7 dias após o primeiro registro.")
            except Exception as e:
                st.info(f"Aguardando dados: {e}")

            st.markdown("### 📡 Winrate dos Sinais de Entrada (weekly_buy, rebound, etc.)")
            try:
                detailed_stats = _ai.get_detailed_signal_performance()
                if detailed_stats:
                    import pandas as pd
                    df_detailed = pd.DataFrame([
                        {"Sinal": s, "Acertos": d["wins"], "Total": d["total"], "Winrate": f"{d['winrate']:.0f}%", "Retorno Médio": f"{d['avg_return']:+.1f}%"}
                        for s, d in detailed_stats.items() if d["total"] >= 1
                    ])
                    st.dataframe(df_detailed, hide_index=True, width='stretch')
                else:
                    st.info("Nenhum sinal de entrada avaliado ainda. Aguarde o primeiro sinal e próximo sinal do mesmo tipo.")
            except Exception as e:
                st.info(f"Aguardando dados: {e}")

            st.markdown("### 📊 Ciclos Completos de Regime (BUY→SELL / SELL→BUY)")
            try:
                cycle_stats = _ai.get_macro_cycle_stats()
                if cycle_stats:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Ciclos BUY", cycle_stats["buy_cycles"].get("total", 0),
                                 f"{cycle_stats['buy_cycles'].get('winrate',0):.0f}% acerto")
                    with col2:
                        st.metric("Retorno médio (BUY)", f"{cycle_stats['buy_cycles'].get('avg_return',0):+.1f}%")
                    with col3:
                        st.metric("Ciclos SELL", cycle_stats["sell_cycles"].get("total", 0),
                                 f"{cycle_stats['sell_cycles'].get('winrate',0):.0f}% acerto")
                    with col4:
                        st.metric("Retorno médio (SELL)", f"{cycle_stats['sell_cycles'].get('avg_return',0):+.1f}%")
                else:
                    st.info("Nenhum ciclo completo registrado ainda. Aguarde transições BUY↔SELL.")
            except Exception as e:
                st.info(f"Aguardando dados: {e}")

            # Gráfico de barras: win rate por rank
            st.markdown("#### 🏆 Win Rate por Rank (picks do Claude)")
            rank_data = {r: stats["win_rate"] for r, stats in perf_dash["rank_stats"].items() if r.isdigit() or r == "3-5"}
            if rank_data:
                import pandas as pd
                df_rank = pd.DataFrame({"Rank": list(rank_data.keys()), "Win Rate (%)": list(rank_data.values())})
                st.bar_chart(df_rank.set_index("Rank"))

            with st.expander("📈 Detalhes por ciclo e rank", expanded=False):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**Ciclo Semanal**")
                    st.metric("Win Rate", f"{perf_dash['cycle_stats']['weekly']['win_rate']:.0f}%",
                            f"{perf_dash['cycle_stats']['weekly']['wins']}/{perf_dash['cycle_stats']['weekly']['total']}")
                    st.markdown("**Ciclo Mensal**")
                    st.metric("Win Rate", f"{perf_dash['cycle_stats']['monthly']['win_rate']:.0f}%",
                            f"{perf_dash['cycle_stats']['monthly']['wins']}/{perf_dash['cycle_stats']['monthly']['total']}")

                with col_b:
                    st.markdown("**Win Rate por Rank**")
                    for r in ["1", "2", "3-5"]:
                        if r in perf_dash["rank_stats"]:
                            wr = perf_dash["rank_stats"][r]["win_rate"]
                            avg = perf_dash["rank_stats"][r]["avg_pct"]
                            st.metric(f"Rank {r}", f"{wr:.0f}%", f"média {avg:+.1f}%")

            # ── Win Rate por Regime Macro (picks reais) ─────────────────
            perf_data = _ai._load_performance()
            if perf_data:
                regime_stats = {}
                for p in perf_data:
                    regime = p.get("market_regime", "UNKNOWN")
                    regime_stats.setdefault(regime, {"total": 0, "wins": 0})
                    regime_stats[regime]["total"] += 1
                    if p.get("pct_change", 0) > 10:
                        regime_stats[regime]["wins"] += 1

                if regime_stats:
                    st.markdown("**📊 Win Rate por Regime Macro (picks reais)**")
                    df_regime = pd.DataFrame([
                        {"Regime": r, "Wins": s["wins"], "Total": s["total"],
                         "Win Rate": f"{s['wins']/s['total']*100:.0f}%" if s['total']>0 else "0%"}
                        for r, s in regime_stats.items()
                    ])
                    st.dataframe(df_regime, hide_index=True, width='stretch')

            with st.expander("🏆 Top 5 Winners (maior retorno)", expanded=False):
                for pick in perf_dash['best_picks']:
                    st.write(f"**{pick['symbol']}**: +{pick['pct']:.0f}% (rank #{pick['rank']}, {pick['cycle']})")

            with st.expander("📉 Worst 3 Losers", expanded=False):
                for pick in perf_dash['worst_picks']:
                    st.write(f"**{pick['symbol']}**: {pick['pct']:.0f}% (rank #{pick['rank']}, {pick['cycle']})")
        else:
            st.info(perf_dash['error'])
    except Exception as e:
        st.info(f"Aguardando dados de performance (execute pelo menos um ciclo semanal e aguarde 7 dias). {e}")

    def _render_pick_cards(result, title, n_show):
        if not result:
            st.info(f"Nenhuma análise {title.lower()} disponível. Clique em rodar acima.")
            return
        picks = result.get("top_picks", [])[:n_show]
        if not picks:
            return
        st.markdown(f"#### {title}")
        # Agrupar em linhas de 3 colunas
        for i in range(0, len(picks), 3):
            cols = st.columns(3)
            for idx, pick in enumerate(picks[i:i+3]):
                with cols[idx]:
                    rank = pick.get('rank', 0)
                    medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank}"))
                    risk = pick.get('risk', 'MEDIUM')
                    risk_color = {"LOW":"#3fb950","MEDIUM":"#e3b341","HIGH":"#f85149"}.get(risk, "#8b949e")
                    risk_badge = f'<span style="background:{risk_color}20;color:{risk_color};padding:2px 8px;border-radius:12px;font-size:11px">{risk} risk</span>'
                    potential = pick.get('potential', 'x2-x5')
                    pot_icon = {"x10+":"🚀","x5-x10":"⚡","x2-x5":"📈"}.get(potential, "•")
                    flags = pick.get('key_flags', [])
                    def flag_class(f):
                        f_low = f.lower()
                        if 'smart_money' in f_low or 'div' in f_low:
                            return 'flag-hot'
                        if 'trend_up' in f_low or 'rank_up' in f_low or 'vol_up' in f_low:
                            return 'flag-up'
                        if 'gold' in f_low or 'is_gold' in f_low:
                            return 'flag-gold'
                        return ''
                    flags_html = "".join([f'<span class="flag {flag_class(flag)}">{flag}</span>' for flag in flags])
                    ml_score = pick.get('ml_score')
                    ml_html = f'<div class="ml">🧠 ML {ml_score*100:.0f}%</div>' if ml_score else ''
                    rationale = pick.get('rationale', '—').replace('\n', '<br>')
                    st.markdown(f"""
                    <div class="pick-card" style="border-color:#30363d;">
                        <div style="position:absolute;top:0;left:0;width:4px;height:100%;background:{risk_color}"></div>
                        <div style="display:flex;justify-content:space-between;align-items:flex-start">
                            <div><div class="rank">{medal}</div><div class="symbol">{pick['symbol']}</div></div>
                            {risk_badge}
                        </div>
                        <div class="potential">{pot_icon} {potential} potencial</div>
                        <div class="rationale">{rationale}</div>
                        <div class="flags">{flags_html}</div>
                        <div class="score">Score <b style="color:#c9d1d9">{pick.get('composite_score',0):.1f}</b></div>
                        {ml_html}
                    </div>
                    """, unsafe_allow_html=True)

        # Exibir macro_note, top3_comparison, avoid (elementos que já estavam em _render_result)
        macro_note = result.get("macro_note", "")
        if macro_note:
            st.markdown(f'<div class="macro-note">{macro_note}</div>', unsafe_allow_html=True)
        comparison = result.get("top3_comparison")
        if comparison:
            st.markdown("#### 🔍 Comparação das Top 3")
            st.info(comparison)
        avoid = result.get("avoid", [])
        if avoid:
            st.markdown(f"""
            <div class="avoid-bar">
                <span>⛔</span> <b>Evitar:</b>
                {" ".join([f'<span class="avoid-pill">{a}</span>' for a in avoid[:3]])}
            </div>
            """, unsafe_allow_html=True)

    tab_w, tab_m, tab_data = st.tabs(["📅 Top 10 Semanal", "🏆 Top 3 Mensal", "📊 Dados Brutos"])
    with tab_w:
        _render_pick_cards(weekly_result, "Top 10 Semanal", 10)
    with tab_m:
        _render_pick_cards(monthly_result, "Top 3 Mensal", 3)
    with tab_data:
        dt1, dt2, dt3 = st.tabs(["📊 Dados Agregados", "🕐 Histórico de Runs", "🔬 DEX Early Stage"])
        with dt1:
            st.markdown("#### Dados Agregados dos Snapshots")
            try:
                df_agg = _ai.get_aggregated_data(7)
                if df_agg.empty:
                    st.info("Nenhum snapshot encontrado nos últimos 7 dias.")
                else:
                    show_cols = [c for c in ["symbol","composite_score","final_score","ratio",
                                              "accumulation_score","social_score","appearances",
                                              "momentum","sector","market_cap"]
                                 if c in df_agg.columns]
                    st.dataframe(df_agg[show_cols].head(50).reset_index(drop=True),
                                 width='stretch')
            except Exception as e:
                st.error(f"Erro ao carregar dados: {e}")
        with dt2:
            st.markdown("#### Histórico de Execuções")
            try:
                hist = _ai.get_history()
                if not hist:
                    st.info("Nenhuma análise rodada ainda.")
                else:
                    rows_h = [{"Data": h.get("ts","")[:16],
                               "Ciclo": h.get("cycle",""),
                               "CSVs lidos": h.get("n_csvs",0),
                               "Moedas analisadas": h.get("n_coins",0)}
                              for h in reversed(hist[-50:])]
                    st.dataframe(rows_h, width='stretch', hide_index=True)
            except Exception as e:
                st.error(f"Erro: {e}")

        with dt3:
            st.markdown("#### 🔬 DEX Early Stage — DexScreener")
            st.markdown(
                "<p style='color:#8b949e;font-size:12px;margin-top:-8px'>"
                "Tokens em estágio inicial detectados pelo dex_scanner.py. "
                "Atualizado a cada 2h pelo daemon. O Claude inclui esses dados "
                "na próxima análise semanal automaticamente.</p>",
                unsafe_allow_html=True)
            try:
                # Define o caminho absoluto baseado no diretório do script app.py
                _script_dir = os.path.dirname(os.path.abspath(__file__))
                _dex_path = os.path.join(_script_dir, "data", "dex_early_stage.csv")
                if not os.path.exists(_dex_path):
                    st.info("Nenhum dado DEX ainda. O daemon gera o arquivo a cada 2h, "
                            "ou rode o Gems Finder manualmente.")
                else:
                    _dex_df = pd.read_csv(_dex_path)
                    if _dex_df.empty:
                        st.info("Arquivo DEX vazio.")
                    else:
                        # Badge de última atualização
                        import datetime as _dt
                        _mtime = _dt.datetime.fromtimestamp(os.path.getmtime(_dex_path))
                        _age_min = int((datetime.now() - _mtime).total_seconds() / 60)
                        _age_lbl = f"{_age_min}min atrás" if _age_min < 60 else f"{_age_min//60}h atrás"
                        st.markdown(
                            f"<div style='background:#161b22;border:1px solid #30363d;"
                            f"border-radius:6px;padding:6px 12px;font-size:11px;color:#8b949e;"
                            f"display:inline-block;margin-bottom:10px'>"
                            f"📡 {len(_dex_df)} tokens | Atualizado {_age_lbl}</div>",
                            unsafe_allow_html=True)

                        # Colunas úteis
                        _show = [c for c in ["symbol","chain","price_usd","price_change_24h",
                                              "liquidity_usd","volume_24h_usd","buys_24h",
                                              "sells_24h","buy_ratio","dex_score","pair_url"]
                                 if c in _dex_df.columns]
                        st.dataframe(
                            _dex_df[_show].head(100).reset_index(drop=True),
                            width='stretch')

                        # Alerta: tokens com buy_ratio > 0.7 e volume alto
                        if "buy_ratio" in _dex_df.columns and "volume_24h_usd" in _dex_df.columns:
                            _hot = _dex_df[
                                (_dex_df["buy_ratio"] > 0.70) &
                                (_dex_df["volume_24h_usd"] > 50000)
                            ].head(5)
                            if not _hot.empty:
                                st.markdown(
                                    "<div style='background:#0f2a1a;border:1px solid #238636;"
                                    "border-radius:6px;padding:8px 14px;font-size:12px;"
                                    "color:#3fb950;margin-top:8px'>"
                                    "🔥 <b>Tokens quentes</b> (buy_ratio > 70% + vol > $50k):<br>"
                                    + " &nbsp;|&nbsp; ".join(
                                        f"<b>{r['symbol']}</b> chain={r.get('chain','?')} "
                                        f"ratio={r.get('buy_ratio',0):.0%}"
                                        for _, r in _hot.iterrows())
                                    + "</div>",
                                    unsafe_allow_html=True)
            except Exception as _e:
                st.error(f"Erro ao carregar dados DEX: {_e}")

    # --- Barra de contexto macro (usando weekly_result) ---
    #if weekly_result:
    #    regime = weekly_result.get('regime', '—')
    #    btc_ctx = weekly_result.get('btc_context', '')
    #    sectors = weekly_result.get('sectors_in_focus', [])
    #    gen_at = weekly_result.get('generated_at', '')[:10]
    #    st.markdown(f"""
    #    <div class="macro-bar">
    #        <span><b>Regime:</b> {regime}</span>
    #        <span><b>BTC:</b> {btc_ctx[:40]}</span>
    #        <span><b>Setores:</b> {', '.join(sectors) if sectors else '—'}</span>
    #        <span style="margin-left:auto;font-size:11px;color:#8b949e">{gen_at}</span>
    #    </div>
    #    """, unsafe_allow_html=True)

    # ── Performance Tracker ──────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📈 Performance Tracker — Registrar resultado das picks", expanded=False):
        st.markdown(
            "<div style='color:#8b949e;font-size:12px;margin-bottom:10px'>"
            "Registre o preço atual das picks para alimentar o feedback loop do Claude. "
            "Com o tempo, o Claude aprende quais moedas realmente performam.</div>",
            unsafe_allow_html=True)

        perf_data = _ai._load_performance()
        latest_w  = _ai.get_latest("weekly")
        picks_w   = latest_w.get("top_picks",[]) if latest_w else []

        if picks_w:
            st.markdown("**Registrar preços atuais (picks semanais):**")
            for p in picks_w:
                col_s, col_p, col_b = st.columns([2,2,1])
                with col_s:
                    st.markdown(f"**#{p['rank']} {p['symbol']}**")
                with col_p:
                    price_now = st.number_input(
                        "Preço atual ($)", min_value=0.0, key=f"perf_px_{p['symbol']}",
                        label_visibility="collapsed")
                with col_b:
                    if st.button("✅", key=f"perf_btn_{p['symbol']}",
                                  help="Registrar performance"):
                        price_at_pick = p.get("price_usd", 0)
                        if price_at_pick <= 0:
                            st.warning(f"Preço de referência não disponível para {p['symbol']}. Rode a análise novamente.")
                        else:
                            _ai.register_performance("weekly", p["symbol"], p["rank"], price_at_pick, price_now)

        if perf_data:
            st.markdown("**Histórico de performance:**")
            rows_p = [{
                "Data":      e.get("date",""),
                "Ciclo":     e.get("cycle",""),
                "Símbolo":   e.get("symbol",""),
                "Rank":      e.get("rank",""),
                "Preço Pick":f"${e.get('price_at_pick',0):.4f}",
                "Preço Atual":f"${e.get('price_now',0):.4f}",
                "Δ%":        f"{e.get('pct_change',0):+.1f}%",
                "Resultado": {"WIN":"✅ WIN","LOSS":"❌ LOSS","NEUTRAL":"➡️ NEUTRAL"}.get(
                                e.get("result",""),"—"),
            } for e in reversed(perf_data[-30:])]
            st.dataframe(rows_p, width='stretch', hide_index=True)

            wins_total = sum(1 for e in perf_data if e.get("result")=="WIN")
            total      = len(perf_data)
            wr         = wins_total/total*100 if total else 0
            wr_clr     = "#3fb950" if wr >= 50 else "#f85149"
            st.markdown(
                f"<div style='background:#161b22;border:1px solid #30363d;"
                f"border-radius:6px;padding:8px 14px;font-size:13px;margin-top:6px'>"
                f"Win Rate total: <b style='color:{wr_clr}'>{wr:.0f}%</b> "
                f"({wins_total}/{total} picks) &nbsp;·&nbsp; "
                f"Modelo: <b style='color:#c9d1d9'>claude-sonnet-4-20250514</b></div>",
                unsafe_allow_html=True)
        else:
            st.info("Nenhuma performance registrada ainda.")


# RODAPÉ
st.markdown("<br><p style='text-align: center; color: #484f58; font-size: 12px;'>Montrezor Analysis System | Powered by Igor Montrezor</p>", unsafe_allow_html=True)

with tab6:
    st.markdown("### 💼 Portfólio de Futuros")
    if _PORT_AVAILABLE:
        # Passar o sinal macro atual para o portfólio
        _current_macro = st.session_state.get("gems_macro_telegram_last")
        render_portfolio_tab(macro_signal=_current_macro)
    else:
        st.warning("portfolio_tab.py não encontrado. Coloque na mesma pasta do app.py.")
