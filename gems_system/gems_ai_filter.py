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
import time
import requests
import glob
import random
import pandas as pd
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List

# ── Configuração ──────────────────────────────────────────────────────────────
def _find_data_dir() -> str:
    """
    Busca a pasta data/ em múltiplos caminhos possíveis.
    Prioriza o diretório ao lado do script (gems_system/data) para manter unificação.
    """
    local_data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    candidates = [
        os.environ.get("MONTREZOR_DATA_DIR", ""),
        local_data,   # ← PRIORIDADE: gems_system/data
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),  # raiz (fallback)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gems_system", "data"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    # Fallback: criar ao lado do script se nada existir
    os.makedirs(local_data, exist_ok=True)
    return local_data

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
# UTILITÁRIOS PARA FUNDING SQUEEZE
# ════════════════════════════════════════════════════════════════════════════════

_COIN_ID_CACHE = {}
_PRICE_CACHE = {}

def _get_coin_id(symbol: str) -> Optional[str]:
    """Retorna o coin_id da CoinGecko para um símbolo (com cache). Verifica correspondência exata do símbolo."""
    sym_up = symbol.upper()
    if sym_up in _COIN_ID_CACHE:
        return _COIN_ID_CACHE[sym_up]
    try:
        url = f"https://api.coingecko.com/api/v3/search?query={symbol.lower()}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            coins = data.get('coins', [])
            # Procurar o primeiro resultado cujo símbolo corresponde exatamente (case-insensitive)
            for coin in coins:
                if coin.get('symbol', '').upper() == sym_up:
                    coin_id = coin['id']
                    _COIN_ID_CACHE[sym_up] = coin_id
                    return coin_id
    except Exception:
        pass
    _COIN_ID_CACHE[sym_up] = None
    return None

def _get_historical_lows(coin_id: str, days: int = 5) -> List[float]:
    """
    Retorna lista de preços mínimos (low) diários dos últimos `days` dias.
    Usa cache de 1 hora.
    """
    cache_key = f"{coin_id}_lows_{days}"
    now = datetime.now()
    if cache_key in _PRICE_CACHE:
        ts, lows = _PRICE_CACHE[cache_key]
        if (now - ts).total_seconds() < 3600:  # cache 1h
            return lows
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # market_chart retorna listas de [timestamp, valor] para 'prices', 'market_caps', 'total_volumes'
            # Para lows, usamos 'prices' (apenas preço de fechamento) – a CoinGecko não fornece low diretamente no endpoint gratuito.
            # Alternativa: usar o endpoint /coins/{id}/ohlc?days=5 (requer API pro?). Como fallback, usamos o preço de fechamento.
            # Para detectar higher lows, o fechamento já é razoável. Se precisar de low real, seria necessário outro endpoint.
            # Vamos usar 'prices' (preço de fechamento diário) como proxy.
            prices = data.get('prices', [])
            if prices:
                lows = [p[1] for p in prices[-days:]]  # últimos `days` dias
                _PRICE_CACHE[cache_key] = (now, lows)
                return lows
    except Exception:
        pass
    return []

def _check_funding_negative_last_2_days() -> bool:
    """
    Retorna True se os últimos 2 dias completos (cada dia inteiro) tiverem funding rate médio negativo.
    """
    try:
        hist_path = os.path.join(DATA_DIR, "macro", "funding_rate_history.csv")
        if not os.path.exists(hist_path):
            macro = _load_macro()
            funding = float(macro.get("funding_rate", 0.01))
            return funding < 0
        df = pd.read_csv(hist_path, parse_dates=['timestamp'])
        if len(df) < 2:
            return False
        df['date'] = df['timestamp'].dt.date
        daily_negative = df.groupby('date')['funding_rate'].mean() < 0
        last_2 = daily_negative.tail(2)
        if len(last_2) < 2:
            return False
        return last_2.all()
    except Exception:
        return False

