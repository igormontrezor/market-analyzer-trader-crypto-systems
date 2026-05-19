"""
MONTREZOR PORTFOLIO TAB
=======================
Arquivo separado — não altera app.py nem qualquer lógica existente.

Funcionalidades:
  1. Busca nome e preço em tempo real via CoinGecko
  2. Alavancagem (futuros)
  3. Margem investida → tamanho real da posição
  4. Corretora
  5. Alerta pré-compra quando sinal der BUY
  6. Botão "Comprei" → monitoramento com ROE, lucro financeiro, margem
  7. Alerta de venda quando sinal der SELL
  8. DCA: preço médio recalculado em novas entradas, delete/edit, saldo dolarizado
  9. Telegram + visual
  10. Gráficos: pizza de alocação + linha de evolução do patrimônio
  11. Preço de liquidação estimado + alerta de emergência

Como usar em app.py (2 linhas, sem alterar nada):
    from portfolio_tab import render_portfolio_tab
    # dentro da nova tab:
    render_portfolio_tab(macro_signal=current_gems_signal)
    # macro_signal: string tipo "SUPER_BUY","BUY","SELL","SUPER_SELL" ou None
"""

import streamlit as st
import pandas as pd
import numpy as np
import json, os, html, requests, time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Persistência ──────────────────────────────────────────────────────────────
_PORT_FILE  = os.path.join(os.path.expanduser("~"), ".montrezor_portfolio.json")
_TG_CFG     = os.path.join(os.path.expanduser("~"), ".montrezor_telegram.json")

# Alertas de liquidação — quanto % acima do preço liq para disparar
LIQ_WARN_PCT = 0.10   # alerta quando preço está a 10% do preço de liquidação

# ── Telegram ──────────────────────────────────────────────────────────────────
def _load_tg():
    try:
        if os.path.exists(_TG_CFG):
            c = json.load(open(_TG_CFG, encoding="utf-8"))
            return c.get("token","").strip(), str(c.get("chat_id","")).strip()
    except Exception: pass
    return "", ""

def _send_tg(msg: str):
    token, chat_id = _load_tg()
    if not token or not chat_id: return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r   = requests.post(url, json={"chat_id":chat_id,"text":msg,"parse_mode":"HTML"}, timeout=10)
        if r.status_code == 200: return True
        # plain fallback
        requests.post(url, json={"chat_id":chat_id,"text":msg}, timeout=10)
        return False
    except Exception: return False

# ── CoinGecko ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _fetch_price(coin_id: str) -> dict:
    """Busca nome e preço atual via CoinGecko. Retorna {"name","symbol","price","change_24h"}."""
    try:
        url  = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower()}"
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return {}
        d    = resp.json()
        md   = d.get("market_data",{})
        return {
            "name":       d.get("name",""),
            "symbol":     d.get("symbol","").upper(),
            "price":      float(md.get("current_price",{}).get("usd",0)),
            "change_24h": float(md.get("price_change_percentage_24h") or 0),
        }
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def _search_coin(query: str) -> list:
    """Busca coins pelo nome/símbolo. Retorna lista de {"id","name","symbol"}."""
    try:
        url  = "https://api.coingecko.com/api/v3/search"
        resp = requests.get(url, params={"query":query}, timeout=8)
        if resp.status_code != 200: return []
        return [{"id":c["id"],"name":c["name"],"symbol":c["symbol"].upper()}
                for c in resp.json().get("coins",[])[:8]]
    except Exception: return []

# ── Persistência do portfólio ─────────────────────────────────────────────────
def _load_port() -> dict:
    try:
        if os.path.exists(_PORT_FILE):
            return json.load(open(_PORT_FILE, encoding="utf-8"))
    except Exception: pass
    return {"positions":[], "cash_usd":0.0, "equity_history":[]}

def _save_port(data: dict):
    try:
        json.dump(data, open(_PORT_FILE,"w",encoding="utf-8"), indent=2, default=str)
    except Exception: pass

# ── Cálculos ──────────────────────────────────────────────────────────────────
def _calc_liq_price(entry: float, leverage: float, direction: str = "LONG") -> float:
    """
    Estimativa de preço de liquidação (margem inicial, sem funding).
    LONG:  liq = entry * (1 - 1/leverage + manut_margin)
    SHORT: liq = entry * (1 + 1/leverage - manut_margin)
    Usa 0.5% de margem de manutenção (padrão Binance/Bybit).
    """
    mm = 0.005  # 0.5% maintenance margin
    if direction == "LONG":
        return round(entry * (1 - 1/leverage + mm), 6)
    else:
        return round(entry * (1 + 1/leverage - mm), 6)

