"""
╔══════════════════════════════════════════════════════════════════════╗
║  GEMS AI FILTER — Filtro inteligente com Claude API                 ║
║                                                                      ║
║  Lê todos os CSVs gerados pelo gems_finder + dados do visualizer,   ║
║  consolida os scores e envia para o Claude fazer a análise final.   ║
║                                                                      ║
║  Ciclos:                                                             ║
║    Semanal  → top 10 moedas da semana                               ║
║    Mensal   → top 3 do mês (refinamento das top 10 semanais)        ║
║                                                                      ║
║  NÃO modifica nenhum dado existente. Apenas leitura + análise.      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import glob
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

# ── Configuração ──────────────────────────────────────────────────────────────
def _find_data_dir() -> str:
    """
    Busca a pasta data/ em múltiplos caminhos possíveis.
    Suporta: mesma pasta do script, pasta pai, path absoluto via env var.
    """
    candidates = [
        os.environ.get("MONTREZOR_DATA_DIR", ""),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gems_system", "data"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    # Fallback: criar se não existir
    fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(fallback, exist_ok=True)
    return fallback

DATA_DIR       = _find_data_dir()
SNAPSHOTS_DIR  = os.path.join(DATA_DIR, "snapshots")
MACRO_DIR      = os.path.join(DATA_DIR, "macro")
RESULTS_FILE   = os.path.join(DATA_DIR, "gems_ai_results.json")
TG_CFG_FILE    = os.path.join(os.path.expanduser("~"), ".montrezor_telegram.json")

# Quanto tempo (dias) considerar nos CSVs para análise semanal/mensal
WEEKLY_LOOKBACK_DAYS  = 7
MONTHLY_LOOKBACK_DAYS = 30

# Claude: usa claude-haiku-4-5 (gratuito via API free tier, suficiente para análise de texto)
CLAUDE_MODEL = "claude-sonnet-4-5"
CLAUDE_API   = "https://api.anthropic.com/v1/messages"


# ════════════════════════════════════════════════════════════════════════════════
# 1. COLETA DE DADOS
# ════════════════════════════════════════════════════════════════════════════════

def _load_csvs(max_age_days: int) -> pd.DataFrame:
    """
    Carrega todos os CSVs de snapshots dentro do período e consolida.
    Retorna DataFrame com uma linha por moeda, com médias ponderadas dos scores.
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)
    files  = sorted(glob.glob(os.path.join(SNAPSHOTS_DIR, "*.csv")))

    frames = []
    for f in files:
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            if mtime < cutoff:
                continue
            df = pd.read_csv(f)
            if df.empty or "symbol" not in df.columns:
                continue
            df["_file_age_days"] = (datetime.now() - mtime).total_seconds() / 86400
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames, ignore_index=True)
    return full