def _has_higher_lows(symbol: str) -> bool:
    """
    Verifica se a moeda está formando 'higher lows' nos últimos 3 dias.
    Retorna True se low[-3] < low[-2] < low[-1] (mínimas sequencialmente mais altas).
    """
    try:
        coin_id = _get_coin_id(symbol)
        if not coin_id:
            return False
        lows = _get_historical_lows(coin_id, days=5)
        if len(lows) < 3:
            return False
        # Pega os últimos 3 lows
        last_3 = lows[-3:]
        return last_3[0] < last_3[1] < last_3[2]
    except Exception:
        return False


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
    HOT_SECTORS = []
    try:
        hot_file = os.path.join(DATA_DIR, 'hot_sectors.json')
        if os.path.exists(hot_file):
            with open(hot_file) as f:
                hdata = json.load(f)
                if (datetime.now() - datetime.fromisoformat(hdata['timestamp'])).days < 7:
                    HOT_SECTORS = hdata.get('hot', [])
    except:
        pass
    if full.empty:
        return pd.DataFrame()

    # Peso por idade: mais recente = mais peso
    full["_weight"] = np.exp(-full["_file_age_days"] / 3.0)  # meia-vida de 3 dias

    score_cols = [c for c in ["final_score","ratio","accumulation_score","social_score",
                               "consistency_score","market_cap","volume_24h","change_24h", "drawdown_pct"]
                  if c in full.columns]

    agg = {}
    for sym, grp in full.groupby("symbol"):
        w  = grp["_weight"].values
        wt = w.sum()
        row = {"symbol": sym, "appearances": len(grp)}

        for col in score_cols:
            if col in grp.columns:
                vals = grp[col].fillna(0).values.astype(float)
                row[col] = float(np.nansum(vals * w) / wt) if wt > 0 else 0.0

        # Campos booleanos / categoricos: moda
        for col in ["momentum","sector","is_gold","price_resilience","volume_recovery", "seller_exhaustion"]:
            if col in grp.columns:
                row[col] = grp[col].mode().iloc[0] if not grp[col].mode().empty else None

        # Nome mais recente
        if "name" in grp.columns:
            row["name"] = grp.sort_values("_file_age_days")["name"].iloc[0]

        # ── Ranking change (7 dias) ──────────────────────────────
        # Coletar pares (file_age_days, rank) para este símbolo
        ranks = []
        for _, r in grp.iterrows():
            rank = r.get('market_cap_rank', 0)
            if rank is not None and rank > 0:
                age = r['_file_age_days']
                ranks.append((age, rank))
        if ranks:
            # Ordenar por idade (menor = mais recente)
            ranks.sort(key=lambda x: x[0])
            newest_rank = ranks[0][1]
            oldest_rank = ranks[-1][1]
            rank_change = oldest_rank - newest_rank   # positivo = subiu no ranking
            row['rank_change_7d'] = rank_change
            row['rank_up'] = rank_change > 10
        else:
            row['rank_change_7d'] = 0
            row['rank_up'] = False

                # ── Tendência de volume (VOL_UP) ──────────────────────────────
        # Coletar volumes com suas idades (mais recente = menor _file_age_days)
        volume_data = []
        for _, r in grp.iterrows():
            vol = r.get('total_volume', 0)
            if vol > 0:
                age = r['_file_age_days']
                volume_data.append((age, vol))
        if len(volume_data) >= 3:  # mínimo 3 pontos para regressão
            # Ordenar por idade (mais recente primeiro)
            volume_data.sort(key=lambda x: x[0])
            # Pegar até 5 dias mais recentes
            recent = volume_data[:5]
            vols = [v for _, v in recent]
            n = len(vols)
            # Regressão linear simples: volume ~ posição (0..n-1)
            x = list(range(n))
            x_mean = sum(x) / n
            y_mean = sum(vols) / n
            num = sum((x[i] - x_mean) * (vols[i] - y_mean) for i in range(n))
            den = sum((x[i] - x_mean) ** 2 for i in range(n))
            slope = num / den if den != 0 else 0
            # Média histórica do símbolo (todos os pontos)
            all_vols = [v for _, v in volume_data]
            historical_mean = sum(all_vols) / len(all_vols)
            recent_mean = y_mean
            if slope > 0 and recent_mean > historical_mean:
                row['vol_up'] = True
            else:
                row['vol_up'] = False
        else:
            row['vol_up'] = False

        # ── Narrativa quente (HOT_NARRATIVE) ──────────────────────────────
        # Determinar setor mais frequente para este símbolo (moda)
        sector_vals = [r.get('sector', '') for _, r in grp.iterrows() if r.get('sector')]
        if sector_vals:
            from collections import Counter
            sector = Counter(sector_vals).most_common(1)[0][0]
        else:
            sector = ''
        # Setor quente (dinâmico, carregado do hot_sectors.json)
        is_hot = (sector in HOT_SECTORS)
        # Opcional: lista fixa de símbolos conhecidos (adicione se quiser)
        # HOT_SYMBOLS = {'FET', 'AGIX', 'RNDR', 'TAO', 'HNT', 'ONDO', 'GALA'}
        # is_hot = is_hot or (sym.upper() in HOT_SYMBOLS)
        row['hot_narrative'] = is_hot

        agg[sym] = row

    df_agg = pd.DataFrame(list(agg.values()))


    # ── Calcular consistency_score (frequência de aparição no período) ──
    if 'appearances' in df_agg.columns and '_file_age_days' in full.columns:
        total_days = math.ceil(full['_file_age_days'].max()) + 1
        if total_days > 0:
            df_agg['consistency_score'] = (df_agg['appearances'] / total_days).clip(0, 1)
        else:
            df_agg['consistency_score'] = 0.0
    else:
        df_agg['consistency_score'] = 0.0

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

    # Bónus por tendência de volume crescente
    if 'vol_up' in df_agg.columns:
        df_agg['composite_score'] += df_agg['vol_up'].astype(float) * 3
        df_agg['composite_score'] = df_agg['composite_score'].clip(0, 100)

    # Bónus por subida no ranking (>10 posições)
    if 'rank_up' in df_agg.columns:
        df_agg['composite_score'] += df_agg['rank_up'].astype(float) * 5
        df_agg['composite_score'] = df_agg['composite_score'].clip(0, 100)

    # Bônus por drawdown > 70% (potencial de recuperação explosiva)
    if 'drawdown_pct' in df_agg.columns:
        # Apenas moedas com drawdown válido e > 0 recebem bônus
        mask = (df_agg['drawdown_pct'] >= 0.7) & (df_agg['drawdown_pct'].notna())
        if mask.any():
            # Bônus linear de 0 a 10 pontos, apenas para drawdown entre 0.7 e 1.0
            bonus = (df_agg.loc[mask, 'drawdown_pct'].clip(0.7, 1.0) - 0.7) / 0.3 * 10
            df_agg.loc[mask, 'composite_score'] += bonus
            df_agg['composite_score'] = df_agg['composite_score'].clip(0, 100)

    # Bónus por narrativa quente (HOT_NARRATIVE)
    if 'hot_narrative' in df_agg.columns:
        df_agg['composite_score'] += df_agg['hot_narrative'].astype(float) * 4
        df_agg['composite_score'] = df_agg['composite_score'].clip(0, 100)

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

    # ... (cálculo de composite_score, bônus, etc.)

    # ── Ordenar e retornar
    df_agg = df_agg.sort_values("composite_score", ascending=False).reset_index(drop=True)

    # ── Gerar hot_sectors.json automaticamente a partir dos dados agregados ──
    # Usa os mesmos CSVs que já foram lidos — sem chamada externa
    try:
        if "sector" in df_agg.columns:
            sector_stats = {}
            for _, row in df_agg.iterrows():
                sec = str(row.get("sector","")).strip()
                if not sec or sec in ("","nan","None","?"): continue
                if sec not in sector_stats:
                    sector_stats[sec] = {"appearances":0, "score_sum":0.0, "count":0}
                sector_stats[sec]["appearances"] += int(row.get("appearances", 1))
                sector_stats[sec]["score_sum"]   += float(row.get("composite_score", 0))
                sector_stats[sec]["count"]        += 1

            if sector_stats:
                # Score por setor = média ponderada por aparições
                for sec in sector_stats:
                    c = sector_stats[sec]["count"]
                    sector_stats[sec]["avg_score"] = (
                        sector_stats[sec]["score_sum"] / c if c > 0 else 0)

                # Top setores: pelo menos 2 moedas, ordenado por avg_score
                hot = sorted(
                    [s for s,v in sector_stats.items() if v["count"] >= 2],
                    key=lambda s: sector_stats[s]["avg_score"], reverse=True
                )[:8]

                hot_file = os.path.join(DATA_DIR, "hot_sectors.json")
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "hot": hot,
                    "all_sectors": {s: {"avg_score": round(v["avg_score"],1),
                                        "count": v["count"],
                                        "appearances": v["appearances"]}
                                    for s,v in sorted(sector_stats.items(),
                                        key=lambda x: x[1]["avg_score"], reverse=True)}
                }, open(hot_file,"w",encoding="utf-8"), indent=2)
    except Exception:
        pass   # silencioso — não quebra a análise

    return df_agg


