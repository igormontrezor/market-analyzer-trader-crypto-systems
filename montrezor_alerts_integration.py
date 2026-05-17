"""
MONTREZOR ALERTS INTEGRATION
Integração centralizada de alertas para Trading System e Gems System

Funciona como ponte para coordenar alertas de ambos os sistemas
via Telegram e exportação de histórico unificado.
"""

import json
import os
import html
import requests
import pandas as pd
from datetime import datetime

# ============================================================
# ARQUIVO DE CONFIG
# ============================================================
TELEGRAM_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_telegram.json")
SIGNALS_LOG_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_signals_unified.json")


def load_telegram_config() -> tuple:
    """Carrega config de Telegram."""
    if os.path.exists(TELEGRAM_CONFIG_FILE):
        try:
            with open(TELEGRAM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                t = (cfg.get("token") or "").strip()
                c = str(cfg.get("chat_id") or "").strip()
                return t, c
        except Exception:
            pass
    return "", ""


def send_trading_alert(symbol: str, direction: str, signal_type: str, price: float,
                       stoch_div: bool = False, mn_ema_div: bool = False,
                       touch_tfs: list = None, div_grade: str = None,
                       vol_ratio: float = None, vol_high: bool = False,
                       atr_low: bool = False, atr_ratio: float = None,
                       elevated: bool = False, elevation_reason: str = None) -> bool:
    """Envia alerta de Trading System via Telegram — mesmo formato do trading_system.py."""
    token, chat_id = load_telegram_config()
    if not token or not chat_id:
        return False

    try:
        direction_icon = "📈" if direction == "COMPRA" else "📉"
        type_icon = "⭐" if signal_type == "SUPER" else "•"
        esc = html.escape
        ts = esc(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))

        tf_text   = f"<b>Toques RSI</b>: {esc(' | '.join(touch_tfs))}\n" if touch_tfs else ""
        elev_text = f"<b>Elevação</b>: COMUM → SUPER ({esc(elevation_reason)})\n" if elevated and elevation_reason else ""
        div_text  = f"<b>Div RSI</b>: {esc({'W1':'⚡ W1','D1':'D1','4H':'4H'}.get(div_grade, div_grade))}\n" if div_grade else ""
        vol_text  = f"<b>Volume 4H</b>: {'🔥' if vol_high else '·'} {vol_ratio:.1f}x média\n" if vol_ratio is not None else ""
        atr_text  = f"⚠️ <b>ATR baixo</b> ({atr_ratio:.2f}x) — mercado em range\n" if atr_low and atr_ratio else ""
        verif_macro = f"🔍 <b>Verif. Macro</b>: {'Verifique divergencias no Market Analysis (D1 e W1)!'}\n"
        warns_text = ""
        if stoch_div:  warns_text += "⚠️ <b>StochRSI</b>: Contra o movimento!\n"
        if mn_ema_div: warns_text += "🚨 <b>EMA Mensal</b>: Tendência divergente!\n"

        message = (
            f"{direction_icon} <b>SINAL {esc(signal_type)}</b> {type_icon}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Par</b>: {esc(symbol)}\n"
            f"<b>Direção</b>: {esc(direction)}\n"
            f"<b>Preço</b>: {price:.5f}\n"
            f"{tf_text}{elev_text}{div_text}{vol_text}{atr_text}{warns_text}{verif_macro}\n"
            f"<b>Hora</b>: {ts}\n\n"
            "Montrezor Trading System"
        )

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=15)
        if resp.status_code == 200:
            return True
        # Fallback plain text
        tf_plain  = ("Toques: " + " | ".join(touch_tfs) + "\n") if touch_tfs else ""
        ts_plain  = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        plain = (
            f"{direction_icon} SINAL {signal_type}\n"
            f"Par: {symbol}\nDireção: {direction}\nPreço: {price:.5f}\n"
            f"{tf_plain}Hora: {ts_plain}\nMontrezor Trading System"
        )
        resp2 = requests.post(url, json={"chat_id": chat_id, "text": plain}, timeout=15)
        return resp2.status_code == 200
    except:
        return False