def _calc_roe(entry_avg: float, current: float, leverage: float,
              direction: str = "LONG") -> float:
    """ROE % = ((current - entry) / entry) * leverage * 100  para LONG."""
    if entry_avg == 0: return 0.0
    pct = (current - entry_avg) / entry_avg
    if direction == "SHORT": pct = -pct
    return round(pct * leverage * 100, 2)

def _calc_pnl(entry_avg: float, current: float, position_size: float,
              direction: str = "LONG") -> float:
    """P&L financeiro em USD."""
    if direction == "LONG":
        return round((current - entry_avg) * position_size, 2)
    return round((entry_avg - current) * position_size, 2)

# ── Render principal ──────────────────────────────────────────────────────────
def render_portfolio_tab(macro_signal: str = None):
    """
    Renderiza a aba de portfólio.
    macro_signal: sinal atual do sistema ("SUPER_BUY","BUY","SELL","SUPER_SELL",None)
    """
    port = _load_port()
    positions = port.get("positions", [])
    cash      = float(port.get("cash_usd", 0.0))
    eq_hist   = port.get("equity_history", [])

    is_buy_signal  = macro_signal in ("SUPER_BUY","BUY")
    is_sell_signal = macro_signal in ("SUPER_SELL","SELL")

    # ── Header com resumo financeiro ─────────────────────────────────────────
    st.markdown(
        "<div style='font-size:12px;font-weight:700;color:#8b949e;"
        "letter-spacing:.8px;text-transform:uppercase;margin-bottom:12px'>"
        "💼 PORTFÓLIO DE FUTUROS</div>",
        unsafe_allow_html=True)

    # Calcular totais com preços atuais
    total_invested = 0.0
    positions_enriched = []
    for pos in positions:
        if pos.get("status") != "OPEN": continue
        cg    = _fetch_price(pos["coin_id"])
        price = cg.get("price", pos.get("entry_avg", 0))
        pos_size = float(pos.get("position_size", 0))
        entry    = float(pos.get("entry_avg", 0))
        lev      = float(pos.get("leverage", 1))
        margin   = float(pos.get("total_margin", 0))
        direction= pos.get("direction","LONG")

        roe     = _calc_roe(entry, price, lev, direction)
        pnl     = _calc_pnl(entry, price, pos_size, direction)
        liq_px  = _calc_liq_price(entry, lev, direction)
        near_liq= (abs(price - liq_px) / price) < LIQ_WARN_PCT if price > 0 else False

        total_invested += margin
        positions_enriched.append({**pos,
            "current_price": price,
            "roe": roe, "pnl": pnl,
            "liq_price": liq_px,
            "near_liq": near_liq,
            "name": cg.get("name", pos.get("coin_id","")),
            "change_24h": cg.get("change_24h", 0),
        })

        # Alerta de liquidação via Telegram (uma vez por posição)
        if near_liq:
            liq_key = f"liq_alerted_{pos['coin_id']}"
            if not st.session_state.get(liq_key):
                msg = (f"🚨 <b>ALERTA DE LIQUIDAÇÃO</b>\n"
                       f"<b>{pos['coin_id'].upper()}</b> — preço a {LIQ_WARN_PCT*100:.0f}% da liquidação!\n"
                       f"Preço atual: ${price:,.4f}\n"
                       f"Preço liq.: ${liq_px:,.4f}\n"
                       f"Alavancagem: {lev}x | Margem: ${margin:,.2f}\n\n"
                       "⚠️ Montrezor Portfolio")
                _send_tg(msg)
                st.session_state[liq_key] = True

    total_equity = cash + total_invested + sum(p["pnl"] for p in positions_enriched)

    # Registrar histórico de equity
    if eq_hist and str(pd.Timestamp.now())[:10] != eq_hist[-1].get("date","")[:10]:
        eq_hist.append({"date": str(pd.Timestamp.now())[:10], "equity": total_equity})
        port["equity_history"] = eq_hist[-180:]
    elif not eq_hist:
        eq_hist.append({"date": str(pd.Timestamp.now())[:10], "equity": total_equity})
        port["equity_history"] = eq_hist

    # Cards de resumo
    c1,c2,c3 = st.columns(3)
    c1.metric("💵 Dolarizado (livre)", f"${cash:,.2f}")
    c2.metric("📊 Investido (posições)", f"${total_invested:,.2f}")
    c3.metric("🏦 Patrimônio Total", f"${total_equity:,.2f}",
              delta=f"${total_equity - cash - total_invested:+,.2f} P&L aberto")

    st.markdown("---")

    # ── Alerta de sinal do sistema ────────────────────────────────────────────
    if macro_signal:
        clr  = "#3fb950" if is_buy_signal else "#f85149"
        icon = "📈" if is_buy_signal else "📉"
        label= "SINAL DE COMPRA ATIVO" if is_buy_signal else "SINAL DE VENDA ATIVO"
        st.markdown(
            f"<div style='background:{clr}22;border:1px solid {clr};border-radius:8px;"
            f"padding:10px 16px;margin-bottom:16px;font-size:13px;color:{clr};font-weight:600'>"
            f"{icon} {label} — {macro_signal}</div>",
            unsafe_allow_html=True)

        # Alerta de venda nas posições abertas
        if is_sell_signal and positions_enriched:
            for pos in positions_enriched:
                sell_key = f"sell_alerted_{pos['coin_id']}_{macro_signal}"
                if not st.session_state.get(sell_key):
                    msg = (f"🔴 <b>SINAL DE VENDA — {pos['coin_id'].upper()}</b>\n"
                           f"Sinal: {macro_signal}\n"
                           f"Preço atual: ${pos['current_price']:,.4f}\n"
                           f"Entrada média: ${pos['entry_avg']:,.4f}\n"
                           f"ROE: {pos['roe']:+.2f}% | P&L: ${pos['pnl']:+,.2f}\n"
                           f"Alavancagem: {pos['leverage']}x | Margem: ${pos['total_margin']:,.2f}\n"
                           f"Corretora: {pos.get('exchange','')}\n\n"
                           "Montrezor Portfolio")
                    _send_tg(msg)
                    st.session_state[sell_key] = True

    # ── Tabs internas ─────────────────────────────────────────────────────────
    pt1, pt2, pt3 = st.tabs(["📋 Posições", "➕ Adicionar Ativo", "📈 Gráficos"])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — POSIÇÕES ABERTAS
    # ════════════════════════════════════════════════════════════════════════
    with pt1:
        if not positions_enriched:
            st.info("Nenhuma posição aberta. Adicione ativos na aba '➕ Adicionar Ativo'.")
        else:
            for i, pos in enumerate(positions_enriched):
                roe_clr   = "#3fb950" if pos["roe"] >= 0 else "#f85149"
                liq_warn  = "🚨 " if pos["near_liq"] else ""
                ch24_icon = "▲" if pos["change_24h"] >= 0 else "▼"

                with st.expander(
                    f"{liq_warn}**{pos['coin_id'].upper()}** — {pos.get('name','')} | "
                    f"ROE: {pos['roe']:+.2f}% | P&L: ${pos['pnl']:+,.2f}",
                    expanded=pos["near_liq"]
                ):
                    col_l, col_r = st.columns([3,2])
                    with col_l:
                        st.markdown(f"""
<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;font-size:12px;'>
  <div style='font-size:15px;font-weight:700;color:#e6edf3;margin-bottom:10px;font-family:JetBrains Mono,monospace'>
    {pos['coin_id'].upper()} &nbsp;<span style='font-size:11px;color:#8b949e'>{pos.get('exchange','')}</span>
  </div>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;'>
    <div><span style='color:#8b949e'>Preço atual</span><br><b style='color:#e6edf3'>${pos['current_price']:,.4f}</b>
         <span style='color:{"#3fb950" if pos["change_24h"]>=0 else "#f85149"};font-size:11px;margin-left:4px'>{ch24_icon} {pos["change_24h"]:+.2f}%</span></div>
    <div><span style='color:#8b949e'>Entrada média</span><br><b style='color:#e6edf3'>${pos['entry_avg']:,.4f}</b></div>
    <div><span style='color:#8b949e'>ROE</span><br><b style='color:{roe_clr};font-size:15px'>{pos['roe']:+.2f}%</b></div>
    <div><span style='color:#8b949e'>P&L (USD)</span><br><b style='color:{roe_clr}'>${pos['pnl']:+,.2f}</b></div>
    <div><span style='color:#8b949e'>Alavancagem</span><br><b style='color:#e6edf3'>{pos['leverage']}x</b></div>
    <div><span style='color:#8b949e'>Margem</span><br><b style='color:#e6edf3'>${pos['total_margin']:,.2f}</b></div>
    <div><span style='color:#8b949e'>Posição real</span><br><b style='color:#e6edf3'>${pos['position_size'] * pos['current_price']:,.2f}</b></div>
    <div><span style='color:#8b949e'>Direção</span><br><b style='color:#e6edf3'>{pos.get('direction','LONG')}</b></div>
  </div>
  <div style='margin-top:10px;padding-top:8px;border-top:1px solid #21262d;'>
    <span style='color:{"#f85149" if pos["near_liq"] else "#8b949e"}'>
      {"🚨 " if pos["near_liq"] else ""}Liq. estimado: <b>${pos['liq_price']:,.4f}</b>
      {"  — ZONA DE PERIGO!" if pos["near_liq"] else ""}
    </span>
  </div>
</div>""", unsafe_allow_html=True)

                    with col_r:
                        st.markdown("**Ações**")

                        # ── DCA: nova entrada ──
                        with st.form(key=f"dca_{pos['coin_id']}_{i}"):
                            st.markdown("**📥 Nova entrada (DCA)**")
                            new_margin = st.number_input("Margem adicional ($)", 0.0, key=f"dca_margin_{i}")
                            new_lev    = st.number_input("Alavancagem nova", 1.0, 125.0,
                                                          float(pos['leverage']), key=f"dca_lev_{i}")
                            new_price  = st.number_input("Preço de entrada ($)",
                                                          float(pos['current_price']),
                                                          key=f"dca_price_{i}")
                            if st.form_submit_button("✅ Registrar DCA"):
                                if new_margin > 0 and new_price > 0:
                                    # Recalcular preço médio ponderado
                                    old_size = float(pos['position_size'])
                                    new_size = (new_margin * new_lev) / new_price
                                    total_sz = old_size + new_size
                                    avg_entry = ((old_size * float(pos['entry_avg'])) +
                                                 (new_size * new_price)) / total_sz if total_sz > 0 else new_price
                                    # Atualizar posição
                                    for p in port["positions"]:
                                        if p["coin_id"] == pos["coin_id"] and p["status"] == "OPEN":
                                            p["entry_avg"]     = round(avg_entry, 6)
                                            p["position_size"] = round(total_sz, 8)
                                            p["total_margin"]  = round(float(p["total_margin"]) + new_margin, 2)
                                            p["leverage"]      = round(new_lev, 1)
                                            p.setdefault("entries",[]).append({
                                                "date": str(pd.Timestamp.now())[:16],
                                                "price": new_price, "margin": new_margin, "leverage": new_lev
                                            })
                                    _save_port(port)
                                    st.success(f"DCA registrado! Novo preço médio: ${avg_entry:,.4f}")
                                    st.rerun()

                        # ── Confirmar venda ──
                        with st.form(key=f"sell_{pos['coin_id']}_{i}"):
                            st.markdown("**💰 Confirmar Venda**")
                            sell_price = st.number_input("Preço de saída ($)",
                                                          float(pos['current_price']),
                                                          key=f"sell_price_{i}")
                            if st.form_submit_button("✅ Vendi"):
                                size = float(pos['position_size'])
                                entry= float(pos['entry_avg'])
                                direction = pos.get("direction","LONG")
                                realized  = _calc_pnl(entry, sell_price, size, direction)
                                returned  = float(pos['total_margin']) + realized
                                port["cash_usd"] = round(float(port["cash_usd"]) + returned, 2)
                                for p in port["positions"]:
                                    if p["coin_id"] == pos["coin_id"] and p["status"] == "OPEN":
                                        p["status"]     = "CLOSED"
                                        p["exit_price"] = sell_price
                                        p["realized_pnl"]= realized
                                        p["closed_at"]  = str(pd.Timestamp.now())[:16]
                                _save_port(port)
                                msg = (f"💰 <b>VENDA CONFIRMADA — {pos['coin_id'].upper()}</b>\n"
                                       f"Saída: ${sell_price:,.4f}\n"
                                       f"Entrada média: ${entry:,.4f}\n"
                                       f"P&L realizado: ${realized:+,.2f}\n"
                                       f"Retorno total: ${returned:,.2f}\n"
                                       f"Saldo dolarizado novo: ${port['cash_usd']:,.2f}\n\n"
                                       "Montrezor Portfolio")
                                _send_tg(msg)
                                st.success(f"Venda registrada! P&L: ${realized:+,.2f}")
                                st.rerun()

                        # ── Deletar posição ──
                        col_e, col_d = st.columns(2)
                        with col_d:
                            if st.button("🗑 Deletar", key=f"del_{pos['coin_id']}_{i}"):
                                port["positions"] = [
                                    p for p in port["positions"]
                                    if not (p["coin_id"] == pos["coin_id"] and p["status"] == "OPEN")
                                ]
                                _save_port(port)
                                st.rerun()

        # ── Saldo dolarizado ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**💵 Saldo Dolarizado (caixa)**")
        col_cash1, col_cash2 = st.columns([2,1])
        with col_cash1:
            st.metric("Disponível", f"${port['cash_usd']:,.2f}")
        with col_cash2:
            with st.form("add_cash"):
                add_amt = st.number_input("Adicionar/remover ($)", value=0.0, key="add_cash_val")
                if st.form_submit_button("Atualizar"):
                    port["cash_usd"] = round(float(port["cash_usd"]) + add_amt, 2)
                    _save_port(port)
                    st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — ADICIONAR ATIVO
    # ════════════════════════════════════════════════════════════════════════
    with pt2:
        st.markdown("#### ➕ Adicionar Ativo ao Portfólio")

        # Busca CoinGecko
        query = st.text_input("Buscar ativo (nome ou símbolo)", placeholder="bitcoin, eth, sol...",
                               key="port_search")
        coin_id = ""
        coin_name = ""
        coin_price = 0.0

        if query and len(query) >= 2:
            results = _search_coin(query)
            if results:
                options = {f"{r['name']} ({r['symbol']}) — id: {r['id']}": r['id'] for r in results}
                chosen  = st.selectbox("Selecione o ativo:", list(options.keys()), key="port_coin_sel")
                coin_id = options[chosen]
                cg_data = _fetch_price(coin_id)
                coin_name  = cg_data.get("name", coin_id)
                coin_price = cg_data.get("price", 0)
                ch24       = cg_data.get("change_24h", 0)
                if coin_price:
                    st.markdown(
                        f"<div style='background:#161b22;border:1px solid #30363d;"
                        f"border-radius:6px;padding:10px 14px;font-size:13px;margin-bottom:8px'>"
                        f"<b style='color:#e6edf3'>{coin_name}</b> &nbsp;"
                        f"<b style='color:#58a6ff'>${coin_price:,.4f}</b> &nbsp;"
                        f"<span style='color:{'#3fb950' if ch24>=0 else '#f85149'}'>"
                        f"{'▲' if ch24>=0 else '▼'} {ch24:+.2f}% 24h</span></div>",
                        unsafe_allow_html=True)

        with st.form("add_position"):
            col1, col2 = st.columns(2)
            with col1:
                direction  = st.selectbox("Direção", ["LONG","SHORT"], key="port_dir")
                leverage   = st.number_input("Alavancagem", 1.0, 125.0, 10.0, 1.0, key="port_lev")
                margin     = st.number_input("Margem ($)", 0.0, key="port_margin")
            with col2:
                entry_price= st.number_input("Preço de entrada ($)",
                                              float(coin_price) if coin_price else 0.0,
                                              key="port_entry")
                exchange   = st.text_input("Corretora", placeholder="Binance, Bybit...", key="port_exc")
                notes      = st.text_input("Notas (opcional)", key="port_notes")

            submitted = st.form_submit_button("➕ Adicionar ao Portfólio", type="primary")
            if submitted:
                if not coin_id:
                    st.error("Busque e selecione um ativo primeiro.")
                elif margin <= 0 or entry_price <= 0:
                    st.error("Margem e preço de entrada devem ser > 0.")
                else:
                    pos_size  = (margin * leverage) / entry_price
                    liq_price = _calc_liq_price(entry_price, leverage, direction)
                    new_pos   = {
                        "coin_id":       coin_id,
                        "name":          coin_name,
                        "direction":     direction,
                        "leverage":      leverage,
                        "total_margin":  margin,
                        "position_size": round(pos_size, 8),
                        "entry_avg":     entry_price,
                        "exchange":      exchange,
                        "notes":         notes,
                        "status":        "OPEN",
                        "opened_at":     str(pd.Timestamp.now())[:16],
                        "entries":       [{"date": str(pd.Timestamp.now())[:16],
                                           "price": entry_price,
                                           "margin": margin,
                                           "leverage": leverage}],
                    }
                    port["positions"].append(new_pos)
                    _save_port(port)

                    # Alerta Telegram pré-compra
                    msg = (f"📋 <b>NOVO ATIVO ADICIONADO</b>\n"
                           f"<b>{coin_name.upper()} ({coin_id})</b>\n"
                           f"Direção: {direction} | Alavancagem: {leverage}x\n"
                           f"Entrada: ${entry_price:,.4f}\n"
                           f"Margem: ${margin:,.2f} | Posição: ${margin*leverage:,.2f}\n"
                           f"Liq. estimado: ${liq_price:,.4f}\n"
                           f"Corretora: {exchange}\n"
                           f"Sinal macro atual: {macro_signal or 'Nenhum'}\n\n"
                           "Montrezor Portfolio")
                    _send_tg(msg)
                    st.success(f"✅ {coin_name} adicionado! Liq. est.: ${liq_price:,.4f}")
                    st.rerun()

        # ── Lista de interesse (watchlist pré-compra) ─────────────────────────
        st.markdown("---")
        st.markdown("**👀 Lista de Interesse (alerta pré-compra)**")
        st.markdown("<div style='color:#8b949e;font-size:12px;margin-bottom:8px'>"
                    "Ativos que você quer comprar quando o sinal aparecer. "
                    "Quando o sistema der BUY/SUPER_BUY, aparece um alerta com o setup.</div>",
                    unsafe_allow_html=True)

        watchlist = port.get("watchlist", [])
        with st.form("add_watch"):
            w_coin  = st.text_input("CoinGecko ID", placeholder="bitcoin", key="w_coin")
            w_lev   = st.number_input("Alavancagem planejada", 1.0, 125.0, 10.0, key="w_lev")
            w_margin= st.number_input("Margem planejada ($)", 0.0, key="w_margin")
            w_exc   = st.text_input("Corretora", key="w_exc")
            if st.form_submit_button("Adicionar à lista"):
                if w_coin:
                    watchlist.append({"coin_id":w_coin,"leverage":w_lev,
                                      "margin":w_margin,"exchange":w_exc})
                    port["watchlist"] = watchlist
                    _save_port(port)
                    st.rerun()

        if watchlist:
            for wi, witem in enumerate(watchlist):
                wcg  = _fetch_price(witem["coin_id"])
                wpx  = wcg.get("price", 0)
                wliq = _calc_liq_price(wpx, witem["leverage"]) if wpx else 0
                col_w, col_wd = st.columns([5,1])
                with col_w:
                    alert_html = ""
                    if is_buy_signal:
                        alert_html = ("<span style='background:#3fb95022;border:1px solid #3fb950;"
                                      "border-radius:4px;padding:2px 6px;font-size:11px;color:#3fb950;"
                                      "margin-left:8px'>📈 SINAL ATIVO!</span>")
                        # Alerta Telegram pré-compra
                        pre_key = f"pre_buy_{witem['coin_id']}_{macro_signal}"
                        if not st.session_state.get(pre_key):
                            msg = (f"📈 <b>ALERTA PRÉ-COMPRA — {witem['coin_id'].upper()}</b>\n"
                                   f"Sinal: {macro_signal}\n"
                                   f"Preço atual: ${wpx:,.4f}\n"
                                   f"Setup planejado: {witem['leverage']}x alavancagem\n"
                                   f"Margem: ${witem['margin']:,.2f} → Posição: ${witem['margin']*witem['leverage']:,.2f}\n"
                                   f"Liq. est.: ${wliq:,.4f}\n"
                                   f"Corretora: {witem.get('exchange','')}\n\n"
                                   "Montrezor Portfolio")
                            _send_tg(msg)
                            st.session_state[pre_key] = True

                    st.markdown(
                        f"<div style='padding:6px 2px;font-size:13px;color:#c9d1d9'>"
                        f"<b>{witem['coin_id'].upper()}</b>"
                        f"<span style='color:#8b949e'> {witem['leverage']}x · "
                        f"${witem['margin']:.0f} · {witem.get('exchange','')}"
                        f"{'  •  $' + f'{wpx:,.4f}' if wpx else ''}</span>"
                        f"{alert_html}</div>",
                        unsafe_allow_html=True)
                with col_wd:
                    if st.button("✕", key=f"del_w_{wi}"):
                        port["watchlist"] = [w for j,w in enumerate(watchlist) if j != wi]
                        _save_port(port)
                        st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — GRÁFICOS
    # ════════════════════════════════════════════════════════════════════════
    with pt3:
        if not positions_enriched and cash == 0:
            st.info("Adicione posições para ver os gráficos.")
        else:
            g1, g2 = st.columns(2)

            # ── Pizza: alocação por ativo ─────────────────────────────────────
            with g1:
                labels  = []
                values  = []
                if cash > 0:
                    labels.append("💵 Dolarizado")
                    values.append(cash)
                for pos in positions_enriched:
                    labels.append(pos["coin_id"].upper())
                    values.append(float(pos["total_margin"]))

                if labels:
                    fig_pie = go.Figure(go.Pie(
                        labels=labels, values=values,
                        hole=0.45,
                        textinfo='label+percent',
                        marker=dict(colors=['#3fb950','#58a6ff','#f78166',
                                            '#d2a8ff','#ffa657','#79c0ff',
                                            '#56d364','#ff7b72'][:len(labels)]),
                    ))
                    fig_pie.update_layout(
                        title="Alocação do Portfólio",
                        height=320,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#8b949e', size=11),
                        margin=dict(l=0,r=0,t=36,b=0),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

            # ── Linha: evolução do patrimônio ─────────────────────────────────
            with g2:
                if len(eq_hist) >= 2:
                    eq_df = pd.DataFrame(eq_hist)
                    fig_eq = go.Figure(go.Scatter(
                        x=eq_df["date"], y=eq_df["equity"],
                        mode='lines+markers',
                        line=dict(color='#3fb950', width=2),
                        marker=dict(size=4),
                        fill='tozeroy',
                        fillcolor='rgba(63,185,80,0.08)',
                        name='Patrimônio (USD)',
                    ))
                    fig_eq.update_layout(
                        title="Evolução do Patrimônio (USD)",
                        height=320,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#8b949e', size=11),
                        margin=dict(l=0,r=0,t=36,b=0),
                    )
                    fig_eq.update_xaxes(gridcolor='#21262d')
                    fig_eq.update_yaxes(gridcolor='#21262d')
                    st.plotly_chart(fig_eq, use_container_width=True)
                else:
                    st.info("Histórico insuficiente para o gráfico de evolução (mín. 2 dias).")

            # ── Tabela ROE por posição ────────────────────────────────────────
            if positions_enriched:
                st.markdown("**📊 ROE por Posição**")
                rows = []
                for pos in positions_enriched:
                    rows.append({
                        "Ativo":      pos["coin_id"].upper(),
                        "Entrada":    f"${pos['entry_avg']:,.4f}",
                        "Atual":      f"${pos['current_price']:,.4f}",
                        "ROE":        f"{pos['roe']:+.2f}%",
                        "P&L":        f"${pos['pnl']:+,.2f}",
                        "Lev":        f"{pos['leverage']}x",
                        "Margem":     f"${pos['total_margin']:,.2f}",
                        "Liq. Est.":  f"${pos['liq_price']:,.4f}",
                        "⚠️":         "🚨" if pos["near_liq"] else "✅",
                        "Corretora":  pos.get("exchange",""),
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)

            # ── Histórico de posições fechadas ────────────────────────────────
            closed = [p for p in port.get("positions",[]) if p.get("status")=="CLOSED"]
            if closed:
                with st.expander(f"📋 Histórico de posições fechadas ({len(closed)})", expanded=False):
                    crows = [{
                        "Ativo":    p["coin_id"].upper(),
                        "Entrada":  f"${p.get('entry_avg',0):,.4f}",
                        "Saída":    f"${p.get('exit_price',0):,.4f}",
                        "P&L":      f"${p.get('realized_pnl',0):+,.2f}",
                        "Margem":   f"${p.get('total_margin',0):,.2f}",
                        "Fechado":  p.get("closed_at",""),
                    } for p in closed]
                    st.dataframe(crows, use_container_width=True, hide_index=True)

    # Salvar equity history atualizado
    port["equity_history"] = eq_hist
    _save_port(port)