def _load_macro() -> dict:
    """
    Carrega o macro_timing.json do diretório data/macro do projeto.
    Garante que o arquivo seja encontrado independentemente do DATA_DIR.
    """
    # Caminho absoluto baseado no arquivo atual (gems_ai_filter.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    macro_file = os.path.join(current_dir, "data", "macro", "macro_timing.json")

    # Fallback: caso não exista, tenta o caminho antigo (DATA_DIR)
    if not os.path.exists(macro_file):
        macro_file = os.path.join(DATA_DIR, "macro", "macro_timing.json")

    if os.path.exists(macro_file):
        try:
            with open(macro_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    # Se ainda não achou, retorna vazio
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
    """Carrega watchlist_selecionada.csv e também a lista de interesse do portfólio."""
    symbols = []
    # 1. CSV original
    path = os.path.join(DATA_DIR, "watchlist_selecionada.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            symbols.extend(df["symbol"].tolist())
        except Exception:
            pass
    # 2. Watchlist do portfólio (apenas os coin_ids)
    port_file = os.path.join(os.path.expanduser("~"), ".montrezor_portfolio.json")
    if os.path.exists(port_file):
        try:
            with open(port_file, encoding="utf-8") as f:
                port = json.load(f)
            watchlist = port.get("watchlist", [])
            for item in watchlist:
                sym = item.get("coin_id", "").upper()
                if sym:
                    symbols.append(sym)
        except Exception:
            pass
    return list(set(symbols))  # remove duplicatas

PERFORMANCE_FILE = os.path.join(DATA_DIR, "gems_ai_performance.json")
BTC_CACHE_FILE   = os.path.join(DATA_DIR, "gems_ai_btc_cache.json")
MACRO_SIGNALS_FILE = os.path.join(DATA_DIR, "macro_signals.json")
MACRO_DETAILED_SIGNALS_FILE = os.path.join(DATA_DIR, "macro_detailed_signals.json")
MACRO_CYCLES_FILE = os.path.join(DATA_DIR, "macro_cycles.json")

_last_signal_states = {
    "weekly_buy": False,
    "weekly_sell": False,
    "rebound": False,
    "rebound_super": False,
    "super_buy": False,
    "super_sell": False
}

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

def _load_macro_signals() -> list:
    if os.path.exists(MACRO_SIGNALS_FILE):
        try:
            with open(MACRO_SIGNALS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_macro_signals(signals: list):
    try:
        with open(MACRO_SIGNALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(signals[-500:], f, indent=2, default=str)
    except Exception:
        pass

def _load_detailed_macro_signals() -> list:
    if os.path.exists(MACRO_DETAILED_SIGNALS_FILE):
        try:
            with open(MACRO_DETAILED_SIGNALS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_detailed_macro_signals(signals: list):
    try:
        with open(MACRO_DETAILED_SIGNALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(signals[-500:], f, indent=2, default=str)
    except Exception:
        pass

def evaluate_pending_macro_signals() -> int:
    """Avalia sinais macro pendentes (7d e 30d) comparando com preço do BTC."""
    signals = _load_macro_signals()
    updated = 0
    now = datetime.now()
    for sig in signals:
        if sig.get("evaluated_7d") and sig.get("evaluated_30d"):
            continue
        sig_date = datetime.fromisoformat(sig["timestamp"])
        btc_then = sig.get("btc_price_usd", 0.0)
        if btc_then <= 0:
            continue

        # Avaliação 7 dias
        if not sig.get("evaluated_7d") and (now - sig_date).days >= 7:
            btc_now = _fetch_btc_context().get("btc_price", 0.0)
            if btc_now > 0:
                pct = (btc_now - btc_then) / btc_then * 100
                regime = sig["regime"]
                if "BUY" in regime or "SUPER_BUY" in regime:
                    win = pct > 3
                elif "SELL" in regime or "SUPER_SELL" in regime or "CAPITULATION" in regime:
                    win = pct < -3
                else:
                    win = abs(pct) < 5
                sig["outcome_7d"] = "WIN" if win else "LOSS"
                sig["evaluated_7d"] = True
                updated += 1
        # Avaliação 30 dias
        if not sig.get("evaluated_30d") and (now - sig_date).days >= 30:
            btc_now = _fetch_btc_context().get("btc_price", 0.0)
            if btc_now > 0:
                pct = (btc_now - btc_then) / btc_then * 100
                regime = sig["regime"]
                if "BUY" in regime or "SUPER_BUY" in regime:
                    win = pct > 10
                elif "SELL" in regime or "SUPER_SELL" in regime or "CAPITULATION" in regime:
                    win = pct < -10
                else:
                    win = abs(pct) < 15
                sig["outcome_30d"] = "WIN" if win else "LOSS"
                sig["evaluated_30d"] = True
                updated += 1
    if updated:
        _save_macro_signals(signals)
    return updated

def evaluate_pending_detailed_signals() -> int:
    """Avalia sinais detalhados pendentes: compara com próximo sinal do mesmo tipo ou mudança de regime."""
    detailed = _load_detailed_macro_signals()
    if not detailed:
        return 0
    updated = 0
    for i, sig in enumerate(detailed):
        if sig.get("evaluated"):
            continue
        signal_type = sig["signal"]
        btc_then = sig.get("btc_price_usd", 0.0)
        if btc_then <= 0:
            continue

        # 1. Tentar encontrar o próximo sinal do MESMO tipo
        next_signal = None
        for j in range(i + 1, len(detailed)):
            if detailed[j]["signal"] == signal_type:
                next_signal = detailed[j]
                break

        if next_signal:
            btc_now = next_signal.get("btc_price_usd", 0.0)
            if btc_now > 0:
                pct = (btc_now - btc_then) / btc_then * 100
                if "buy" in signal_type or "rebound" in signal_type or "super_buy" in signal_type:
                    win = pct > 0
                else:
                    win = pct < 0
                sig["outcome"] = "WIN" if win else "LOSS"
                sig["return_pct"] = round(pct, 2)
                sig["exit_timestamp"] = next_signal["timestamp"]
                sig["exit_price"] = btc_now
                sig["evaluated"] = True
                updated += 1
                print(f"📊 Sinal {signal_type} de {sig['date']} avaliado: {sig['outcome']} ({pct:+.2f}%) até próximo {signal_type} em {next_signal['date'][:10]}")
            continue

        # 2. Se não há próximo sinal, usar mudança de regime contrário
        macro_signals = _load_macro_signals()
        sig_ts = datetime.fromisoformat(sig["timestamp"])
        current_regime = sig.get("regime_at_signal", "")
        # Determinar se é sinal de compra ou venda
        is_buy_signal = any(x in signal_type for x in ["buy", "rebound", "super_buy"])
        opposite_regime = None
        for ms in macro_signals:
            ms_ts = datetime.fromisoformat(ms["timestamp"])
            if ms_ts > sig_ts:
                if is_buy_signal and "SELL" in ms["regime"]:
                    opposite_regime = ms
                    break
                elif not is_buy_signal and "BUY" in ms["regime"]:
                    opposite_regime = ms
                    break
        if opposite_regime:
            btc_now = opposite_regime.get("btc_price_usd", 0.0)
            if btc_now > 0:
                pct = (btc_now - btc_then) / btc_then * 100
                win = (pct > 0) if is_buy_signal else (pct < 0)
                sig["outcome"] = "WIN" if win else "LOSS"
                sig["return_pct"] = round(pct, 2)
                sig["exit_timestamp"] = opposite_regime["timestamp"]
                sig["exit_price"] = btc_now
                sig["evaluated"] = True
                updated += 1
                print(f"📊 Sinal {signal_type} de {sig['date']} avaliado por mudança de regime: {sig['outcome']} ({pct:+.2f}%) até {opposite_regime['date'][:10]}")
    if updated:
        _save_detailed_macro_signals(detailed)
    return updated

def evaluate_macro_regime_cycles() -> list:
    """Avalia ciclos completos de regime macro (ex.: BUY_CONFIRMED → SELL_CONFIRMED)."""
    signals = _load_macro_signals()
    if len(signals) < 2:
        return []
    cycles = []
    current_cycle = None
    for sig in signals:
        regime = sig["regime"]
        if "BUY" in regime or "SELL" in regime:
            if current_cycle is None:
                current_cycle = {"type": regime, "start_ts": sig["timestamp"], "start_price": sig.get("btc_price_usd", 0)}
            elif ("BUY" in current_cycle["type"] and "SELL" in regime) or ("SELL" in current_cycle["type"] and "BUY" in regime):
                current_cycle["end_ts"] = sig["timestamp"]
                current_cycle["end_price"] = sig.get("btc_price_usd", 0)
                cycles.append(current_cycle)
                current_cycle = None
    cycle_results = []
    for c in cycles:
        if c["start_price"] > 0 and c.get("end_price", 0) > 0:
            ret = (c["end_price"] - c["start_price"]) / c["start_price"] * 100
            win = (ret > 0 and "BUY" in c["type"]) or (ret < 0 and "SELL" in c["type"])
            cycle_results.append({
                "type": c["type"],
                "start": c["start_ts"],
                "end": c["end_ts"],
                "return_pct": round(ret, 2),
                "win": win
            })
    try:
        with open(MACRO_CYCLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cycle_results, f, indent=2, default=str)
    except Exception:
        pass
    return cycle_results

def get_macro_signal_performance(days_window: int = 7) -> dict:
    """Retorna winrate por regime macro para janela de 7d ou 30d."""
    signals = _load_macro_signals()
    stats = {}
    for sig in signals:
        if days_window == 7:
            outcome = sig.get("outcome_7d")
        else:
            outcome = sig.get("outcome_30d")
        if outcome is None:
            continue
        regime = sig["regime"]
        if regime not in stats:
            stats[regime] = {"total": 0, "wins": 0}
        stats[regime]["total"] += 1
        if outcome == "WIN":
            stats[regime]["wins"] += 1
    for r in stats:
        stats[r]["winrate"] = stats[r]["wins"] / stats[r]["total"] * 100 if stats[r]["total"] else 0
    return stats

def get_detailed_signal_performance(signal_type_filter=None) -> dict:
    """Retorna winrate e retorno médio por tipo de sinal detalhado."""
    detailed = _load_detailed_macro_signals()
    stats = {}
    for sig in detailed:
        if sig.get("outcome") is None:
            continue
        s_type = sig["signal"]
        if signal_type_filter and s_type != signal_type_filter:
            continue
        if s_type not in stats:
            stats[s_type] = {"total": 0, "wins": 0, "returns": []}
        stats[s_type]["total"] += 1
        if sig["outcome"] == "WIN":
            stats[s_type]["wins"] += 1
        ret = sig.get("return_pct", 0)
        if ret is not None:
            stats[s_type]["returns"].append(ret)
    for s in stats:
        t = stats[s]["total"]
        stats[s]["winrate"] = stats[s]["wins"] / t * 100 if t else 0
        stats[s]["avg_return"] = sum(stats[s]["returns"]) / len(stats[s]["returns"]) if stats[s]["returns"] else 0
    return stats

def get_macro_cycle_stats() -> dict:
    """Retorna estatísticas dos ciclos completos (BUY→SELL ou SELL→BUY)."""
    if not os.path.exists(MACRO_CYCLES_FILE):
        return {}
    try:
        with open(MACRO_CYCLES_FILE, 'r', encoding='utf-8') as f:
            cycles = json.load(f)
    except:
        return {}
    if not cycles:
        return {}

    buy_cycles = [c for c in cycles if "BUY" in c["type"]]
    sell_cycles = [c for c in cycles if "SELL" in c["type"]]

    def stats(cycle_list):
        if not cycle_list:
            return {}
        wins = sum(1 for c in cycle_list if c["win"])
        total = len(cycle_list)
        avg_return = sum(c["return_pct"] for c in cycle_list) / total
        return {
            "total": total,
            "wins": wins,
            "winrate": wins / total * 100,
            "avg_return": avg_return
        }

    return {
        "buy_cycles": stats(buy_cycles),
        "sell_cycles": stats(sell_cycles),
        "all_cycles": stats(cycles)
    }

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
                  perf_txt: str = "", btc_ctx: dict = None,
                  dex_df=None) -> tuple:
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
    for _, row in df_top.head(50).iterrows():
        extra = []
        if row.get("is_gold"): extra.append("IS_GOLD")
        if row.get("price_resilience"): extra.append("PRICE_RESILIENT")
        if row.get("volume_recovery"): extra.append("VOL_RECOVERY")
        if row["symbol"] in confirmed_syms: extra.append("CONFIRMED_GEM")
        if row["symbol"] in watchlist: extra.append("IN_WATCHLIST")
        # Flags adicionais
        if row.get("smart_money_div"): extra.append("SMART_MONEY_DIV")
        if row.get("rank_up"): extra.append("RANK_UP")
        if row.get("vol_up"): extra.append("VOL_UP")
        if row.get("hot_narrative"): extra.append("HOT_NARRATIVE")
        if row.get("funding_squeeze"): extra.append("FUNDING_SQUEEZE")
        if row.get("seller_exhaustion"): extra.append("SELLER_EXHAUSTION")
        trend_val = int(row.get("weekly_trend", 0))
        trend_lbl = {2:"TREND_UP↑↑", 1:"TREND_STABLE", -1:"TREND_FADING↓"}.get(trend_val, "")
        if trend_lbl: extra.append(trend_lbl)
        # Consistência de aparições como pct do máximo
        consist = float(row.get("consistency_score", 0))
        rows.append(
            f"- {row['symbol']:<12} score={row.get('composite_score',0):.1f} "
            f"drawdown={row.get('drawdown_pct',0):.2f} "
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
        "Retorne APENAS JSON válido, sem texto extra.\n"
        "O JSON deve conter:\n"
        '{"symbol": "SYMBOL", "composite_score": 0.0, "key_flags": [],\n'
        ' "rationale": "...", "entry_note": "...", "risk": "LOW|MEDIUM|HIGH",\n'
        ' "potential": "x2-x5|x5-x10|x10+", "confidence": 0-100,\n'
        ' "price_target": null, "stop_loss": null, "entry_zone": null}\n'
        "Considere o contexto macro e os flags.\n\n"
        "**Formatação:** Use quebras de linha (`\\n`) e, se apropriado, bullet points (ex.: `- item`) para organizar a rationale, tornando-a fácil de ler."
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
drawdown=queda desde o ATH (0=ATH, 0.7=70% abaixo, 0.9=90% abaixo) – >0.7 = potencial explosivo
RANK_UP = subiu >10 posições no ranking de market cap em 7 dias (entrada de capital)
VOL_UP = volume total em tendência de alta nos últimos 5 dias (acumulação silenciosa)
HOT_NARRATIVE = setor identificado como quente pelo sistema (ex: AI, DePIN, RWA, GameFi, etc.)
FUNDING_SQUEEZE = funding BTC negativo 2 dias + higher lows (potencial short squeeze)
SELLER_EXHAUSTION = drawdown > 80% + volatilidade < 6% + ratio atual > 2x média 3d → fundo real, reversão explosiva

=== TOP {len(rows)} CANDIDATAS ===
{data_str}

=== CICLO ANTERIOR ===
{prev_txt}

=== FEEDBACK LOOP ===
{perf_txt}

=== MISSÃO: {cycle_txt} ===
{mission}
Prioridades: 1.SMART_MONEY_DIV+ratio+TREND_UP 2.IS_GOLD+acum 3.MCap<$30M 4.ciclo={cycle_pos}
{ "5. CAPITULATION LOCK: preferir LOW RISK.\n" if cap_lock else "" }
Dica adicional: Em ciclo BUY_CONFIRMED ou NEUTRO, dê peso extra para moedas com drawdown > 0.7 (potencial de recuperação explosiva).
Dica adicional: Dê atenção extra a moedas com RANK_UP combinado com ratio alto (sinal de entrada institucional).
Dica adicional: Moedas com VOL_UP + SMART_MONEY_DIV indicam acumulação silenciosa antes do movimento.
Dica adicional: Priorize moedas com HOT_NARRATIVE + SMART_MONEY_DIV (narrativa quente + acumulação silenciosa) em ciclos de alta.
Dica adicional: Moedas com FUNDING_SQUEEZE + SMART_MONEY_DIV indicam possível explosão de alta por aperto de shorts.
Dica adicional: Moedas com SELLER_EXHAUSTION são candidatas a fundo real – priorize em ciclos de compra ou repique tático.
**Importante: inclua o campo "top3_comparison" com uma análise comparativa detalhada das top 3 picks.**

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
      "rationale": "2-3 frases específicas: explique porque esta moeda se destaca (ratio, flags, tendência, contexto macro, etc.)",
      "entry_note": "entrada em pullback / em momentum / aguardar confirmação",
      "risk": "LOW|MEDIUM|HIGH",
      "potential": "x2-x5|x5-x10|x10+"
    }}
  ],
  "top3_comparison": "Parágrafo comparando as 3 principais candidatas (rank 1, 2 e 3). Destaque diferenças de risco, potencial, flags e contexto macro. Conclua qual delas tem o melhor risco/retorno.",
  "macro_note": "como ciclo BTC e macro afetam as escolhas",
  "sectors_in_focus": ["setor1"],
  "smart_money_highlight": "símbolo SMART_MONEY_DIV mais promissor",
  "avoid": ["motivo curto"]
}}"""

    # ── Seção DexScreener (early stage, pré-CoinGecko) ──────────────────────
    if dex_df is not None and not dex_df.empty:
        dex_rows = []
        for _, row in dex_df.head(15).iterrows():
            dex_rows.append(
                f"- {str(row.get('symbol','?')):<12} "
                f"liq=${float(row.get('liquidity_usd',0))/1000:.0f}K "
                f"vol=${float(row.get('volume_24h_usd',0))/1000:.0f}K "
                f"buys={int(row.get('buys_24h',0))} "
                f"sells={int(row.get('sells_24h',0))} "
                f"ratio={float(row.get('buy_ratio',0)):.2f} "
                f"chain={row.get('chain','?')}"
                f"count={int(row.get('appearances',1))}")
        dex_header = "\n\n=== EARLY STAGE — DexScreener (pré-CoinGecko) ===\n"
        dex_footer = ("\nPriorize tokens com buy_ratio > 0.6, liquidez crescente e "
                      "ciclo BTC em BUY_CONFIRMED. Potencial x10-x100 mas risco HIGH obrigatório.\n")
        user += dex_header + "\n".join(dex_rows) + dex_footer
        system = system.replace(
                "Retorne APENAS JSON válido, sem texto extra.\n",
                "Retorne APENAS JSON válido, sem texto extra.\n"
                "- EARLY STAGE ..."
            )

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
        "max_tokens": 4096,
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

def _get_ml_score_for_pick(cycle: str, symbol: str, pick_date: str) -> Optional[float]:
    """
    Busca o ml_score que foi salvo para um pick específico.
    Retorna None se não encontrado.
    """
    results = _load_results()
    result = results.get(cycle)
    if not result:
        return None
    # pick_date está no formato "YYYY-MM-DD" (ex: "2025-05-26")
    # generated_at está no formato "2025-05-26 12:34"
    gen_date = result.get("generated_at", "")[:10]
    if gen_date != pick_date:
        # Pode acontecer se a data de registro for diferente da data da análise
        # Ainda assim tentamos encontrar pelo símbolo (último resultado do ciclo)
        pass
    for pick in result.get("top_picks", []):
        if pick.get("symbol") == symbol:
            return pick.get("ml_score")
    return None

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

def _build_individual_prompt(row, macro, confirmed, watchlist, btc_ctx, cycle, dex_df=None):
    """Constrói prompt para análise individual de uma moeda."""
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
    extra = []
    if row.get("is_gold"): extra.append("IS_GOLD")
    if row.get("price_resilience"): extra.append("PRICE_RESILIENT")
    if row.get("volume_recovery"): extra.append("VOL_RECOVERY")
    if row["symbol"] in confirmed_syms: extra.append("CONFIRMED_GEM")
    if row["symbol"] in watchlist: extra.append("IN_WATCHLIST")
    if row.get("smart_money_div"): extra.append("SMART_MONEY_DIV")
    if row.get("rank_up"): extra.append("RANK_UP")
    if row.get("vol_up"): extra.append("VOL_UP")
    if row.get("hot_narrative"): extra.append("HOT_NARRATIVE")
    if row.get("funding_squeeze"): extra.append("FUNDING_SQUEEZE")
    if row.get("seller_exhaustion"): extra.append("SELLER_EXHAUSTION")
    trend_val = int(row.get("weekly_trend", 0))
    trend_lbl = {2:"TREND_UP↑↑", 1:"TREND_STABLE", -1:"TREND_FADING↓"}.get(trend_val, "")
    if trend_lbl: extra.append(trend_lbl)

    btc = btc_ctx or {}
    btc_price  = float(btc.get("btc_price", 0))
    btc_24h    = float(btc.get("btc_24h", 0))
    btc_dom    = float(btc.get("btc_dom", 0))
    total_mcap = float(btc.get("total_mcap_b", 0))
    cycle_pos  = btc.get("cycle_pos", "desconhecido")
    btc_line   = (f"BTC ${btc_price:,.0f} ({btc_24h:+.1f}% 24h) | Dom {btc_dom:.1f}% | MCap total ${total_mcap:.0f}B"
                  if btc_price > 0 else "dados indisponíveis")

    system = (
        "Você é o Montrezor AI Gems Analyst — especializado em micro-cap e small-cap "
        "crypto ANTES de moves explosivos.\n\n"
        "Retorne APENAS JSON válido, sem texto extra.\n"
        "O JSON deve conter:\n"
        '{"symbol": "SYMBOL", "composite_score": 0.0, "key_flags": [],\n'
        ' "rationale": "...", "entry_note": "...", "risk": "LOW|MEDIUM|HIGH",\n'
        ' "potential": "x2-x5|x5-x10|x10+", "confidence": 0-100,\n'
        ' "price_target": null, "stop_loss": null, "entry_zone": null}\n'
        "Considere o contexto macro e os flags.\n\n"
        "**Formatação:** Use quebras de linha (`\\n`) e, se apropriado, bullet points (ex.: `- item`) para organizar a rationale, tornando-a fácil de ler."
    )

    data_str = (
        f"- {row['symbol']:<12} score={row.get('composite_score',0):.1f} "
        f"drawdown={row.get('drawdown_pct',0):.2f} "
        f"mc=${row.get('market_cap',0)/1e6:.1f}M "
        f"ratio={row.get('ratio',0):.2f} "
        f"acum={row.get('accumulation_score',0):.1f} "
        f"social={row.get('social_score',0):.1f} "
        f"resilience={float(row.get('price_resilience',0)):.1f} "
        f"vol_recovery={int(bool(row.get('volume_recovery',False)))} "
        f"momentum={row.get('momentum','?')} sector={row.get('sector','?')} "
        f"appear={row.get('appearances',1)} "
        f"{'[' + ' '.join(extra) + ']' if extra else ''}"
    )

    user = f"""=== CONTEXTO BTC ===
{btc_line}
Posição no ciclo: {cycle_pos}

=== REGIME MACRO ===
Status: {regime_txt} | Funding: {funding:.4f}% | Weekly Buy: {weekly_buy}
{"CAPITULATION LOCK ATIVO" if cap_lock else ""}

=== DADOS DA MOEDA ===
{data_str}"""

    # ── Seção DexScreener (early stage) para esta moeda ──────────────────────
    if dex_df is not None and not dex_df.empty:
        # 1. Tentar correspondência exata por símbolo
        sym = row['symbol'].upper()
        dex_matches = dex_df[dex_df['symbol'].str.upper() == sym]
        if not dex_matches.empty:
            # Mostrar apenas os tokens correspondentes (máx. 5)
            dex_rows = []
            for _, drow in dex_matches.head(5).iterrows():
                dex_rows.append(
                    f"- {drow['symbol']:<12} liq=${drow.get('liquidity_usd',0)/1000:.0f}K "
                    f"vol=${drow.get('volume_24h_usd',0)/1000:.0f}K "
                    f"buys={int(drow.get('buys_24h',0))} sells={int(drow.get('sells_24h',0))} "
                    f"buy_ratio={drow.get('buy_ratio',0):.2f} chain={drow.get('chain','?')} "
                    f"appear={int(drow.get('appearances',1))}"
                )
            if dex_rows:
                user += "\n\n=== DEX EARLY STAGE (mesmo símbolo) ===\n" + "\n".join(dex_rows)
                user += "\nPriorize tokens com buy_ratio > 0.6 e liquidez crescente."
        else:
            # 2. Sem correspondência: mostrar top tokens DEX como contexto macro
            top_dex = dex_df.head(5)   # top 5 por composite_dex (já ordenado)
            if not top_dex.empty:
                dex_rows = []
                for _, drow in top_dex.iterrows():
                    dex_rows.append(
                        f"- {drow['symbol']:<12} liq=${drow.get('liquidity_usd',0)/1000:.0f}K "
                        f"vol=${drow.get('volume_24h_usd',0)/1000:.0f}K "
                        f"buy_ratio={drow.get('buy_ratio',0):.2f} "
                        f"appear={int(drow.get('appearances',1))} chain={drow.get('chain','?')}"
                    )
                if dex_rows:
                    user += "\n\n=== DEX EARLY STAGE (contexto macro – top tokens dos últimos 7 dias) ===\n"
                    user += f"Nenhum token com símbolo '{sym}' foi encontrado no DexScreener. "
                    user += "Abaixo os principais tokens early-stage detectados recentemente:\n"
                    user += "\n".join(dex_rows)
                    user += "\n\nConsidere o apetite geral por risco e as narrativas emergentes (ex.: setores, chains ativas)."

    user += "\n\nResponda APENAS com o JSON."
    return system, user

def _analyze_coin_deep(row, macro, confirmed, watchlist, btc_ctx, cycle, api_key, dex_df=None):
    """Chama Claude para análise individual de uma moeda. Retorna dict com campos padronizados."""
    system_prompt, user_prompt = _build_individual_prompt(row, macro, confirmed, watchlist, btc_ctx, cycle, dex_df)
    try:
        result = _call_claude(system_prompt, user_prompt, api_key)
        # Garantir campos obrigatórios
        result.setdefault("composite_score", row.get("composite_score", 0))
        result.setdefault("key_flags", [])
        result.setdefault("rationale", "Análise não disponível")
        result.setdefault("entry_note", "aguardar confirmação")
        result.setdefault("risk", "MEDIUM")
        result.setdefault("potential", "x2-x5")
        result.setdefault("confidence", 50)
        result.setdefault("price_target", None)
        result.setdefault("stop_loss", None)
        result.setdefault("entry_zone", None)
        if "symbol" not in result:
            result["symbol"] = row["symbol"]
        return result
    except Exception as e:
        print(f"Erro na análise individual de {row['symbol']}: {e}")
        return {
            "symbol": row["symbol"],
            "composite_score": row.get("composite_score", 0),
            "rationale": f"Falha na análise: {str(e)[:100]}",
            "risk": "MEDIUM",
            "potential": "x2-x5",
            "confidence": 30,
        }

def _run_deep_analysis(agg_df, macro, confirmed, watchlist, btc_ctx, cycle, api_key, dex_df=None):
    """Itera sobre top 15, chama análise individual, retorna top 10 ordenado por confidence."""
    top_candidates = agg_df.nlargest(15, "composite_score")
    picks = []
    for _, row in top_candidates.iterrows():
        deep = _analyze_coin_deep(row, macro, confirmed, watchlist, btc_ctx, cycle, api_key, dex_df)
        if deep:
            picks.append(deep)
        time.sleep(0.5)
    picks.sort(key=lambda x: (x.get("confidence", 0), x.get("composite_score", 0)), reverse=True)
    for i, pick in enumerate(picks[:10], 1):
        pick["rank"] = i
    return picks[:10]

def aggregate_dex_data(days: int = 7) -> pd.DataFrame:
    """
    Lê todos os arquivos dex_early_stage_*.csv no diretório data/
    dos últimos `days` dias, agrupa por símbolo e retorna DataFrame
    com métricas agregadas (médias, contagem de aparições, etc.).
    """
    data_dir = DATA_DIR
    pattern = os.path.join(data_dir, "dex_early_stage_*.csv")
    files = glob.glob(pattern)
    if not files:
        return pd.DataFrame()

    cutoff = datetime.now() - timedelta(days=days)
    dfs = []
    for f in files:
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        if mtime < cutoff:
            continue
        try:
            df = pd.read_csv(f)
            if not df.empty:
                dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)

    # Agrupar por symbol
    agg = combined.groupby('symbol').agg({
        'buy_ratio': 'mean',
        'volume_24h_usd': 'mean',
        'liquidity_usd': 'mean',
        'buys_24h': 'mean',
        'sells_24h': 'mean',
        'price_usd': 'mean',
        'price_change_24h': 'mean',
        'chain': lambda x: x.mode()[0] if not x.mode().empty else 'unknown',
        'dex_score': 'mean'
    }).reset_index()

    # Contagem de aparições
    count_series = combined.groupby('symbol').size().rename('appearances')
    agg = agg.merge(count_series, on='symbol')

    # Score composto (aparições * buy_ratio médio)
    agg['composite_dex'] = agg['appearances'] * agg['buy_ratio']
    agg = agg.sort_values('composite_dex', ascending=False)

    # Limitar a top 30
    return agg.head(30)

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

    # ── Detectar Funding Squeeze para as top 30 candidatas ─────────────
    funding_negative = _check_funding_negative_last_2_days()   # ← antes era _check_funding_negative_last_3_days()
    if funding_negative:
        agg_df['funding_squeeze'] = False
        for idx in agg_df.head(30).index:
            sym = agg_df.loc[idx, 'symbol']
            if _has_higher_lows(sym):
                agg_df.loc[idx, 'funding_squeeze'] = True
                agg_df.loc[idx, 'composite_score'] += 2
                agg_df.loc[idx, 'composite_score'] = agg_df.loc[idx, 'composite_score'].clip(0, 100)
    else:
        agg_df['funding_squeeze'] = False

    # ── Bônus Seller Exhaustion (fundo real) ─────────────────────────────
    if 'seller_exhaustion' in agg_df.columns:
        agg_df['seller_exhaustion'] = agg_df['seller_exhaustion'].astype(bool).astype(float)
        agg_df['composite_score'] += agg_df['seller_exhaustion'] * 8
        agg_df['composite_score'] = agg_df['composite_score'].clip(0, 100)

    # ── Smart Money Divergence (acumulação antes do hype) ───────────────
    if 'smart_money_div' in agg_df.columns:
        agg_df['smart_money_div'] = agg_df['smart_money_div'].astype(bool).astype(float)
        agg_df['composite_score'] += agg_df['smart_money_div'] * 3
        agg_df['composite_score'] = agg_df['composite_score'].clip(0, 100)

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

    # Adicionar performance histórica dos sinais macro
    macro_perf = get_macro_signal_performance(days_window=7)
    macro_lines = []
    for regime, data in macro_perf.items():
        if data["total"] >= 3:
            macro_lines.append(f"{regime}: {data['winrate']:.0f}% acerto ({data['wins']}/{data['total']})")
    if macro_lines:
        perf_txt += "\n\n=== PERFORMANCE DOS SINAIS MACRO (7d) ===\n" + "\n".join(macro_lines)

    # Adicionar performance dos sinais detalhados (entradas)
    detailed_perf = get_detailed_signal_performance()
    if detailed_perf:
        perf_txt += "\n\n=== PERFORMANCE DOS SINAIS DE ENTRADA ===\n"
        for s, data in detailed_perf.items():
            if data["total"] >= 3:
                perf_txt += f"{s}: {data['winrate']:.0f}% acerto ({data['wins']}/{data['total']}) | retorno médio {data['avg_return']:+.1f}%\n"

    cycle_stats = get_macro_cycle_stats()
    if cycle_stats:
        buy_total = cycle_stats.get("buy_cycles", {}).get("total", 0)
        sell_total = cycle_stats.get("sell_cycles", {}).get("total", 0)
        if buy_total >= 1 or sell_total >= 1:
            perf_txt += "\n\n=== CICLOS COMPLETOS DE REGIME ===\n"
            buy = cycle_stats["buy_cycles"]
            sell = cycle_stats["sell_cycles"]
            if buy_total >= 1:
                perf_txt += f"Ciclos BUY: {buy.get('total',0)} | acerto {buy.get('winrate',0):.0f}% | retorno médio {buy.get('avg_return',0):+.1f}%\n"
            if sell_total >= 1:
                perf_txt += f"Ciclos SELL: {sell.get('total',0)} | acerto {sell.get('winrate',0):.0f}% | retorno médio {sell.get('avg_return',0):+.1f}%"

    # Contexto BTC — cache 1h, silencioso se offline
    btc_ctx = _fetch_btc_context()

    # Early stage DexScreener - agregado dos últimos 7 dias
    dex_agg_df = aggregate_dex_data(days=7)
    if not dex_agg_df.empty:
        dex_df = dex_agg_df
        # Opcional: log informativo
        print(f"[DEX] Agregado {len(dex_df)} tokens early stage (últimos 7 dias)")
    else:
        dex_df = None

    # ── NOVO FLUXO PARA CICLO SEMANAL (análise individual) ──
    if cycle == "weekly":
        print("🔍 Usando análise individual para 15 candidatas...")

        top_picks = _run_deep_analysis(agg_df, macro, confirmed, watchlist,
                                        btc_ctx, cycle, api_key, dex_df)

        # Aplicar modelo ML nos picks semanais
        try:
            from ml_ranker import ml_predict_picks
            temp_result = {"top_picks": top_picks}
            temp_result = ml_predict_picks(temp_result, agg_df)
            top_picks = temp_result["top_picks"]
        except ImportError:
            pass

            # ── Preencher preços com delay entre chamadas ──
        for i, pick in enumerate(top_picks):
            sym = pick.get("symbol")
            if sym:
                price = _fetch_coingecko_price(sym)   # agora é a versão robusta
                pick["price_usd"] = price if price > 0 else None
                pick["price_date"] = datetime.now().isoformat()
                # Aguarda 2 segundos entre chamadas (evita rate limit)
                if i < len(top_picks) - 1:
                    time.sleep(3)

        regime_txt = "COMPRA ATIVA" if macro.get("regime", {}).get("buy_mode") else \
                     ("VENDA" if macro.get("regime", {}).get("sell_mode") else "NEUTRO")
        result = {
            "cycle": "weekly",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "regime": regime_txt,
            "btc_context": btc_ctx.get("cycle_pos", "desconhecido")[:80],
            "top_picks": top_picks,
            "top3_comparison": "",
            "macro_note": "Análise individual profunda por moeda.",
            "sectors_in_focus": [],
            "smart_money_highlight": "",
            "avoid": [],
            "market_regime": _get_current_macro_regime()
        }
        # Tentar adicionar setores em foco
        sectors = set()
        for p in top_picks:
            if "sector" in p:
                sectors.add(p["sector"])
        result["sectors_in_focus"] = list(sectors)[:3]

        # Salvar resultado
        results = _load_results()
        results["weekly"] = result
        results.setdefault("history", []).append({
            "cycle": "weekly", "ts": datetime.now().isoformat(),
            "n_csvs": len(full_df), "n_coins": len(agg_df)
        })
        _save_results(results)
        _send_result_tg(result, "weekly")
        return result

    # Construir system+user e chamar Claude
    system_prompt, user_prompt = _build_prompt(
        agg_df, macro, confirmed, watchlist, cycle, prev_top, perf_txt, btc_ctx, dex_df)
    result = _call_claude(system_prompt, user_prompt, api_key)
    result["market_regime"] = _get_current_macro_regime()
    try:
        from ml_ranker import ml_predict_picks
        result = ml_predict_picks(result, agg_df)
    except ImportError:
        pass
    if result_warning:
        result["macro_note"] = result_warning + " " + result.get("macro_note","")

    if result and "top_picks" in result:
        picks_list = result["top_picks"]
        for i, pick in enumerate(picks_list):
            sym = pick.get("symbol")
            if sym:
                price = _fetch_coingecko_price(sym)
                pick["price_usd"] = price if price > 0 else None
                pick["price_date"] = datetime.now().isoformat()
                if i < len(picks_list) - 1:
                    time.sleep(3)

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

# ── CACHE PERSISTENTE DE PREÇOS (CoinGecko) ─────────────────────────────────
_PRICE_CACHE_FILE = os.path.join(DATA_DIR, "coingecko_price_cache.json")
_PRICE_MEM_CACHE = {}

def _load_price_cache() -> dict:
    if os.path.exists(_PRICE_CACHE_FILE):
        try:
            with open(_PRICE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_price_cache(cache: dict):
    try:
        with open(_PRICE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, default=str)
    except:
        pass

def _fetch_coingecko_price(symbol: str, max_total_seconds: int = 240) -> float:
    """
    Busca preço atual via CoinGecko com tentativas exaustivas.
    - Retry infinito (limitado por tempo máximo)
    - Backoff exponencial com jitter
    - Cache em memória + arquivo (TTL 1h)
    - Retorna 0 só se símbolo inválido ou tempo esgotado.
    """
    sym = symbol.upper()
    start_time = datetime.now()

    # 1. Cache em memória
    if sym in _PRICE_MEM_CACHE:
        ts, price = _PRICE_MEM_CACHE[sym]
        if (datetime.now() - ts).total_seconds() < 3600:
            return price

    # 2. Cache persistente
    persistent_cache = _load_price_cache()
    if sym in persistent_cache:
        ts_str = persistent_cache[sym].get('timestamp')
        price = persistent_cache[sym].get('price', 0)
        if ts_str and price > 0:
            try:
                ts = datetime.fromisoformat(ts_str)
                if (datetime.now() - ts).total_seconds() < 3600:
                    _PRICE_MEM_CACHE[sym] = (ts, price)
                    return price
            except:
                pass

    attempt = 0
    delay = 3.0

    while (datetime.now() - start_time).total_seconds() < max_total_seconds:
        try:
            # Busca via search
            search_url = f"https://api.coingecko.com/api/v3/search?query={symbol.lower()}"
            r = requests.get(search_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})

            if r.status_code == 200:
                data = r.json()
                coins = data.get('coins', [])
                if coins:
                    coin_id = coins[0]['id']
                    price_url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
                    r2 = requests.get(price_url, timeout=10)
                    if r2.status_code == 200:
                        price_data = r2.json()
                        price = price_data.get(coin_id, {}).get('usd', 0)
                        if price > 0:
                            _PRICE_MEM_CACHE[sym] = (datetime.now(), price)
                            persistent_cache[sym] = {'timestamp': datetime.now().isoformat(), 'price': price}
                            _save_price_cache(persistent_cache)
                            return price

            # Fallback: busca direta
            fallback_url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}"
            r3 = requests.get(fallback_url, timeout=10)
            if r3.status_code == 200:
                coin_data = r3.json()
                price = coin_data.get('market_data', {}).get('current_price', {}).get('usd', 0)
                if price > 0:
                    _PRICE_MEM_CACHE[sym] = (datetime.now(), price)
                    persistent_cache[sym] = {'timestamp': datetime.now().isoformat(), 'price': price}
                    _save_price_cache(persistent_cache)
                    return price

            # Símbolo não encontrado (404 ou sem coins)
            if r.status_code == 404 or (r.status_code == 200 and not coins):
                print(f"❌ Símbolo {symbol} não encontrado na CoinGecko")
                return 0.0

        except Exception as e:
            print(f"⚠️ Tentativa {attempt+1} para {symbol} falhou: {e}")

        # Backoff exponencial com jitter (máx 60s)
        delay = min(delay * 2, 60)
        wait = delay * random.uniform(0.8, 1.5)
        print(f"⏳ Aguardando {wait:.1f}s antes de tentar novamente ({symbol})...")
        time.sleep(wait)
        attempt += 1

    # Fallback: usa último preço do cache mesmo expirado
    if sym in persistent_cache:
        old_price = persistent_cache[sym].get('price', 0)
        if old_price > 0:
            print(f"⚠️ Usando preço antigo em cache para {symbol}: ${old_price:.4f}")
            return old_price

    print(f"❌ Não foi possível obter preço para {symbol} após {max_total_seconds}s")
    return 0.0

def update_all_pending_performances() -> int:
    results = _load_results()
    perf    = _load_performance()
    perf_keys = {(p["symbol"], p.get("analysis_date", p["date"])) for p in perf}
    now = datetime.now()
    updated = 0

    for cycle in ("weekly", "monthly"):
        result = results.get(cycle)
        if not result:
            continue
        regime = result.get("market_regime", "UNKNOWN")
        gen_at = result.get("generated_at", "")
        if not gen_at:
            continue
        try:
            pick_date_obj = datetime.fromisoformat(gen_at.replace(" ", "T")).date()
            pick_date_str = str(pick_date_obj)
        except Exception:
            continue

        days_needed = 7 if cycle == "weekly" else 30
        if (now.date() - pick_date_obj).days < days_needed:
            continue

        for pick in result.get("top_picks", []):
            sym = pick.get("symbol", "")
            price_at_pick = pick.get("price_usd")
            if not sym or not price_at_pick:
                continue
            if (sym, pick_date_str) in perf_keys:
                continue
            price_now = _fetch_coingecko_price(sym)
            if price_now > 0:
                register_performance(cycle, sym, pick.get("rank", 0), price_at_pick, price_now,
                                     market_regime=regime, analysis_date=pick_date_str)
                perf_keys.add((sym, pick_date_str))
                updated += 1
    return updated

def auto_update_performance() -> int:
    """
    Busca preços atuais via CoinGecko para todas as picks ainda não registradas.
    Chamado automaticamente ao abrir a aba AI Filter.
    Retorna número de entradas atualizadas.
    """
    results = _load_results()
    perf    = _load_performance()
    updated = 0
    perf_keys = {(p["symbol"], p.get("analysis_date", p["date"])) for p in perf}

    for cycle in ("weekly", "monthly"):
        result = results.get(cycle)
        if not result:
            continue
        regime = result.get("market_regime", "UNKNOWN")
        pick_date = result.get("generated_at", "")[:10]
        top_picks = result.get("top_picks", [])
        total_picks = len(top_picks)

        for idx, pick in enumerate(top_picks):
            sym = pick.get("symbol", "")
            price_at_pick = pick.get("price_usd")
            if not sym or not price_at_pick or price_at_pick <= 0:
                continue
            if (sym, pick_date) in perf_keys:
                continue

            # 🔁 Busca preço atual com timeout de 240 segundos (4 minutos)
            price_now = _fetch_coingecko_price(sym, max_total_seconds=240)

            if price_now > 0:
                register_performance(cycle, sym, pick.get("rank", 0), price_at_pick, price_now,
                                     market_regime=regime, analysis_date=pick_date)
                perf_keys.add((sym, pick_date))
                updated += 1
                print(f"[PERF] ✅ {sym} atualizado: {price_now:.4f} (variação {((price_now-price_at_pick)/price_at_pick*100):+.2f}%)")
            else:
                print(f"[PERF] ❌ Falha ao obter preço para {sym}")

            # ⏱️ Delay de 3 segundos entre picks (exceto após o último)
            if idx < total_picks - 1:
                time.sleep(3)

        # ⏱️ Delay de 5 segundos entre ciclos (weekly → monthly)
        time.sleep(5)

    try:
        evaluate_pending_macro_signals()
        evaluate_pending_detailed_signals()
        evaluate_macro_regime_cycles()
    except Exception:
        pass

    return updated


def register_performance(cycle: str, symbol: str, rank: int,
                          price_at_pick: float, price_now: float,
                          market_regime: str = "UNKNOWN",
                          ml_score: Optional[float] = None,
                          analysis_date: Optional[str] = None):
    """
    Registra o resultado real de uma pick.
    analysis_date: data da análise no formato "YYYY-MM-DD" (opcional)
    """
    try:
        # Se ml_score não foi fornecido, tentar buscar do resultado salvo
        if ml_score is None:
            if analysis_date is None:
                analysis_date = datetime.now().strftime("%Y-%m-%d")
            ml_score = _get_ml_score_for_pick(cycle, symbol, analysis_date)

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
            "market_regime": market_regime,
            "result":        "WIN" if pct > 10 else ("LOSS" if pct < -10 else "NEUTRAL"),
            "ml_score":      ml_score,
            "analysis_date": analysis_date,  # guardar também para referência
        })
        _save_performance(perf[-500:])
    except Exception:
        pass

def get_performance_dashboard(lookback_picks: int = 60) -> dict:
    """
    Retorna estatísticas de performance para exibição na UI.
    """
    perf = _load_performance()
    if not perf:
        return {"error": "Nenhuma performance registrada ainda."}

    recent = perf[-lookback_picks:]
    if not recent:
        return {"error": "Sem dados recentes."}

    # Classifica picks com base no pct_change
    winners = [p for p in recent if p.get("pct_change", 0) > 10]
    losers  = [p for p in recent if p.get("pct_change", 0) < -10]
    neutrals = [p for p in recent if -10 <= p.get("pct_change", 0) <= 10]

    total = len(recent)
    win_rate = len(winners) / total * 100 if total else 0
    loss_rate = len(losers) / total * 100 if total else 0

    avg_win = sum(p.get("pct_change", 0) for p in winners) / len(winners) if winners else 0
    avg_loss = sum(p.get("pct_change", 0) for p in losers) / len(losers) if losers else 0
    risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    # Melhores e piores
    best = sorted(winners, key=lambda x: x.get("pct_change", 0), reverse=True)[:5]
    worst = sorted(losers, key=lambda x: x.get("pct_change", 0))[:3]

    # Por ciclo
    cycle_stats = {}
    for cycle in ["weekly", "monthly"]:
        picks_cycle = [p for p in recent if p.get("cycle") == cycle]
        wins_cycle = [p for p in picks_cycle if p.get("pct_change", 0) > 10]
        cycle_stats[cycle] = {
            "total": len(picks_cycle),
            "wins": len(wins_cycle),
            "win_rate": len(wins_cycle) / len(picks_cycle) * 100 if picks_cycle else 0
        }

    # Por rank (agrupa ranks)
    rank_stats = {}
    for p in recent:
        r = str(p.get("rank", "?"))
        # Agrupa ranks 3-5 como "3-5"
        if r in ("3","4","5"):
            r = "3-5"
        if r not in rank_stats:
            rank_stats[r] = {"total": 0, "wins": 0, "sum_pct": 0}
        rank_stats[r]["total"] += 1
        rank_stats[r]["sum_pct"] += p.get("pct_change", 0)
        if p.get("pct_change", 0) > 10:
            rank_stats[r]["wins"] += 1
    for r in rank_stats:
        rank_stats[r]["win_rate"] = rank_stats[r]["wins"] / rank_stats[r]["total"] * 100 if rank_stats[r]["total"] else 0
        rank_stats[r]["avg_pct"] = rank_stats[r]["sum_pct"] / rank_stats[r]["total"]

    # Classificação da qualidade do sistema
    quality = "❌ Ruim (melhor que aleatório?)"
    if win_rate > 60 and rank_stats.get("1", {}).get("win_rate", 0) > 70:
        quality = "🔥 Excelente – confiável para operações"
    elif win_rate > 55 and rank_stats.get("1", {}).get("win_rate", 0) > 65:
        quality = "👍 Bom – com margem de segurança"
    elif win_rate > 50:
        quality = "⚖️ Neutro – pouco melhor que aleatório"

    return {
        "total_picks": total,
        "win_rate": round(win_rate, 1),
        "loss_rate": round(loss_rate, 1),
        "avg_win": round(avg_win, 1),
        "avg_loss": round(avg_loss, 1),
        "risk_reward": round(risk_reward, 2),
        "best_picks": [{"symbol": p["symbol"], "pct": p["pct_change"], "rank": p["rank"], "cycle": p["cycle"]} for p in best],
        "worst_picks": [{"symbol": p["symbol"], "pct": p["pct_change"], "rank": p["rank"], "cycle": p["cycle"]} for p in worst],
        "cycle_stats": cycle_stats,
        "rank_stats": rank_stats,
        "quality": quality
    }

def get_ml_performance() -> dict:
    """Retorna estatísticas de acurácia do modelo de ML."""
    perf = _load_performance()
    if not perf:
        return {"error": "Nenhuma performance registrada."}

    total = 0
    correct = 0
    for p in perf:
        ml_score = p.get("ml_score")
        if ml_score is None:
            continue
        total += 1
        pred_win = ml_score > 0.5
        actual_win = p.get("result") == "WIN"
        if pred_win == actual_win:
            correct += 1
    if total == 0:
        return {"error": "Nenhum pick com ml_score registrado ainda."}
    return {
        "total": total,
        "accuracy": round(correct / total * 100, 1),
        "correct": correct,
    }

def get_history() -> list:
    """Retorna histórico de execuções (ciclo, timestamp, n_coins analisadas)."""
    return _load_results().get("history", [])


def get_aggregated_data(max_age_days: int = 7) -> pd.DataFrame:
    """Expõe o DataFrame agregado para visualização na UI."""
    full = _load_csvs(max_age_days)
    if full.empty:
        return pd.DataFrame()
    return _aggregate(full)

def _get_current_macro_regime() -> str:
    """Retorna a classificação do regime macro atual baseada no macro_timing.json."""
    macro = _load_macro()
    if not macro:
        return "UNKNOWN"

    regime = macro.get("regime", {})
    signal = macro.get("signal", {})

    buy_mode = regime.get("buy_mode", False)
    sell_mode = regime.get("sell_mode", False)
    weekly_buy = signal.get("weekly_buy_trigger", False)
    weekly_sell = signal.get("weekly_sell_trigger", False)
    funding = float(macro.get("funding_rate", 0))
    cap_lock = regime.get("capitulation_lock", False)
    rebound = signal.get("tactical_rebound", False)

    # Mesma hierarquia do HUD
    regime_result = "NEUTRO"
    if buy_mode and weekly_buy and funding < 0:
        regime_result = "SUPER_BUY"
    elif buy_mode and weekly_buy:
        regime_result = "BUY_CONFIRMED"
    elif buy_mode:
        regime_result = "BUY_MACRO"
    elif sell_mode and weekly_sell and funding > 0.08:
        regime_result = "SUPER_SELL"
    elif sell_mode and weekly_sell:
        regime_result = "SELL_CONFIRMED"
    elif sell_mode and cap_lock:
        regime_result = "CAPITULATION"
    elif sell_mode and rebound:
        regime_result = "SELL_REBOUND"
    elif sell_mode:
        regime_result = "SELL_MACRO"
    # else: regime_result já "NEUTRO"

    # ── REGISTRO DE SINAL MACRO (regime) ──
    try:
        signals = _load_macro_signals()
        last = signals[-1] if signals else None
        now = datetime.now()
        if (not last or last.get("regime") != regime_result or
            (now - datetime.fromisoformat(last["timestamp"])).days >= 1):
            btc_ctx = _fetch_btc_context()
            signals.append({
                "timestamp": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "regime": regime_result,
                "buy_mode": buy_mode,
                "sell_mode": sell_mode,
                "weekly_buy": weekly_buy,
                "weekly_sell": weekly_sell,
                "funding_rate": funding,
                "btc_price_usd": btc_ctx.get("btc_price", 0.0),
                "evaluated_7d": False,
                "outcome_7d": None,
                "evaluated_30d": False,
                "outcome_30d": None,
            })
            _save_macro_signals(signals)
    except Exception as e:
        print(f"⚠️ Erro ao registrar sinal macro: {e}")

    # ── REGISTRO DE SINAIS DETALHADOS (entradas) ──
    try:
        current_signal_states = {
            "weekly_buy": weekly_buy,
            "weekly_sell": weekly_sell,
            "rebound": rebound,
            "rebound_super": bool(rebound and funding < 0),
            "super_buy": (buy_mode and weekly_buy and funding < 0),
            "super_sell": (sell_mode and weekly_sell and funding > 0.08)
        }

        global _last_signal_states
        for signal_name, current in current_signal_states.items():
            previous = _last_signal_states.get(signal_name, False)
            if current and not previous:
                # Sinal ativado agora
                btc_ctx = _fetch_btc_context()
                new_signal = {
                    "timestamp": datetime.now().isoformat(),
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "signal": signal_name,
                    "btc_price_usd": btc_ctx.get("btc_price", 0.0),
                    "regime_at_signal": regime_result,
                    "evaluated": False,
                    "outcome": None,
                    "exit_timestamp": None,
                    "exit_price": None,
                    "return_pct": None
                }
                detailed = _load_detailed_macro_signals()
                detailed.append(new_signal)
                _save_detailed_macro_signals(detailed)
                print(f"📢 Novo sinal detalhado: {signal_name} em {new_signal['date']}")
            _last_signal_states[signal_name] = current
    except Exception as e:
        print(f"⚠️ Erro ao registrar sinal detalhado: {e}")

    return regime_result
