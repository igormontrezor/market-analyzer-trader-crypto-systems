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
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
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


def _get_api_key() -> str:
    """Lê ANTHROPIC_API_KEY do ambiente ou do arquivo de config Telegram."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # Fallback: procurar no arquivo de config local
    cfg_file = os.path.join(os.path.expanduser("~"), ".montrezor_ai.json")
    if os.path.exists(cfg_file):
        try:
            return json.load(open(cfg_file)).get("anthropic_key", "")
        except Exception:
            pass
    return ""


# ════════════════════════════════════════════════════════════════════════════════
# 2. PROMPT PARA O CLAUDE
# ════════════════════════════════════════════════════════════════════════════════

def _build_prompt(df_top: pd.DataFrame, macro: dict, confirmed: list,
                  watchlist: list, cycle: str, prev_top10: list) -> str:
    """
    Constrói o prompt com todos os dados relevantes para o Claude analisar.
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
        rows.append(
            f"- {row['symbol']:<12} score={row.get('composite_score',0):.1f} "
            f"mc=${row.get('market_cap',0)/1e6:.1f}M "
            f"ratio={row.get('ratio',0):.2f} "
            f"acum={row.get('accumulation_score',0):.1f} "
            f"social={row.get('social_score',0):.1f} "
            f"momentum={row.get('momentum','?')} "
            f"sector={row.get('sector','?')} "
            f"appear={row.get('appearances',1)} "
            f"{'[' + ' '.join(extra) + ']' if extra else ''}"
        )

    data_str = "\n".join(rows)
    prev_txt  = ", ".join(prev_top10) if prev_top10 else "nenhuma"
    cycle_txt = "SEMANAL (top 10)" if cycle == "weekly" else "MENSAL — refinamento final (top 3 das top 10 semanais)"

    return f"""Você é um analista quantitativo especializado em criptomoedas de baixa capitalização (micro-caps e small-caps) com potencial de valorização explosiva (x10 a x100).

Analise os dados abaixo do sistema Montrezor Gems Finder e retorne sua análise em JSON puro, sem markdown.

=== CONTEXTO DO SISTEMA ===
O sistema classifica moedas por:
- composite_score: score combinado (final_score 40%, ratio 20%, accumulation 20%, social 10%, consistency 10%)
- ratio: volume/market_cap — métrica central de atividade real vs tamanho
- accumulation_score: detecção de acumulação silenciosa
- social_score: momentum em redes sociais e Telegram
- appearances: quantas vezes apareceu nos scans recentes (consistência)
- IS_GOLD: pullback + volume real confirmado
- CONFIRMED_GEM: confirmada em múltiplos scans históricos
- IN_WATCHLIST: já está na watchlist do usuário

=== REGIME MACRO ATUAL ===
Status: {regime_txt}
Funding Rate BTC: {funding:.4f}%
Weekly Buy Trigger: {weekly_buy}

=== TOP 30 CANDIDATAS (dados agregados) ===
{data_str}

=== TOP 10 DA SEMANA ANTERIOR ===
{prev_txt}

=== MISSÃO: FILTRO {cycle_txt} ===
{"Selecione as 10 moedas com maior probabilidade de valorização expressiva na próxima semana, considerando o regime macro atual." if cycle == "weekly" else "Das top 10 semanais acima, selecione as 3 com maior probabilidade de ser as grandes vencedoras do mês. Estas são as moedas para posição mais relevante."}

Critérios prioritários:
1. Consistência de aparições (moedas que persistem são mais confiáveis)
2. Ratio alto (volume real vs market cap — o indicador mais honesto)
3. Acumulação silenciosa detectada (smart money entrando)
4. Alinhamento com regime macro ({regime_txt})
5. Market cap pequeno o suficiente para moves explosivos (preferencialmente < $50M)
6. Setor em momentum no ciclo atual

{"ATENÇÃO: Com capitulation_lock ativo, priorize moedas defensivas e de menor risco." if cap_lock else ""}

Retorne APENAS este JSON (sem texto extra, sem ```json):
{{
  "cycle": "{cycle}",
  "generated_at": "{datetime.now().strftime('%Y-%m-%d %H:%M')}",
  "regime": "{regime_txt}",
  "top_picks": [
    {{
      "rank": 1,
      "symbol": "SYMBOL",
      "composite_score": 0.0,
      "rationale": "explicação em 1-2 frases do por que esta moeda",
      "risk": "LOW|MEDIUM|HIGH",
      "potential": "x2-x5|x5-x10|x10+"
    }}
  ],
  "macro_note": "nota sobre o regime macro e como afeta as escolhas",
  "sectors_in_focus": ["setor1", "setor2"],
  "avoid": ["simbolo que deve evitar e por que em string curta"]
}}
"""


# ════════════════════════════════════════════════════════════════════════════════
# 3. CHAMADA À API DO CLAUDE
# ════════════════════════════════════════════════════════════════════════════════

def _call_claude(prompt: str, api_key: str) -> dict:
    """Chama Claude API e retorna o JSON parseado."""
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":      CLAUDE_MODEL,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post(CLAUDE_API, headers=headers, json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Claude API erro {r.status_code}: {r.text[:300]}")

    content = r.json()["content"][0]["text"].strip()
    # Limpar possível markdown que o modelo inclua
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
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

    # Construir prompt e chamar Claude
    prompt = _build_prompt(agg_df, macro, confirmed, watchlist, cycle, prev_top)
    result = _call_claude(prompt, api_key)
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


def get_history() -> list:
    """Retorna histórico de execuções (ciclo, timestamp, n_coins analisadas)."""
    return _load_results().get("history", [])


def get_aggregated_data(max_age_days: int = 7) -> pd.DataFrame:
    """Expõe o DataFrame agregado para visualização na UI."""
    full = _load_csvs(max_age_days)
    if full.empty:
        return pd.DataFrame()
    return _aggregate(full)