def _aggregate(full: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega múltiplas aparições da mesma moeda.
    Pondera scores mais recentes com peso maior (decaimento exponencial).
    """
    if full.empty:
        return pd.DataFrame()

    # Peso por idade: mais recente = mais peso
    full["_weight"] = np.exp(-full["_file_age_days"] / 3.0)  # meia-vida de 3 dias

    score_cols = [c for c in ["final_score","ratio","accumulation_score","social_score",
                               "consistency_score","market_cap","volume_24h","change_24h"]
                  if c in full.columns]

    agg = {}
    for sym, grp in full.groupby("symbol"):
        w  = grp["_weight"].values
        wt = w.sum()
        row = {"symbol": sym, "appearances": len(grp)}

        for col in score_cols:
            if col in grp.columns:
                vals = grp[col].fillna(0).values.astype(float)
                row[col] = float(np.sum(vals * w) / wt) if wt > 0 else 0.0

        # Campos booleanos / categoricos: moda
        for col in ["momentum","sector","is_gold","price_resilience","volume_recovery"]:
            if col in grp.columns:
                row[col] = grp[col].mode().iloc[0] if not grp[col].mode().empty else None

        # Nome mais recente
        if "name" in grp.columns:
            row["name"] = grp.sort_values("_file_age_days")["name"].iloc[0]

        agg[sym] = row

    df_agg = pd.DataFrame(list(agg.values()))

    # Score composto normalizado (0–100)
    # Pesos: final_score=40%, ratio=20%, accumulation=20%, social=10%, consistency=10%
    weight_map = {"final_score":0.40,"ratio":0.20,"accumulation_score":0.20,
                  "social_score":0.10,"consistency_score":0.10}
    df_agg["composite_score"] = 0.0
    total_w = 0.0
    for col, w in weight_map.items():
        if col in df_agg.columns:
            col_max = df_agg[col].max()
            if col_max > 0:
                df_agg["composite_score"] += (df_agg[col] / col_max) * w * 100
                total_w += w
    # Normaliza pelo peso real disponível (evita inflação quando colunas faltam)
    if total_w > 0:
        df_agg["composite_score"] = ((df_agg["composite_score"] / total_w)).clip(0, 100).round(2)

    # Bônus por consistência de aparições
    appearances_max = df_agg["appearances"].max()
    if appearances_max > 0:
        df_agg["composite_score"] += (df_agg["appearances"] / appearances_max) * 5

    # ── Tendência temporal: aparições crescendo = acumulação real ──────────────
    # Divide os CSVs em 2 metades (antiga vs recente) e compara frequência
    # trend_score > 0 = aparecendo mais nas últimas janelas (momentum crescente)
    try:
        full_sorted = full.sort_values("_file_age_days", ascending=False)
        midpoint    = full_sorted["_file_age_days"].median()
        recent_half = set(full_sorted[full_sorted["_file_age_days"] <= midpoint]["symbol"].unique())
        old_half    = set(full_sorted[full_sorted["_file_age_days"] >  midpoint]["symbol"].unique())

        def _trend(sym):
            in_recent = sym in recent_half
            in_old    = sym in old_half
            if in_recent and not in_old:    return 2   # nova entrante — forte sinal
            if in_recent and in_old:        return 1   # consistente
            if not in_recent and in_old:    return -1  # sumindo — cuidado
            return 0

        df_agg["weekly_trend"] = df_agg["symbol"].apply(_trend)
        # Bônus de até +3 pts por tendência crescente
        df_agg["composite_score"] += df_agg["weekly_trend"].clip(0, 2) * 1.5
    except Exception:
        df_agg["weekly_trend"] = 0

    # ── Divergência smart money: score alto + social baixo ────────────────────
    # Padrão mais explosivo: acumulação silenciosa antes do hype
    try:
        score_med  = df_agg["composite_score"].median()
        social_med = df_agg["social_score"].median() if "social_score" in df_agg.columns else 0
        df_agg["smart_money_div"] = (
            (df_agg["composite_score"] > score_med) &
            (df_agg.get("social_score", pd.Series(0, index=df_agg.index)) <= social_med * 0.6)
        )
    except Exception:
        df_agg["smart_money_div"] = False

    df_agg = df_agg.sort_values("composite_score", ascending=False).reset_index(drop=True)
    return df_agg


def _load_macro() -> dict:
    """Carrega o macro_timing.json do visualizer."""
    for path in [
        os.path.join(MACRO_DIR, "macro_timing.json"),
        os.path.join(MACRO_DIR, "macro_timing_cg.json"),
    ]:
        if os.path.exists(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except Exception:
                pass
    return {}


def _load_confirmed_gems() -> list:
    """Carrega confirmed_gems.json do gems_finder."""
    path = os.path.join(DATA_DIR, "confirmed_gems.json")
    if os.path.exists(path):
        try:
            data = json.load(open(path, encoding="utf-8"))
            return data.get("confirmed_gems", data) if isinstance(data, dict) else data
        except Exception:
            pass
    return []


def _load_watchlist() -> list:
    """Carrega watchlist_selecionada.csv."""
    path = os.path.join(DATA_DIR, "watchlist_selecionada.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            return df["symbol"].tolist() if "symbol" in df.columns else []
        except Exception:
            pass
    return []


PERFORMANCE_FILE = os.path.join(DATA_DIR, "gems_ai_performance.json")
BTC_CACHE_FILE   = os.path.join(DATA_DIR, "gems_ai_btc_cache.json")


def _fetch_btc_context() -> dict:
    """
    Lê contexto de ciclo do macro_timing.json gerado pelo visualizer.
    Este é o sistema de ciclo real do Montrezor — mais preciso que deduzir pelo ATH.
    Complementa com preço BTC via CoinGecko (cache 1h) para dar número concreto ao Claude.
    """
    # ── 1. Regime do sistema Montrezor (fonte primária) ───────────────────────
    macro = {}
    for candidate in [MACRO_DIR, os.path.join(os.path.dirname(MACRO_DIR), "macro")]:
        mf = os.path.join(candidate, "macro_timing.json")
        if os.path.exists(mf):
            try:
                macro = json.load(open(mf, encoding="utf-8"))
                break
            except Exception:
                pass

    regime  = macro.get("regime", {})
    signal  = macro.get("signal", {})
    buy_mode        = bool(regime.get("buy_mode", False))
    sell_mode       = bool(regime.get("sell_mode", False))
    cap_lock        = bool(regime.get("capitulation_lock", False))
    weekly_buy      = bool(signal.get("weekly_buy_trigger", False))
    weekly_sell     = bool(signal.get("weekly_sell_trigger", False))
    rebound         = bool(signal.get("tactical_rebound", False))
    funding         = float(macro.get("funding_rate", 0))

    # Classificação de ciclo baseada no seu sistema real
    if buy_mode and weekly_buy:
        cycle_pos = "BUY_CONFIRMED — compra mensal + semanal alinhados, janela ótima para alts"
    elif buy_mode and not weekly_buy:
        cycle_pos = "BUY_MACRO — macro de compra mas semanal ainda não confirmou, aguardar"
    elif sell_mode and cap_lock:
        cycle_pos = "CAPITULATION — dominância USDT subindo, evitar entradas, só repiques táticos"
    elif sell_mode and rebound:
        cycle_pos = "SELL_REBOUND — macro de venda mas repique ativo, janela curta de alta"
    elif sell_mode:
        cycle_pos = "SELL_MACRO — regime de venda, cautela máxima com alts especulativas"
    else:
        cycle_pos = "NEUTRO — regime indefinido, aguardar confirmação"

    # ── 2. Preço BTC via CoinGecko (complemento numérico) ────────────────────
    btc_price = 0.0; btc_24h = 0.0; btc_dom = 0.0; total_mcap = 0.0
    if os.path.exists(BTC_CACHE_FILE):
        try:
            cache = json.load(open(BTC_CACHE_FILE, encoding="utf-8"))
            age_h = (datetime.now() - datetime.fromisoformat(cache["ts"])).total_seconds() / 3600
            if age_h < 1.0:
                btc_price  = cache.get("btc_price", 0)
                btc_24h    = cache.get("btc_24h", 0)
                btc_dom    = cache.get("btc_dom", 0)
                total_mcap = cache.get("total_mcap_b", 0)
        except Exception:
            pass
    if btc_price == 0:
        try:
            r1 = requests.get("https://api.coingecko.com/api/v3/simple/price"
                              "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true", timeout=8)
            r2 = requests.get("https://api.coingecko.com/api/v3/global", timeout=8)
            btc        = r1.json().get("bitcoin", {}) if r1.status_code == 200 else {}
            gdata      = r2.json().get("data", {})    if r2.status_code == 200 else {}
            btc_price  = float(btc.get("usd", 0))
            btc_24h    = float(btc.get("usd_24h_change", 0))
            btc_dom    = float(gdata.get("market_cap_percentage", {}).get("btc", 0))
            total_mcap = float(gdata.get("total_market_cap", {}).get("usd", 0)) / 1e9
            cache_new  = {"ts": datetime.now().isoformat(), "btc_price": btc_price,
                          "btc_24h": btc_24h, "btc_dom": btc_dom, "total_mcap_b": total_mcap}
            json.dump(cache_new, open(BTC_CACHE_FILE,"w",encoding="utf-8"), default=str)
        except Exception:
            pass

    return {"ts": datetime.now().isoformat(),
            "btc_price": btc_price, "btc_24h": btc_24h,
            "btc_dom": btc_dom, "total_mcap_b": total_mcap,
            "cycle_pos": cycle_pos,
            "buy_mode": buy_mode, "sell_mode": sell_mode,
            "cap_lock": cap_lock, "weekly_buy": weekly_buy,
            "rebound": rebound, "funding": funding}


def _load_performance() -> list:
    """
    Carrega histórico de performance: quais picks do AI subiram/caíram.
    Cada entrada: {cycle, date, symbol, rank, price_at_pick, price_now, pct_change}
    """
    if os.path.exists(PERFORMANCE_FILE):
        try:
            return json.load(open(PERFORMANCE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_performance(data: list):
    json.dump(data, open(PERFORMANCE_FILE, "w", encoding="utf-8"), indent=2, default=str)


def _build_performance_summary(perf: list, lookback_runs: int = 6) -> str:
    """
    Feedback loop rico: padrões de quais características correlacionam
    com wins e losses — não apenas win rate genérico.
    """
    if not perf:
        return "Sem histórico de performance anterior."

    recent = perf[-(lookback_runs * 10):]
    wins   = [p for p in recent if p.get("pct_change", 0) > 10]
    losses = [p for p in recent if p.get("pct_change", 0) < -10]
    wr     = len(wins) / len(recent) * 100 if recent else 0
    lines  = [f"PERFORMANCE HISTÓRICA ({len(recent)} picks | win rate {wr:.0f}%):"]

    if wins:
        top = sorted(wins, key=lambda x: x.get("pct_change",0), reverse=True)[:5]
        lines.append("MELHORES PICKS: " + " | ".join(
            f"{p['symbol']} +{p['pct_change']:.0f}% (rank#{p.get('rank','?')})"
            for p in top))
    if losses:
        bot = sorted(losses, key=lambda x: x.get("pct_change",0))[:3]
        lines.append("PIORES PICKS: " + " | ".join(
            f"{p['symbol']} {p['pct_change']:.0f}%" for p in bot))

    # Padrão por rank
    rank_wins = {}; rank_total = {}
    for p in recent:
        r = str(p.get("rank","?"))
        rank_total[r] = rank_total.get(r, 0) + 1
        if p.get("pct_change", 0) > 10:
            rank_wins[r] = rank_wins.get(r, 0) + 1
    rank_patterns = [
        f"rank#{r}={rank_wins.get(r,0)/tot*100:.0f}%wr({tot}picks)"
        for r, tot in sorted(rank_total.items()) if tot >= 2
    ]
    if rank_patterns:
        lines.append("WIN RATE POR RANK: " + " | ".join(rank_patterns))

    # Padrão por ciclo
    for cyc in ("weekly", "monthly"):
        cp = [p for p in recent if p.get("cycle") == cyc]
        cw = [p for p in cp if p.get("pct_change",0) > 10]
        if cp:
            lines.append(f"CICLO {cyc.upper()}: {len(cw)}/{len(cp)} wins "
                         f"({len(cw)/len(cp)*100:.0f}%)")

    lines.append("INSTRUÇÃO: use esses padrões para calibrar suas escolhas. "
                 "Prefira características que correlacionam com wins históricos.")
    return "\n".join(lines)


def _get_api_key() -> str:
    """Lê ANTHROPIC_API_KEY do ambiente ou do arquivo de config."""
    def _clean(k: str) -> str:
        # Remove espaços, newlines e aspas que podem entrar ao copiar
        return k.strip().strip('"').strip("'").strip()

    key = _clean(os.environ.get("ANTHROPIC_API_KEY", ""))
    if key:
        return key
    cfg_file = os.path.join(os.path.expanduser("~"), ".montrezor_ai.json")
    if os.path.exists(cfg_file):
        try:
            raw = json.load(open(cfg_file, encoding="utf-8")).get("anthropic_key", "")
            return _clean(raw)
        except Exception:
            pass
    return ""


# ════════════════════════════════════════════════════════════════════════════════
# 2. PROMPT PARA O CLAUDE
# ════════════════════════════════════════════════════════════════════════════════

def _build_prompt(df_top: pd.DataFrame, macro: dict, confirmed: list,
                  watchlist: list, cycle: str, prev_top10: list,
                  perf_txt: str = "", btc_ctx: dict = None) -> tuple:
    """
    Retorna (system_prompt, user_prompt).
    cycle: "weekly" | "monthly"
    """
    regime = macro.get("regime", macro)
    buy_mode   = bool(regime.get("buy_mode", False))
    sell_mode  = bool(regime.get("sell_mode", False))
    cap_lock   = bool(macro.get("capitulation_lock", regime.get("capitulation_lock", False)))
    funding    = float(macro.get("funding_rate", 0))
    signal     = macro.get("signal", {})
    weekly_buy = bool(signal.get("weekly_buy_trigger", False))

    regime_txt = "COMPRA ATIVA" if buy_mode else ("VENDA" if sell_mode else "NEUTRO")
    if cap_lock:
        regime_txt += " + CAPITULATION LOCK (evitar entradas)"

    confirmed_syms = [g.get("symbol","") for g in confirmed if isinstance(g, dict)]
    rows = []
    for _, row in df_top.head(30).iterrows():
        extra = []
        if row.get("is_gold"): extra.append("IS_GOLD")
        if row.get("price_resilience"): extra.append("PRICE_RESILIENT")
        if row.get("volume_recovery"): extra.append("VOL_RECOVERY")
        if row["symbol"] in confirmed_syms: extra.append("CONFIRMED_GEM")
        if row["symbol"] in watchlist: extra.append("IN_WATCHLIST")
        # Flags adicionais
        if row.get("smart_money_div"): extra.append("SMART_MONEY_DIV")
        trend_val = int(row.get("weekly_trend", 0))
        trend_lbl = {2:"TREND_UP↑↑", 1:"TREND_STABLE", -1:"TREND_FADING↓"}.get(trend_val, "")
        if trend_lbl: extra.append(trend_lbl)
        # Consistência de aparições como pct do máximo
        consist = float(row.get("consistency_score", 0))
        rows.append(
            f"- {row['symbol']:<12} score={row.get('composite_score',0):.1f} "
            f"mc=${row.get('market_cap',0)/1e6:.1f}M "
            f"ratio={row.get('ratio',0):.2f} "
            f"acum={row.get('accumulation_score',0):.1f} "
            f"social={row.get('social_score',0):.1f} "
            f"consist={consist:.1f} "
            f"resilience={float(row.get('price_resilience',0)):.1f} "
            f"vol_recovery={int(bool(row.get('volume_recovery',False)))} "
            f"momentum={row.get('momentum','?')} "
            f"sector={row.get('sector','?')} "
            f"appear={row.get('appearances',1)} "
            f"{'[' + ' '.join(extra) + ']' if extra else ''}"
        )

    data_str = "\n".join(rows)
    prev_txt  = ", ".join(prev_top10) if prev_top10 else "nenhuma"
    cycle_txt = "SEMANAL (top 10)" if cycle == "weekly" else "MENSAL — refinamento final (top 3 das top 10 semanais)"
    if not perf_txt:
        perf_txt = "Sem histórico de performance anterior."

    btc = btc_ctx or {}
    btc_price  = float(btc.get("btc_price", 0))
    btc_24h    = float(btc.get("btc_24h", 0))
    btc_ath    = float(btc.get("btc_ath_pct", 0))
    btc_dom    = float(btc.get("btc_dom", 0))
    total_mcap = float(btc.get("total_mcap_b", 0))
    cycle_pos  = btc.get("cycle_pos", "desconhecido")
    btc_line   = (f"BTC ${btc_price:,.0f} ({btc_24h:+.1f}% 24h) | Dom {btc_dom:.1f}% | "
                  f"{btc_ath:.0f}% vs ATH | MCap total ${total_mcap:.0f}B"
                  if btc_price > 0 else "dados indisponíveis")

    system = (
        "Você é o Montrezor AI Gems Analyst — especializado em micro-cap e small-cap "
        "crypto ANTES de moves explosivos.\n\n"
        "Detecta padrões invisíveis:\n"
        "- SMART_MONEY_DIV: acumulação alta + social baixo = whales antes do hype\n"
        "- TREND_UP: nova nos scans = smart money acabou de entrar\n"
        "- IS_GOLD + acum: pullback + acumulação silenciosa = entrada perfeita\n\n"
        "Considera o ciclo BTC para calibrar potencial e risco.\n"
        "É CÉTICO com hype sem fundamentals.\n"
        "Retorna APENAS JSON válido, sem texto extra."
    )

    mission = ("Selecione as 10 moedas com maior probabilidade de valorização expressiva "
               "na próxima semana." if cycle == "weekly" else
               "Das top 10 semanais, selecione as 3 de MAIOR CONVICÇÃO para o mês.")

    user = f"""=== CONTEXTO BTC ===
{btc_line}
Posição no ciclo: {cycle_pos}

=== REGIME MACRO ===
Status: {regime_txt} | Funding: {funding:.4f}% | Weekly Buy: {weekly_buy}
{"CAPITULATION LOCK ATIVO" if cap_lock else ""}

=== LEGENDA ===
composite_score=score combinado | ratio=volume/mcap (CENTRAL) | acum=acumulação silenciosa
social=momentum público (BAIXO+score alto=SMART_MONEY_DIV) | TREND_UP=nova nos scans
IS_GOLD=pullback+volume | CONFIRMED_GEM=múltiplos scans | consist=consistência histórica

=== TOP {len(rows)} CANDIDATAS ===
{data_str}

=== CICLO ANTERIOR ===
{prev_txt}

=== FEEDBACK LOOP ===
{perf_txt}

=== MISSÃO: {cycle_txt} ===
{mission}
Prioridades: 1.SMART_MONEY_DIV+ratio+TREND_UP 2.IS_GOLD+acum 3.MCap<$30M 4.ciclo={cycle_pos}
{"5. CAPITULATION LOCK: preferir LOW RISK." if cap_lock else ""}

Retorne APENAS este JSON:
{{
  "cycle": "{cycle}",
  "generated_at": "{datetime.now().strftime('%Y-%m-%d %H:%M')}",
  "regime": "{regime_txt}",
  "btc_context": "{btc_line[:80]}",
  "top_picks": [
    {{
      "rank": 1,
      "symbol": "SYMBOL",
      "composite_score": 0.0,
      "key_flags": ["FLAG1"],
      "rationale": "dados específicos: ratio, flags, trend que destacam esta moeda",
      "entry_note": "entrada em pullback / em momentum / aguardar confirmação",
      "risk": "LOW|MEDIUM|HIGH",
      "potential": "x2-x5|x5-x10|x10+"
    }}
  ],
  "macro_note": "como ciclo BTC e macro afetam as escolhas",
  "sectors_in_focus": ["setor1"],
  "smart_money_highlight": "símbolo SMART_MONEY_DIV mais promissor",
  "avoid": ["motivo curto"]
}}"""

    return system, user


# ════════════════════════════════════════════════════════════════════════════════
# 3. CHAMADA À API DO CLAUDE
# ════════════════════════════════════════════════════════════════════════════════

def _call_claude(system_prompt: str, user_prompt: str, api_key: str) -> dict:
    """Chama Claude API com system prompt separado."""
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":      CLAUDE_MODEL,
        "max_tokens": 2048,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_prompt}],
    }
    r = requests.post(CLAUDE_API, headers=headers, json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Claude API erro {r.status_code}: {r.text[:300]}")
    content = r.json()["content"][0]["text"].strip()
    if "```" in content:
        for part in content.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                content = part; break
    return json.loads(content)


# ════════════════════════════════════════════════════════════════════════════════
# 4. ORQUESTRADOR PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════════

def _send_result_tg(result: dict, cycle: str):
    """Envia resumo da análise AI ao Telegram."""
    try:
        if not os.path.exists(TG_CFG_FILE):
            return
        cfg     = json.load(open(TG_CFG_FILE, encoding="utf-8"))
        token   = cfg.get("token","").strip()
        chat_id = str(cfg.get("chat_id","")).strip()
        if not token or not chat_id:
            return

        picks   = result.get("top_picks", [])[:5]   # top 5 no Telegram
        cycle_l = "SEMANAL 🗓" if cycle == "weekly" else "MENSAL 🏆"
        lines   = [f"🤖 <b>AI GEMS FILTER — {cycle_l}</b>",
                   "━━━━━━━━━━━━━━━━━━",
                   f"🌍 Regime: {result.get('regime','—')}"]

        for p in picks:
            risk_icon = {"LOW":"🟢","MEDIUM":"🟡","HIGH":"🔴"}.get(p.get("risk","MEDIUM"),"•")
            pot_icon  = {"x10+":"🚀","x5-x10":"⚡","x2-x5":"📈"}.get(p.get("potential","x2-x5"),"•")
            lines.append(f"{risk_icon} #{p.get('rank',0)} <b>{p.get('symbol','?')}</b> "
                         f"{pot_icon} {p.get('potential','?')} | score {p.get('composite_score',0):.1f}")

        if result.get("macro_note"):
            lines += ["", f"<i>{result['macro_note'][:200]}</i>"]

        avoid = result.get("avoid",[])
        if avoid:
            lines.append(f"⛔ Evitar: {', '.join(str(a) for a in avoid[:3])}")

        lines += ["", f"📅 {result.get('generated_at','—')}", "Montrezor AI Gems Filter"]

        msg = "\n".join(lines)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id":chat_id,"text":msg,"parse_mode":"HTML"}, timeout=10)
    except Exception:
        pass   # Telegram é opcional — não quebra a análise


def _load_results() -> dict:
    if os.path.exists(RESULTS_FILE):
        try:
            return json.load(open(RESULTS_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"weekly": None, "monthly": None, "history": []}


def _save_results(results: dict):
    json.dump(results, open(RESULTS_FILE, "w", encoding="utf-8"), indent=2, default=str)


def should_run(cycle: str) -> bool:
    """Verifica se é hora de rodar o ciclo (semanal = 7d, mensal = 30d)."""
    results = _load_results()
    entry   = results.get(cycle)
    if not entry:
        return True
    try:
        last_run = datetime.fromisoformat(entry["generated_at"].replace(" ", "T"))
        threshold = timedelta(days=7 if cycle == "weekly" else 30)
        return (datetime.now() - last_run) > threshold
    except Exception:
        return True


def run_analysis(cycle: str, api_key: str, force: bool = False) -> dict:
    """
    Roda a análise completa para o ciclo especificado.
    Retorna o resultado (dict) ou lança exceção.
    """
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurada. "
                         "Defina a variável de ambiente ou salve em ~/.montrezor_ai.json")

    results = _load_results()

    if not force and not should_run(cycle):
        return results[cycle]

    # Coletar dados
    days    = WEEKLY_LOOKBACK_DAYS if cycle == "weekly" else MONTHLY_LOOKBACK_DAYS
    full_df = _load_csvs(days)
    if full_df.empty:
        raise RuntimeError("Nenhum snapshot CSV encontrado em data/snapshots/. "
                           "Execute o Gems Finder primeiro.")

    agg_df    = _aggregate(full_df)
    macro     = _load_macro()
    confirmed = _load_confirmed_gems()
    watchlist = _load_watchlist()

    # Para análise mensal, usar top 10 semanal como candidatas
    _monthly_filtered = False
    if cycle == "monthly" and results.get("weekly"):
        weekly_syms = [p["symbol"] for p in results["weekly"].get("top_picks", [])]
        if weekly_syms:
            agg_df = agg_df[agg_df["symbol"].isin(weekly_syms)]
            _monthly_filtered = True
    if cycle == "monthly" and not _monthly_filtered:
        # Sinaliza no resultado que não havia semanal para refinar
        result_warning = "⚠️ Análise mensal sem refinamento semanal — rode a semanal primeiro para resultado mais preciso."
    else:
        result_warning = ""

    # Top 10 da análise anterior (para contexto)
    prev_key   = "weekly" if cycle == "weekly" else "monthly"
    prev_entry = results.get(prev_key)
    prev_top   = [p["symbol"] for p in prev_entry.get("top_picks",[])] if prev_entry else []

    # Feedback loop: carregar performance histórica
    perf     = _load_performance()
    perf_txt = _build_performance_summary(perf)

    # Contexto BTC — cache 1h, silencioso se offline
    btc_ctx = _fetch_btc_context()

    # Construir system+user e chamar Claude
    system_prompt, user_prompt = _build_prompt(
        agg_df, macro, confirmed, watchlist, cycle, prev_top, perf_txt, btc_ctx)
    result = _call_claude(system_prompt, user_prompt, api_key)
    if result_warning:
        result["macro_note"] = result_warning + " " + result.get("macro_note","")

    # Salvar resultado
    results[cycle] = result
    results.setdefault("history", []).append({
        "cycle": cycle, "ts": datetime.now().isoformat(),
        "n_csvs": len(full_df), "n_coins": len(agg_df)
    })
    _save_results(results)

    # Enviar resultado ao Telegram
    _send_result_tg(result, cycle)

    return result


def get_latest(cycle: str) -> Optional[dict]:
    """Retorna o último resultado salvo sem rodar nova análise."""
    return _load_results().get(cycle)


def _fetch_coingecko_price(symbol: str) -> float:
    """Busca preço atual via CoinGecko. Tenta coin id direto, depois search."""
    try:
        sym = symbol.lower().replace("usdt","").replace("usd","").strip()
        url = "https://api.coingecko.com/api/v3/simple/price"
        r   = requests.get(url, params={"ids": sym, "vs_currencies": "usd"}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if sym in data:
                return float(data[sym].get("usd", 0))
        # Fallback: search por nome
        r2 = requests.get("https://api.coingecko.com/api/v3/search",
                           params={"query": sym}, timeout=8)
        if r2.status_code == 200:
            coins = r2.json().get("coins", [])
            if coins:
                coin_id = coins[0]["id"]
                r3 = requests.get(url, params={"ids": coin_id, "vs_currencies": "usd"}, timeout=8)
                if r3.status_code == 200:
                    return float(r3.json().get(coin_id, {}).get("usd", 0))
    except Exception:
        pass
    return 0.0


def auto_update_performance() -> int:
    """
    Busca preços atuais via CoinGecko para todas as picks ainda não registradas.
    Chamado automaticamente ao abrir a aba AI Filter.
    Retorna número de entradas atualizadas.
    """
    results = _load_results()
    perf    = _load_performance()
    updated = 0
    perf_keys = {(p["symbol"], p["date"]) for p in perf}

    for cycle in ("weekly", "monthly"):
        result = results.get(cycle)
        if not result:
            continue
        pick_date = result.get("generated_at", "")[:10]
        for pick in result.get("top_picks", []):
            sym = pick.get("symbol", "")
            if not sym or (sym, pick_date) in perf_keys:
                continue
            price_now = _fetch_coingecko_price(sym)
            if price_now > 0:
                register_performance(cycle, sym, pick.get("rank", 0), 0.0, price_now)
                perf_keys.add((sym, pick_date))
                updated += 1
    return updated


def register_performance(cycle: str, symbol: str, rank: int,
                          price_at_pick: float, price_now: float):
    """
    Registra o resultado real de uma pick.
    Chamar semanalmente para alimentar o feedback loop.
    Pode ser chamado manualmente pela UI ou pelo daemon.
    """
    try:
        perf = _load_performance()
        pct  = (price_now - price_at_pick) / price_at_pick * 100 if price_at_pick > 0 else 0
        perf.append({
            "cycle":         cycle,
            "date":          datetime.now().strftime("%Y-%m-%d"),
            "symbol":        symbol,
            "rank":          rank,
            "price_at_pick": price_at_pick,
            "price_now":     price_now,
            "pct_change":    round(pct, 2),
            "result":        "WIN" if pct > 10 else ("LOSS" if pct < -10 else "NEUTRAL"),
        })
        _save_performance(perf[-500:])  # manter últimas 500 entradas
    except Exception:
        pass


def get_history() -> list:
    """Retorna histórico de execuções (ciclo, timestamp, n_coins analisadas)."""
    return _load_results().get("history", [])


def get_aggregated_data(max_age_days: int = 7) -> pd.DataFrame:
    """Expõe o DataFrame agregado para visualização na UI."""
    full = _load_csvs(max_age_days)
    if full.empty:
        return pd.DataFrame()
    return _aggregate(full)
