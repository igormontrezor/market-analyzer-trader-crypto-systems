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

_PRICE_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_price_cache.json")
_PRICE_CACHE_TTL = 300  # 5 minutos

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

def _load_price_cache() -> dict:
    try:
        with open(_PRICE_CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def _save_price_cache(cache: dict):
    try:
        with open(_PRICE_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except:
        pass

def _fetch_price(coin_id: str, use_cache: bool = True) -> dict:
    """Busca nome e preço com cache persistente e retry em caso de 429."""
    cache = _load_price_cache()
    now = time.time()

    # Se cache válido e uso permitido, retorna
    if use_cache and coin_id in cache:
        entry = cache[coin_id]
        if (now - entry.get("ts", 0)) < _PRICE_CACHE_TTL:
            return entry.get("data", {})

    # Fetch com retry
    for attempt in range(3):
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower()}"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                d = resp.json()
                md = d.get("market_data", {})
                data = {
                    "name":       d.get("name", ""),
                    "symbol":     d.get("symbol", "").upper(),
                    "price":      float(md.get("current_price", {}).get("usd", 0)),
                    "change_24h": float(md.get("price_change_percentage_24h") or 0),
                }
                # Atualiza cache
                cache[coin_id] = {"ts": now, "data": data}
                _save_price_cache(cache)
                return data
            elif resp.status_code == 429:
                wait = (2 ** attempt)  # 1, 2, 4 segundos
                time.sleep(wait)
                continue
            else:
                # Outro erro, para de tentar
                break
        except Exception:
            if attempt == 2:
                break
            time.sleep(1)
    # Fallback: retorna cache antigo se existir
    if coin_id in cache:
        return cache[coin_id].get("data", {})
    return {}

def _fetch_many_prices(coin_ids: list) -> dict:
    """
    Busca preço e variação 24h para vários coins via /simple/price.
    Retorna dicionário {coin_id: {"price": x, "change_24h": y}}.
    """
    if not coin_ids:
        return {}
    ids_str = ",".join([c.lower() for c in coin_ids])
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            result = {}
            for cid in coin_ids:
                cid_low = cid.lower()
                if cid_low in data:
                    result[cid] = {
                        "price": float(data[cid_low].get("usd", 0)),
                        "change_24h": float(data[cid_low].get("usd_24h_change", 0))
                    }
                else:
                    result[cid] = {"price": 0, "change_24h": 0}
            return result
        else:
            return {}
    except:
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
        with open(_PORT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        st.error(f"ERRO AO SALVAR PORTFÓLIO: {e}")
        import traceback
        traceback.print_exc()

def _log_tx(port: dict, tx_type: str, coin_id: str, amount: float,
            price: float = 0, pnl: float = 0, notes: str = ""):
    """
    Registra movimentação no extrato unificado.
    tx_type: DEPOSITO | SAQUE | ABERTURA | DCA | VENDA_PARCIAL | VENDA_TOTAL
    """
    port.setdefault("extrato", []).insert(0, {
        "date":    str(pd.Timestamp.now())[:16],
        "type":    tx_type,
        "coin_id": coin_id,
        "amount":  round(amount, 2),
        "price":   round(price, 6),
        "pnl":     round(pnl, 2),
        "notes":   notes,
    })
    port["extrato"] = port["extrato"][:500]

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

def update_portfolio_watchlist_prices() -> bool:
    """Atualiza preços de todos os itens da watchlist. Retorna True se algum preço mudou."""
    port = _load_port()
    watchlist = port.get("watchlist", [])
    updated = False
    for item in watchlist:
        cg = _fetch_price(item["coin_id"], use_cache=True)
        price = cg.get("price", 0)
        if price > 0:
            old_price = item.get("current_price", 0)
            if old_price != price:
                item["current_price"] = price
                item["change_24h"] = cg.get("change_24h", 0)
                updated = True
    if updated:
        _save_port(port)
    return updated

def get_portfolio_watchlist() -> list:
    """Retorna a watchlist do portfólio com preços atualizados (se disponíveis)."""
    port = _load_port()
    watchlist = port.get("watchlist", [])
    # Garantir que cada item tenha current_price e change_24h
    for item in watchlist:
        if "current_price" not in item or item.get("current_price", 0) == 0:
            cg = _fetch_price(item["coin_id"], use_cache=True)
            item["current_price"] = cg.get("price", 0)
            item["change_24h"] = cg.get("change_24h", 0)
    return watchlist

# ── Render principal ──────────────────────────────────────────────────────────
def render_portfolio_tab(macro_signal: str = None):
    """
    Renderiza a aba de portfólio.
    macro_signal: sinal atual do sistema ("SUPER_BUY","BUY","SELL","SUPER_SELL",None)
    """

    if "editing_position_index" not in st.session_state:
        st.session_state.editing_position_index = None

    port = _load_port()
    positions = port.get("positions", [])
    cash      = float(port.get("cash_usd", 0.0))
    eq_hist   = port.get("equity_history", [])

    is_buy_signal  = macro_signal in ("SUPER_BUY","BUY")
    is_sell_signal = macro_signal in ("SUPER_SELL","SELL")

    # Coletar todos os coin_ids de posições abertas e watchlist
    all_coin_ids = set()
    for pos in positions:
        if pos.get("status") == "OPEN":
            all_coin_ids.add(pos["coin_id"])
    for w in port.get("watchlist", []):
        all_coin_ids.add(w["coin_id"])

    # Buscar preços em lote e atualizar cache
    if all_coin_ids:
        batch_data = _fetch_many_prices(list(all_coin_ids))
        cache = _load_price_cache()
        now = time.time()
        for cid, data in batch_data.items():
            if data.get("price", 0) > 0:
                # Monta estrutura igual à de _fetch_price
                cached_entry = {
                    "name": cache.get(cid, {}).get("data", {}).get("name", cid.upper()),
                    "symbol": cid.upper(),
                    "price": data["price"],
                    "change_24h": data["change_24h"]
                }
                cache[cid] = {"ts": now, "data": cached_entry}
        _save_price_cache(cache)

    # ── Header com resumo financeiro ─────────────────────────────────────────
    st.markdown(
        "<div style='font-size:12px;font-weight:700;color:#8b949e;"
        "letter-spacing:.8px;text-transform:uppercase;margin-bottom:12px'>"
        "💼 PORTFÓLIO DE FUTUROS</div>",
        unsafe_allow_html=True)

    # Calcular totais — usa o cache em disco já populado pelo batch acima (zero requests extras)
    _mem_cache = _load_price_cache()

    total_invested = 0.0
    positions_enriched = []
    for pos in positions:
        if pos.get("status") != "OPEN": continue
        _cd   = _mem_cache.get(pos["coin_id"], {}).get("data", {})
        cg    = _cd if _cd else {}
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
    pt1, pt2, pt3, pt4 = st.tabs(["📋 Posições", "➕ Adicionar Ativo", "📈 Gráficos", "📒 Extrato"])

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
                                    _log_tx(port, "DCA", pos["coin_id"],
                                            new_margin, new_price, 0,
                                            f"+${new_margin:.2f} @ ${new_price:,.4f}")
                                    _save_port(port)
                                    st.success(f"DCA registrado! Novo preço médio: ${avg_entry:,.4f}")
                                    st.rerun()

                        # ── Confirmar venda (total ou parcial) ──
                        with st.form(key=f"sell_{pos['coin_id']}_{i}"):
                            st.markdown("**💰 Confirmar Venda**")
                            sell_price   = st.number_input("Preço de saída ($)",
                                                            float(pos['current_price']),
                                                            key=f"sell_price_{i}")
                            total_margin = float(pos['total_margin'])
                            sell_pct     = st.slider("% da posição a realizar",
                                                      min_value=10, max_value=100,
                                                      value=100, step=10,
                                                      key=f"sell_pct_{i}",
                                                      help="100% = venda total | < 100% = parcial (take profit)")
                            sell_frac    = sell_pct / 100.0
                            margin_real  = round(total_margin * sell_frac, 2)
                            st.caption(f"Realizando: ${margin_real:.2f} de ${total_margin:.2f} de margem")

                            if st.form_submit_button("✅ Confirmar"):
                                size      = float(pos['position_size'])
                                entry     = float(pos['entry_avg'])
                                direction = pos.get("direction","LONG")

                                sell_size = size * sell_frac
                                realized  = _calc_pnl(entry, sell_price, sell_size, direction)
                                returned  = margin_real + realized
                                port["cash_usd"] = round(float(port["cash_usd"]) + returned, 2)

                                if sell_pct == 100:
                                    # Venda total — fecha posição
                                    for p in port["positions"]:
                                        if p["coin_id"] == pos["coin_id"] and p["status"] == "OPEN":
                                            p["status"]      = "CLOSED"
                                            p["exit_price"]  = sell_price
                                            p["realized_pnl"]= realized
                                            p["closed_at"]   = str(pd.Timestamp.now())[:16]
                                    _log_tx(port, "VENDA_TOTAL", pos["coin_id"],
                                            returned, sell_price, realized,
                                            f"100% @ ${sell_price:,.4f}")
                                    tg_label = "VENDA TOTAL"
                                else:
                                    # Venda parcial — recalcula posição restante
                                    remain_frac  = 1.0 - sell_frac
                                    remain_size  = size * remain_frac
                                    remain_margin= round(total_margin * remain_frac, 2)
                                    for p in port["positions"]:
                                        if p["coin_id"] == pos["coin_id"] and p["status"] == "OPEN":
                                            p["position_size"] = round(remain_size, 8)
                                            p["total_margin"]  = remain_margin
                                            p.setdefault("partial_sales",[]).append({
                                                "date":     str(pd.Timestamp.now())[:16],
                                                "pct":      sell_pct,
                                                "price":    sell_price,
                                                "realized": realized,
                                            })
                                    _log_tx(port, "VENDA_PARCIAL", pos["coin_id"],
                                            returned, sell_price, realized,
                                            f"{sell_pct}% @ ${sell_price:,.4f}")
                                    tg_label = f"VENDA PARCIAL ({sell_pct}%)"

                                _save_port(port)
                                msg = (f"💰 <b>{tg_label} — {pos['coin_id'].upper()}</b>\n"
                                       f"Saída: ${sell_price:,.4f}\n"
                                       f"Entrada média: ${entry:,.4f}\n"
                                       f"P&L realizado: ${realized:+,.2f}\n"
                                       f"Retorno: ${returned:,.2f}\n"
                                       f"Saldo livre: ${port['cash_usd']:,.2f}\n\n"
                                       "Montrezor Portfolio")
                                _send_tg(msg)
                                st.success(f"{tg_label} — P&L: ${realized:+,.2f} | Retorno: ${returned:,.2f}")
                                st.rerun()

                        # ── Notas da operação ──
                        with st.form(key=f"notes_{pos['coin_id']}_{i}"):
                            new_note = st.text_area("📝 Notas / Tese da operação",
                                                     value=pos.get("notes",""),
                                                     height=80, key=f"note_txt_{i}")
                            if st.form_submit_button("Salvar nota"):
                                for p in port["positions"]:
                                    if p["coin_id"]==pos["coin_id"] and p["status"]=="OPEN":
                                        p["notes"] = new_note
                                _save_port(port)
                                st.success("Nota salva!")

                        # ── Deletar posição ──
                        col_e, col_d = st.columns(2)
                        with col_d:
                             if st.button("🗑 Deletar", key=f"del_{pos['coin_id']}_{i}"):
                                # Carrega o portfólio mais recente do arquivo
                                fresh_port = _load_port()
                                fresh_port["positions"] = [
                                    p for p in fresh_port["positions"]
                                    if not (p["coin_id"] == pos["coin_id"] and p.get("status") == "OPEN")
                                ]
                                _save_port(fresh_port)
                                st.success(f"Posição {pos['coin_id'].upper()} removida!")
                                st.rerun()

                        # Botão para editar
                        if st.button("✏️ Editar", key=f"edit_btn_{i}"):
                            if st.session_state.editing_position_index == i:
                                st.session_state.editing_position_index = None   # fecha
                            else:
                                st.session_state.editing_position_index = i      # abre
                            st.rerun()

                        # Formulário de edição – só aparece quando a posição está com o índice correto
                        if st.session_state.editing_position_index == i:
                            with st.form(key=f"edit_form_{i}"):
                                st.markdown("**📝 Editar posição**")

                                new_leverage = st.number_input(
                                    "Alavancagem",
                                    min_value=1.0, max_value=125.0,
                                    value=float(pos["leverage"]),
                                    step=0.5,
                                    key=f"edit_lev_{i}"
                                )
                                new_margin = st.number_input(
                                    "Margem total ($)",
                                    min_value=0.0,
                                    value=float(pos["total_margin"]),
                                    step=10.0,
                                    key=f"edit_margin_{i}"
                                )
                                new_entry = st.number_input(
                                    "Preço de entrada médio ($)",
                                    min_value=0.0,
                                    value=float(pos["entry_avg"]),
                                    format="%.6f",
                                    key=f"edit_entry_{i}"
                                )

                                st.caption("⚠️ Alterar o preço de entrada médio pode distorcer o histórico de DCA. Use com cuidado.")

                                col1, col2 = st.columns(2)
                                with col1:
                                    submitted = st.form_submit_button("💾 Salvar alterações")
                                with col2:
                                    if st.form_submit_button("❌ Cancelar"):
                                        st.session_state.editing_position_index = None
                                        st.rerun()

                                if submitted:
                                    if new_margin <= 0 or new_entry <= 0 or new_leverage <= 0:
                                        st.error("Margem, preço e alavancagem devem ser positivos.")
                                    else:
                                        # Recalcula o tamanho da posição
                                        new_position_size = (new_margin * new_leverage) / new_entry

                                        # Atualiza a posição no objeto `port` (carregado no início)
                                        for p in port["positions"]:
                                            if p["coin_id"] == pos["coin_id"] and p.get("status") == "OPEN":
                                                p["leverage"] = new_leverage
                                                p["total_margin"] = new_margin
                                                p["entry_avg"] = new_entry
                                                p["position_size"] = round(new_position_size, 8)
                                                # Registra a edição nas notas
                                                old_notes = p.get("notes", "")
                                                p["notes"] = f"{old_notes}\n[Editado em {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}] Lev:{new_leverage}x Margem:${new_margin:,.2f} Entry:${new_entry:,.4f}"
                                                break

                                        _save_port(port)
                                        st.success("Posição atualizada com sucesso!")
                                        st.session_state.editing_position_index = None
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
                    tx_type = "DEPOSITO" if add_amt >= 0 else "SAQUE"
                    port["cash_usd"] = round(float(port["cash_usd"]) + add_amt, 2)
                    _log_tx(port, tx_type, "USD", abs(add_amt), 1.0, 0,
                            f"Saldo ajustado para ${port['cash_usd']:,.2f}")
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
                cg_data = _fetch_price(coin_id, use_cache=True)
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

            # ── Risk Calculator (preview automático) ──────────────────
            if margin > 0 and entry_price > 0 and leverage > 0:
                _liq_prev   = _calc_liq_price(entry_price, leverage, direction if direction else "LONG")
                _pos_prev   = margin * leverage
                _risk_pct   = (margin / (cash + total_invested + 1)) * 100 if (cash + total_invested) > 0 else 0
                _dist_liq   = abs(entry_price - _liq_prev) / entry_price * 100
                _slots      = int((cash) / margin) if margin > 0 else 0
                _liq_clr    = "#f85149" if _dist_liq < 15 else "#ffa657" if _dist_liq < 30 else "#3fb950"
                st.markdown(
                    f"<div style='background:#0d1117;border:1px solid #21262d;"
                    f"border-radius:6px;padding:10px 14px;font-size:12px;margin-bottom:8px'>"
                    f"<b style='color:#8b949e;letter-spacing:.6px'>📊 RISK CALCULATOR</b><br><br>"
                    f"<span style='color:#8b949e'>Posição real</span>: "
                    f"<b style='color:#58a6ff'>${_pos_prev:,.2f}</b> &nbsp;·&nbsp; "
                    f"<span style='color:#8b949e'>Liq. est.</span>: "
                    f"<b style='color:{_liq_clr}'>${_liq_prev:,.4f} ({_dist_liq:.1f}% de distância)</b><br>"
                    f"<span style='color:#8b949e'>% do patrimônio</span>: "
                    f"<b style='color:{'#f85149' if _risk_pct > 20 else '#ffa657' if _risk_pct > 10 else '#3fb950'}'>"
                    f"{_risk_pct:.1f}%</b> &nbsp;·&nbsp; "
                    f"<span style='color:#8b949e'>Operações similares no caixa</span>: "
                    f"<b style='color:#e6edf3'>{_slots}x</b>"
                    f"</div>",
                    unsafe_allow_html=True)

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
                    _log_tx(port, "ABERTURA", coin_id, margin, entry_price, 0,
                            f"{direction} {leverage}x @ ${entry_price:,.4f} | {exchange}")
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
            # Grid de cards — 3 por linha
            _wcols = st.columns(min(len(watchlist), 3))
            for wi, witem in enumerate(watchlist):
                wcg     = _fetch_price(witem["coin_id"], use_cache=True)
                wpx     = wcg.get("price", 0)
                wch24   = wcg.get("change_24h", 0)
                wname   = wcg.get("name", witem["coin_id"])
                wliq    = _calc_liq_price(wpx, witem["leverage"]) if wpx else 0
                wpos    = witem["margin"] * witem["leverage"]
                # Distância % até liq
                w_dist_liq = abs(wpx - wliq) / wpx * 100 if wpx > 0 else 0
                # Risco max em $ (perda total da margem)
                w_risk_max = witem["margin"]

                # Enviar alerta Telegram se sinal ativo (uma vez por sinal)
                if is_buy_signal:
                    pre_key = f"pre_buy_{witem['coin_id']}_{macro_signal}"
                    if not st.session_state.get(pre_key):
                        msg = (f"📈 <b>ALERTA PRÉ-COMPRA — {witem['coin_id'].upper()}</b>\n"
                               f"Sinal: {macro_signal}\n"
                               f"Preço atual: ${wpx:,.4f}\n"
                               f"Setup: {witem['leverage']}x | Margem: ${witem['margin']:,.2f}\n"
                               f"Posição real: ${wpos:,.2f}\n"
                               f"Liq. est.: ${wliq:,.4f} (dist. {w_dist_liq:.1f}%)\n"
                               f"Corretora: {witem.get('exchange','')}\n\n"
                               "Montrezor Portfolio")
                        _send_tg(msg)
                        st.session_state[pre_key] = True

                # Cor de borda: verde se sinal ativo, amarelo normal
                border_clr = "#3fb950" if is_buy_signal else "#30363d"
                ch24_clr   = "#3fb950" if wch24 >= 0 else "#f85149"
                ch24_icon  = "▲" if wch24 >= 0 else "▼"
                signal_badge = (
                    "<div style='background:#3fb95022;border:1px solid #3fb950;"
                    "border-radius:4px;padding:2px 8px;font-size:11px;color:#3fb950;"
                    "text-align:center;margin-bottom:6px;font-weight:700'>📈 SINAL ATIVO!</div>"
                ) if is_buy_signal else ""

                with _wcols[wi % 3]:
                    st.markdown(
                        f"<div style='background:#161b22;border:1px solid {border_clr};"
                        f"border-radius:8px;padding:12px 14px;margin-bottom:10px;position:relative'>"
                        f"{signal_badge}"
                        f"<div style='font-size:14px;font-weight:700;color:#e6edf3;"
                        f"font-family:JetBrains Mono,monospace'>{witem['coin_id'].upper()}</div>"
                        f"<div style='font-size:11px;color:#8b949e;margin-bottom:8px'>{wname}</div>"
                        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px'>"
                        f"<div><span style='color:#8b949e'>Preço</span><br>"
                        f"<b style='color:#e6edf3'>${wpx:,.4f}</b> "
                        f"<span style='color:{ch24_clr};font-size:10px'>{ch24_icon}{wch24:+.1f}%</span></div>"
                        f"<div><span style='color:#8b949e'>Corretora</span><br>"
                        f"<b style='color:#e6edf3'>{witem.get('exchange','—')}</b></div>"
                        f"<div><span style='color:#8b949e'>Alavancagem</span><br>"
                        f"<b style='color:#e6edf3'>{witem['leverage']}x</b></div>"
                        f"<div><span style='color:#8b949e'>Margem plan.</span><br>"
                        f"<b style='color:#e6edf3'>${witem['margin']:,.2f}</b></div>"
                        f"<div><span style='color:#8b949e'>Posição real</span><br>"
                        f"<b style='color:#58a6ff'>${wpos:,.2f}</b></div>"
                        f"<div><span style='color:#8b949e'>Liq. est.</span><br>"
                        f"<b style='color:#f85149'>${wliq:,.4f}</b></div>"
                        f"</div>"
                        f"<div style='margin-top:8px;padding-top:6px;border-top:1px solid #21262d;"
                        f"font-size:11px;color:#8b949e'>Dist. até liq: "
                        f"<b style='color:{'#f85149' if w_dist_liq < 20 else '#8b949e'}'>"
                        f"{w_dist_liq:.1f}%</b> &nbsp;·&nbsp; "
                        f"Risco máx: <b style='color:#ffa657'>${w_risk_max:,.2f}</b></div>"
                        f"</div>",
                        unsafe_allow_html=True)

                    # Botão "Abrir posição"
                    col_abrir, col_remover = st.columns(2)
                    with col_abrir:
                        if st.button("➕ Abrir posição", key=f"open_watch_{witem['coin_id']}_{wi}", width='stretch'):
                            # Lógica de abertura
                            cg_data = _fetch_price(witem["coin_id"], use_cache=True)
                            price = cg_data.get("price", 0)
                            if price <= 0:
                                st.error(f"Preço não disponível para {witem['coin_id']}. Tente novamente.")
                            else:
                                # Verificar se já existe posição aberta para este ativo (opcional)
                                port = _load_port()
                                already_open = any(p["coin_id"] == witem["coin_id"] and p.get("status") == "OPEN" for p in port.get("positions", []))
                                if already_open:
                                    st.warning(f"Já existe uma posição aberta para {witem['coin_id'].upper()}.")
                                else:
                                    # Calcular posição
                                    lev = float(witem["leverage"])
                                    margin = float(witem["margin"])
                                    pos_size = (margin * lev) / price
                                    liq_price = _calc_liq_price(price, lev, "LONG")
                                    # Criar novo objeto de posição
                                    new_pos = {
                                        "coin_id": witem["coin_id"],
                                        "name": cg_data.get("name", witem["coin_id"]),
                                        "direction": "LONG",
                                        "leverage": lev,
                                        "total_margin": margin,
                                        "position_size": round(pos_size, 8),
                                        "entry_avg": price,
                                        "exchange": witem.get("exchange", ""),
                                        "notes": f"Aberto via watchlist em {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} | Sinal macro ativo",
                                        "status": "OPEN",
                                        "opened_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                                        "entries": [{
                                            "date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                                            "price": price,
                                            "margin": margin,
                                            "leverage": lev
                                        }]
                                    }
                                    # Deduzir margem do caixa (se disponível)
                                    cash_atual = float(port.get("cash_usd", 0))
                                    if cash_atual < margin:
                                        st.error(f"Saldo insuficiente! Disponível: ${cash_atual:.2f} | Necessário: ${margin:.2f}")
                                    else:
                                        port["cash_usd"] = round(cash_atual - margin, 2)
                                        port["positions"].append(new_pos)
                                        # Registrar no extrato
                                        _log_tx(port, "ABERTURA", witem["coin_id"], margin, price, 0,
                                                f"LONG {lev}x via watchlist")
                                        # Remover da watchlist (opcional, comente se preferir manter)
                                        port["watchlist"] = [w for w in port.get("watchlist", []) if w["coin_id"] != witem["coin_id"]]
                                        _save_port(port)
                                        # Enviar Telegram
                                        msg = (f"📥 <b>POSIÇÃO ABERTA VIA WATCHLIST</b>\n"
                                            f"<b>{witem['coin_id'].upper()}</b> — {lev}x LONG @ ${price:,.4f}\n"
                                            f"Margem: ${margin:,.2f} | Posição: ${margin*lev:,.2f}\n"
                                            f"Liq. est.: ${liq_price:,.4f}\n"
                                            f"Corretora: {witem.get('exchange','')}\n"
                                            f"Saldo restante: ${port['cash_usd']:,.2f}\n\n"
                                            "Montrezor Portfolio")
                                        _send_tg(msg)
                                        st.success(f"✅ Posição {witem['coin_id'].upper()} aberta com sucesso!")
                                        st.rerun()
                    with col_remover:
                        if st.button("✕ Remover", key=f"del_w_{wi}", width='stretch'):
                            # Lê o arquivo diretamente
                            with open(_PORT_FILE, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            # Remove o item pelo índice real (wi)
                            if 0 <= wi < len(data.get("watchlist", [])):
                                data["watchlist"].pop(wi)
                            # Salva
                            with open(_PORT_FILE, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, default=str)
                            # Força recarga completa
                            st.success("Item removido da watchlist!")
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
                    st.plotly_chart(fig_pie, width='stretch')

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
                    st.plotly_chart(fig_eq, width='stretch')
                else:
                    st.info("Histórico insuficiente para o gráfico de evolução (mín. 2 dias).")

            # ── Gráfico P&L por ativo ────────────────────────────────────────
            if positions_enriched:
                _pnl_vals  = [p["pnl"]            for p in positions_enriched]
                _pnl_names = [p["coin_id"].upper() for p in positions_enriched]
                _pnl_clrs  = ["#3fb950" if v >= 0 else "#f85149" for v in _pnl_vals]
                fig_pnl = go.Figure(go.Bar(
                    x=_pnl_vals, y=_pnl_names,
                    orientation="h",
                    marker_color=_pnl_clrs,
                    text=[f"${v:+,.2f}" for v in _pnl_vals],
                    textposition="outside",
                ))
                fig_pnl.add_vline(x=0, line_dash="dot", line_color="#484f58")
                fig_pnl.update_layout(
                    title="P&L Aberto por Ativo (USD)",
                    height=max(160, len(positions_enriched)*50),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#8b949e", size=11),
                    margin=dict(l=0, r=60, t=36, b=0),
                    xaxis=dict(gridcolor="#21262d"),
                    yaxis=dict(gridcolor="#21262d"),
                )
                st.plotly_chart(fig_pnl, width='stretch')

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
                st.dataframe(rows, width='stretch', hide_index=True)

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
                    st.dataframe(crows, width='stretch', hide_index=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 4 — EXTRATO / LINHA DO TEMPO
    # ════════════════════════════════════════════════════════════════════════
    with pt4:
        st.markdown("#### 📒 Extrato — Linha do Tempo de Movimentações")
        extrato = port.get("extrato", [])

        if not extrato:
            st.info("Nenhuma movimentação registrada ainda.")
        else:
            # Filtros
            fc1, fc2 = st.columns([2,3])
            with fc1:
                tipos_disp = sorted(set(t["type"] for t in extrato))
                tipo_filtro = st.multiselect("Filtrar por tipo", tipos_disp,
                                              default=tipos_disp, key="ext_filtro")
            with fc2:
                coin_disp = sorted(set(t["coin_id"] for t in extrato))
                coin_filtro = st.multiselect("Filtrar por ativo", coin_disp,
                                              default=coin_disp, key="ext_coin")

            filtrado = [t for t in extrato
                        if t["type"] in tipo_filtro and t["coin_id"] in coin_filtro]

            # Ícones por tipo
            _icons = {
                "DEPOSITO":      "💵",
                "SAQUE":         "🏧",
                "ABERTURA":      "📥",
                "DCA":           "🔄",
                "VENDA_PARCIAL": "💸",
                "VENDA_TOTAL":   "💰",
            }

            # Tabela visual
            rows_ext = []
            total_pnl_realizado = 0.0
            for t in filtrado:
                icon = _icons.get(t["type"], "•")
                pnl_clr = "+" if t["pnl"] >= 0 else ""
                total_pnl_realizado += t["pnl"]
                rows_ext.append({
                    "Data":    t["date"],
                    "Tipo":    f"{icon} {t['type']}",
                    "Ativo":   t["coin_id"].upper(),
                    "Valor":   f"${t['amount']:,.2f}",
                    "Preço":   f"${t['price']:,.4f}" if t["price"] > 0 else "—",
                    "P&L":     f"${t['pnl']:+,.2f}" if t["pnl"] != 0 else "—",
                    "Notas":   t.get("notes",""),
                })

            st.dataframe(rows_ext, width='stretch', hide_index=True)

            # Resumo de P&L realizado total
            clr_sum = "#3fb950" if total_pnl_realizado >= 0 else "#f85149"
            st.markdown(
                f"<div style='background:#161b22;border:1px solid #30363d;"
                f"border-radius:6px;padding:10px 16px;margin-top:8px;font-size:13px'>"
                f"P&L Realizado Total (filtrado): "
                f"<b style='color:{clr_sum}'>${total_pnl_realizado:+,.2f}</b>"
                f"</div>",
                unsafe_allow_html=True)

            # Download CSV
            st.download_button(
                "📥 Exportar Extrato CSV",
                __import__("pandas").DataFrame(filtrado).to_csv(index=False),
                "montrezor_extrato.csv", "text/csv", key="ext_dl")

            if st.button("🗑 Limpar Extrato", key="ext_clear"):
                port["extrato"] = []
                _save_port(port)
                st.rerun()

    # Salvar equity history — APENAS se mudou hoje (evita rerun infinito)
    # _save_port a cada rerun causaria loop: salva → mtime muda → rerun → salva → ...
    today = str(pd.Timestamp.now())[:10]
    last_eq_date = eq_hist[-1].get("date","") if eq_hist else ""
    if last_eq_date == today and port.get("equity_history") != eq_hist:
        port["equity_history"] = eq_hist
        _save_port(port)
