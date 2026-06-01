#!/usr/bin/env python3
"""
position_monitor.py
Sistema de monitoramento de posições abertas:
- Registrar entrada (ativo, direção, preço, timeframe de referência)
- Alertas de saída: RSI canal (topo/fundo), StochRSI (sobrecompra/sobrevenda)
- Alerta de variação contra a posição (>3%)
- Persistência em JSON
- Integração com Telegram e alertas sonoros/visuais
"""

import os
import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st

# Importar funções necessárias do trading_system (para não duplicar código)
# Mas para evitar dependência circular, vamos usar import dentro de funções ou redefinir?
# Melhor: o trading_system.py vai injetar as dependências (fetch_multi_tf_data, send_telegram_alert, play_alert_sound)
# Então este módulo receberá essas funções como parâmetros ou as importará dinamicamente.

# Arquivos de persistência
POSITIONS_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_positions.json")
ALERTS_LOG_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_position_alerts.json")

class Position:
    """Representa uma posição aberta."""
    def __init__(self, symbol: str, direction: str, entry_price: float, entry_time: str,
                 tf_reference: str = "4h", stop_loss: float = None, take_profit: float = None,
                 alerts_sent: List[str] = None):
        self.symbol = symbol
        self.direction = direction.upper()  # "COMPRA" ou "VENDA"
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.tf_reference = tf_reference  # "4h" ou "1d"
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.alerts_sent = alerts_sent or []  # lista de alertas já enviados para esta posição

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "tf_reference": self.tf_reference,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "alerts_sent": self.alerts_sent
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(
            symbol=data["symbol"],
            direction=data["direction"],
            entry_price=data["entry_price"],
            entry_time=data["entry_time"],
            tf_reference=data.get("tf_reference", "4h"),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            alerts_sent=data.get("alerts_sent", [])
        )


def load_positions() -> List[Position]:
    """Carrega posições do arquivo JSON."""
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Position.from_dict(p) for p in data]
        except Exception:
            pass
    return []