def send_gems_alert(symbol: str, signal_type: str, market_cap: float = 0, funding_rate: float = 0) -> bool:
    """Envia alerta de Gems System via Telegram."""
    token, chat_id = load_telegram_config()
    if not token or not chat_id:
        return False

    try:
        icon_map = {
            "SUPER_BUY": "⚡🟢",
            "SUPER_SELL": "🚨🔴",
            "SUPER_REPIQUE": "⚡🔵",
            "REPIQUE": "🔵",
            "BUY": "🟢",
            "SELL": "🔴",
            "NEUTRO": "⚪",
            "ACELERANDO": "🚀",
            "DESACELERANDO": "📉",
            "ESTÁVEL": "➡️",
        }
        icon = icon_map.get(signal_type, "•")

        esc = html.escape
        ts = esc(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
        msg_lines = [
            f"{icon} <b>GEMS ALERT</b> — {esc(signal_type)}",
            "━━━━━━━━━━━━━━━━━━",
            f"<b>Ativo</b>: {esc(symbol)}",
            f"<b>Status</b>: {esc(signal_type)}",
            f"<b>Hora</b>: {ts}",
            "<b>Sistema</b>: 💎 Gems Finder",
        ]

        if market_cap > 0:
            msg_lines.insert(5, f"<b>Market Cap</b>: ${market_cap:,.0f}")
        if funding_rate != 0:
            msg_lines.insert(6, f"<b>Funding Rate</b>: {funding_rate:.3f}%")

        msg_lines.append("")
        msg_lines.append("#gems #" + symbol.lower().replace(" ", ""))
        message = "\n".join(msg_lines)

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, json=payload, timeout=15)
        try:
            if resp.status_code == 200 and resp.json().get("ok"):
                return True
        except Exception:
            if resp.status_code == 200:
                return True
        plain = "\n".join(
            [
                f"{icon} GEMS ALERT — {signal_type}",
                "-------------------",
                f"Ativo: {symbol}",
                f"Status: {signal_type}",
                f"Hora: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "Gems Finder",
                "",
                "#gems #" + symbol.lower().replace(" ", ""),
            ]
        )
        resp2 = requests.post(
            url, json={"chat_id": chat_id, "text": plain}, timeout=15
        )
        try:
            return resp2.status_code == 200 and resp2.json().get("ok")
        except Exception:
            return resp2.status_code == 200
    except Exception:
        return False


def log_signal(system: str, symbol: str, signal_info: dict):
    """Registra sinal no log unificado."""
    try:
        logs = []
        if os.path.exists(SIGNALS_LOG_FILE):
            with open(SIGNALS_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)

        entry = {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system": system,  # "TRADING" ou "GEMS"
            "symbol": symbol,
            **signal_info
        }

        logs.insert(0, entry)

        # Manter últimos 500 sinais
        if len(logs) > 500:
            logs = logs[:500]

        with open(SIGNALS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

        return True
    except:
        return False


def export_all_signals_csv() -> str:
    """Exporta todos os sinais unificados em CSV."""
    try:
        if os.path.exists(SIGNALS_LOG_FILE):
            with open(SIGNALS_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)

            if logs:
                df = pd.DataFrame(logs)
                return df.to_csv(index=False)
    except:
        pass

    return ""


def get_signal_stats() -> dict:
    """Retorna estatísticas dos sinais."""
    try:
        if os.path.exists(SIGNALS_LOG_FILE):
            with open(SIGNALS_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)

            total = len(logs)
            trading_count = sum(1 for log in logs if log.get('system') == 'TRADING')
            gems_count = sum(1 for log in logs if log.get('system') == 'GEMS')

            return {
                "total": total,
                "trading": trading_count,
                "gems": gems_count,
                "last_signal": logs[0]["timestamp"] if logs else None
            }
    except:
        pass

    return {"total": 0, "trading": 0, "gems": 0, "last_signal": None}


# ============================================================
# EXEMPLO DE USO EM APP.PY
# ============================================================
"""
# No gems_system/app.py, substituir os alertas por:

from montrezor_alerts_integration import send_gems_alert, log_signal

# Quando detectar um sinal:
if is_super_buy:
    send_gems_alert("BTC", "SUPER_BUY", market_cap=50000000, funding_rate=0.023)
    log_signal("GEMS", "BTC", {"type": "SUPER_BUY", "market_cap": 50000000})

# Para exportar CSV:
from montrezor_alerts_integration import export_all_signals_csv
csv_data = export_all_signals_csv()
st.download_button("📥 Exportar Todos", csv_data, "sinais_unificados.csv", "text/csv")
"""
