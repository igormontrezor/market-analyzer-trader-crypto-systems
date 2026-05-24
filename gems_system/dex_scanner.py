"""
dex_scanner.py
Módulo para buscar tokens em estágio inicial via DexScreener API.
Foco: novas pools, liquidez travada, volume crescente, atividade de compra.
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuração
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
DEFAULT_CHAINS = ["ethereum", "bsc", "solana", "base", "arbitrum"]
MIN_LIQUIDITY_USD   = 30_000    # mínimo para evitar scams
MAX_LIQUIDITY_USD   = 2_000_000 # máximo — acima disso não é early stage
MIN_VOLUME_24H_USD  = 10_000    # volume mínimo 24h
MAX_VOLUME_24H_USD  = 5_000_000 # acima disso é projeto grande
MAX_MCAP_USD        = 10_000_000 # market cap máximo $10M — small cap real
MIN_BUY_RATIO       = 0.52      # mais compradores que vendedores
MAX_AGE_HOURS       = 72        # pools criadas nas últimas 72h (se disponível)
# Tokens grandes conhecidos para excluir (evitar BTC/ETH/SOL wrappers)
EXCLUDE_SYMBOLS = {"BTC","ETH","SOL","BNB","USDT","USDC","DAI","WBTC","WETH","WSOL",
                   "WBNB","MATIC","AVAX","ARB","OP","BASE","LINK","UNI","AAVE","PEPE"}

def search_pairs_by_chain(chain: str) -> List[Dict]:
    """
    Busca pairs em alta por chain via DexScreener /token-boosts/latest/v1
    e /search como fallback. Retorna só tokens small cap em momentum.
    """
    pairs = []
    # Tentar endpoint de tokens em boost (mais relevante para early stage)
    try:
        url_boost = "https://api.dexscreener.com/token-boosts/latest/v1"
        r = requests.get(url_boost, timeout=12)
        if r.status_code == 200:
            for item in r.json() if isinstance(r.json(), list) else []:
                if item.get("chainId","").lower() == chain.lower():
                    # Buscar dados do par pelo tokenAddress
                    addr = item.get("tokenAddress","")
                    if addr:
                        r2 = requests.get(f"{DEXSCREENER_API}/tokens/{addr}", timeout=8)
                        if r2.status_code == 200:
                            pairs.extend(r2.json().get("pairs",[]) or [])
    except Exception:
        pass

    # Fallback: buscar por query de chain + "new"
    if not pairs:
        try:
            url = f"{DEXSCREENER_API}/search?q=new+{chain}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                pairs = r.json().get("pairs", [])
        except Exception:
            pass

    return pairs

def filter_early_stage_pairs(pairs: List[Dict]) -> List[Dict]:
    """
    Filtra por critérios reais de early stage:
    - Liquidez: $30k-$2M (abaixo = scam, acima = projeto grande)
    - Volume 24h: $10k-$5M
    - Market cap: < $10M (small cap real)
    - Buy ratio > 52% (mais compradores)
    - Exclui tokens grandes conhecidos (BTC, ETH, SOL, stablecoins etc)
    - Exclui tokens sem símbolo ou endereço
    """
    early = []
    for pair in pairs:
        try:
            base_token    = pair.get("baseToken", {})
            symbol        = base_token.get("symbol", "").upper().strip()
            name          = base_token.get("name", "")
            token_address = base_token.get("address", "")
            chain_id      = pair.get("chainId", "")

            if not symbol or not token_address:
                continue
            if symbol in EXCLUDE_SYMBOLS:
                continue
            # Ignorar tokens que são wrappers (começam com W + símbolo grande)
            if len(symbol) > 1 and symbol[0] == "W" and symbol[1:] in EXCLUDE_SYMBOLS:
                continue

            liquidity  = float(pair.get("liquidity", {}).get("usd", 0))
            volume_24h = float(pair.get("volume", {}).get("h24", 0))
            mcap       = float(pair.get("marketCap") or pair.get("fdv") or 0)

            if liquidity  < MIN_LIQUIDITY_USD  or liquidity  > MAX_LIQUIDITY_USD:  continue
            if volume_24h < MIN_VOLUME_24H_USD or volume_24h > MAX_VOLUME_24H_USD: continue
            if mcap > 0 and mcap > MAX_MCAP_USD: continue  # só checar se disponível

            txns      = pair.get("txns", {}).get("h24", {})
            buys_24h  = int(txns.get("buys",  0))
            sells_24h = int(txns.get("sells", 0))
            total_txns= buys_24h + sells_24h
            buy_ratio = buys_24h / total_txns if total_txns > 0 else 0

            if buy_ratio < MIN_BUY_RATIO: continue

            price_usd        = float(pair.get("priceUsd") or 0)
            price_change_24h = float((pair.get("priceChange") or {}).get("h24", 0))
            pair_url         = pair.get("url", "")

            # Idade do par (se disponível)
            pair_created_at = pair.get("pairCreatedAt")
            age_hours = None
            if pair_created_at:
                try:
                    created = datetime.utcfromtimestamp(pair_created_at / 1000)
                    age_hours = (datetime.utcnow() - created).total_seconds() / 3600
                    if age_hours > MAX_AGE_HOURS: continue
                except Exception:
                    pass

            early.append({
                "symbol":            symbol,
                "name":              name,
                "token_address":     token_address,
                "chain":             chain_id,
                "price_usd":         price_usd,
                "price_change_24h":  price_change_24h,
                "market_cap_usd":    mcap,
                "liquidity_usd":     liquidity,
                "volume_24h_usd":    volume_24h,
                "buys_24h":          buys_24h,
                "sells_24h":         sells_24h,
                "buy_ratio":         round(buy_ratio, 2),
                "age_hours":         round(age_hours, 1) if age_hours is not None else None,
                "pair_url":          pair_url,
                "last_updated":      datetime.now().isoformat(),
                "source":            "dexscreener"
            })
        except Exception:
            continue
    return early

def get_early_stage_tokens(limit_per_chain: int = 20) -> pd.DataFrame:
    """
    Função principal para varrer chains e retornar DataFrame com tokens early stage.
    """
    all_pairs = []
    for chain in DEFAULT_CHAINS:
        pairs = search_pairs_by_chain(chain)
        if pairs:
            early = filter_early_stage_pairs(pairs)
            all_pairs.extend(early[:limit_per_chain])
        time.sleep(1)  # respeitar rate limit
    df = pd.DataFrame(all_pairs)
    if not df.empty:
        # Remover duplicatas pelo token_address (pode aparecer em múltiplos pairs)
        df = df.drop_duplicates(subset=["token_address"], keep="first")
        # Ordenar por score simples: volume + liquidez + buy_ratio
        df["dex_score"] = (df["volume_24h_usd"] / 1000) + (df["liquidity_usd"] / 10000) + (df["buy_ratio"] * 100)
        df = df.sort_values("dex_score", ascending=False)
    return df

# Se executado diretamente, mostra exemplo
if __name__ == "__main__":
    df = get_early_stage_tokens(limit_per_chain=10)
    print(df.head(10).to_string())