def save_positions(positions: List[Position]):
    """Salva posições no arquivo JSON."""
    try:
        with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in positions], f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_alerts_log() -> List[Dict]:
    """Carrega histórico de alertas."""
    if os.path.exists(ALERTS_LOG_FILE):
        try:
            with open(ALERTS_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_alert_log(alert: Dict):
    """Adiciona um alerta ao histórico e salva."""
    logs = load_alerts_log()
    logs.insert(0, alert)
    # manter últimos 200
    logs = logs[:200]
    try:
        with open(ALERTS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def check_exit_conditions(position: Position, data: Dict[str, pd.DataFrame]) -> List[tuple]:
    """
    Verifica condições de saída para uma posição.
    Retorna lista de (alert_type, message, price)
    """
    alerts = []
    tf = position.tf_reference
    if tf not in data or data[tf] is None or data[tf].empty:
        return alerts

    df = data[tf]
    last = df.iloc[-1]
    current_price = float(last["Close"])

    # 1. Variação contra a posição (>3%)
    if position.direction == "COMPRA":
        pct_change = (current_price - position.entry_price) / position.entry_price
        if pct_change < -0.03:
            alerts.append(("preco_contra", f"Preço caiu {abs(pct_change):.2%} abaixo da entrada", current_price))
    else:  # VENDA
        pct_change = (position.entry_price - current_price) / position.entry_price
        if pct_change < -0.03:
            alerts.append(("preco_contra", f"Preço subiu {abs(pct_change):.2%} acima da entrada", current_price))

    # 2. Stop Loss (se definido)
    if position.stop_loss:
        if position.direction == "COMPRA" and current_price <= position.stop_loss:
            alerts.append(("stop_loss", f"Stop Loss acionado em {current_price:.5f}", current_price))
        elif position.direction == "VENDA" and current_price >= position.stop_loss:
            alerts.append(("stop_loss", f"Stop Loss acionado em {current_price:.5f}", current_price))

    # 3. Take Profit (se definido)
    if position.take_profit:
        if position.direction == "COMPRA" and current_price >= position.take_profit:
            alerts.append(("take_profit", f"Take Profit acionado em {current_price:.5f}", current_price))
        elif position.direction == "VENDA" and current_price <= position.take_profit:
            alerts.append(("take_profit", f"Take Profit acionado em {current_price:.5f}", current_price))

    # 4. RSI canal (toque no topo para compra / fundo para venda)
    if "RSI" in last and "RSI_Upper" in last and "RSI_Lower" in last:
        rsi = float(last["RSI"])
        upper = float(last["RSI_Upper"])
        lower = float(last["RSI_Lower"])
        if position.direction == "COMPRA":
            if rsi >= upper:
                alerts.append(("rsi_topo", f"RSI tocou topo do canal ({rsi:.1f} >= {upper:.1f})", current_price))
        else:
            if rsi <= lower:
                alerts.append(("rsi_fundo", f"RSI tocou fundo do canal ({rsi:.1f} <= {lower:.1f})", current_price))

    # 5. StochRSI (sobrecompra para compra / sobrevenda para venda)
    if "StochRSI_D" in last:
        d = float(last["StochRSI_D"])
        if position.direction == "COMPRA":
            if d >= 80:
                alerts.append(("stoch_sobrecompra", f"StochRSI entrou em sobrecompra ({d:.1f} >= 80)", current_price))
            # Opcional: alerta de saída da sobrecompra (quando cruza abaixo de 80) – exigiria estado anterior
        else:
            if d <= 20:
                alerts.append(("stoch_sobrevenda", f"StochRSI entrou em sobrevenda ({d:.1f} <= 20)", current_price))

    return alerts


def run_monitoring_cycle(positions: List[Position], fetch_data_func, send_alert_func, play_sound_func, logger=None):
    """
    Executa um ciclo de monitoramento para todas as posições abertas.
    fetch_data_func: função que recebe symbol e retorna dict de DataFrames multi-TF
    send_alert_func: função(symbol, direction, message, price, token, chat_id, ...)
    play_sound_func: função(symbol, direction, "SAIDA")
    """
    if not positions:
        return

    # Carregar configurações do Telegram (do trading_system) – como não temos acesso direto, usaremos st.session_state
    # Para simplificar, assumimos que st.session_state.tg_token e st.session_state.tg_chat_id estão disponíveis.
    # Quem chama esta função deve garantir que os valores estejam em st.session_state.
    token = st.session_state.get("tg_token", "")
    chat_id = st.session_state.get("tg_chat_id", "")

    for pos in positions[:]:  # cópia para permitir remoção
        try:
            data = fetch_data_func(pos.symbol)
            if not data:
                continue

            alerts = check_exit_conditions(pos, data)
            for alert_type, msg, price in alerts:
                alert_key = f"{pos.symbol}_{alert_type}"
                if alert_key not in pos.alerts_sent:
                    # Enviar alerta
                    if token and chat_id:
                        send_alert_func(
                            pos.symbol, pos.direction, "SAIDA", price,
                            token, chat_id,
                            touch_tfs=[pos.tf_reference.upper()],
                            stoch_div=(alert_type.startswith("stoch")),
                            mn_ema_div=False,
                            div_grade=None,
                            vol_ratio=None,
                            vol_high=False,
                            atr_low=False,
                            elevated=False,
                            adx_weak=False
                        )
                    if play_sound_func:
                        play_sound_func(pos.symbol, pos.direction, "SAIDA")

                    # Registrar no log
                    save_alert_log({
                        "timestamp": datetime.now().isoformat(),
                        "symbol": pos.symbol,
                        "direction": pos.direction,
                        "alert_type": alert_type,
                        "message": msg,
                        "price": price,
                        "entry_price": pos.entry_price
                    })

                    pos.alerts_sent.append(alert_key)
                    save_positions(positions)

                    # Se for stop_loss ou take_profit, podemos opcionalmente fechar a posição automaticamente
                    if alert_type in ("stop_loss", "take_profit"):
                        if logger:
                            logger.info(f"[MONITOR] Posição {pos.symbol} {pos.direction} fechada por {alert_type}")
                        positions.remove(pos)
                        save_positions(positions)
                        break  # sair do loop pois pos foi removida

        except Exception as e:
            if logger:
                logger.error(f"[MONITOR] Erro ao verificar {pos.symbol}: {e}")


def add_position(symbol: str, direction: str, entry_price: float, tf_reference: str = "4h",
                 stop_loss: float = None, take_profit: float = None) -> bool:
    """Adiciona uma nova posição à lista."""
    positions = load_positions()
    # Evitar duplicatas do mesmo símbolo/direção abertas (opcional)
    for p in positions:
        if p.symbol == symbol and p.direction == direction and p.entry_time.split("T")[0] == datetime.now().strftime("%Y-%m-%d"):
            return False
    new_pos = Position(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        entry_time=datetime.now().isoformat(),
        tf_reference=tf_reference,
        stop_loss=stop_loss,
        take_profit=take_profit
    )
    positions.append(new_pos)
    save_positions(positions)
    return True


def remove_position(index: int):
    """Remove posição pelo índice na lista carregada."""
    positions = load_positions()
    if 0 <= index < len(positions):
        positions.pop(index)
        save_positions(positions)
        return True
    return False


def get_positions_summary():
    """Retorna lista de posições para exibição."""
    return load_positions()
