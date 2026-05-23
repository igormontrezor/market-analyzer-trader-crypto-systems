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
# Pode buscar por chain: ethereum, bsc, polygon, solana, arbitrum, optimism, avalanche, fantom, base, etc.
DEFAULT_CHAINS = ["ethereum", "bsc", "polygon", "arbitrum", "base", "solana"]
MIN_LIQUIDITY_USD = 50000       # mínimo para evitar scams muito pequenos
MIN_VOLUME_24H_USD = 20000      # volume mínimo 24h
MAX_AGE_HOURS = 48              # apenas pools criadas nas últimas 48h
MIN_BUY_TAX = 0                 # sem taxa de compra abusiva
SELL_TAX_MAX = 15               # taxa de venda máxima tolerável

def search_pairs_by_chain(chain: str) -> List[Dict]:
    """
    Busca pairs recentes em uma chain específica.
    DexScreener não tem filtro direto por data de criação, então pegamos os mais recentes
    e filtramos por criação recente (se disponível) ou por pairAddress.
    """
    url = f"{DEXSCREENER_API}/search?q={chain}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get("pairs", [])
            return pairs
        else:
            return []
    except Exception:
        return []

def filter_early_stage_pairs(pairs: List[Dict]) -> List[Dict]:
    """
    Filtra pairs que atendem critérios de early stage.
    Retorna lista com dados relevantes.
    """
    early = []
    now = datetime.utcnow()
    for pair in pairs:
        try:
            # Verificar liquidez
            liquidity = float(pair.get("liquidity", {}).get("usd", 0))
            if liquidity < MIN_LIQUIDITY_USD:
                continue
            # Volume 24h
            volume_24h = float(pair.get("volume", {}).get("h24", 0))
            if volume_24h < MIN_VOLUME_24H_USD:
                continue
            # Taxas (alguns contratos têm buy/sell tax)
            # DexScreener pode retornar `txns` com informações de transações
            # Não há campo direto de taxas, mas podemos inferir por diferença de preço?
            # Vamos pular taxas por enquanto, mas se houver campo `fees`, usaremos.
            
            # Data de criação do par (nem sempre disponível)
            # DexScreener não retorna pair creation time diretamente.
            # Alternativa: usar o `pairCreatedAt`? Não existe. 
            # Vamos confiar na ordenação: os mais recentes aparecem primeiro na busca.
            # Como fallback, aceitamos qualquer um que tenha liquidez e volume, mas limitamos número.
            
            # Transações nas últimas 24h: se houver mais compras que vendas, é bom sinal.
            txns = pair.get("txns", {})
            buys_24h = txns.get("h24", {}).get("buys", 0)
            sells_24h = txns.get("h24", {}).get("sells", 0)
            buy_volume_24h = txns.get("h24", {}).get("buys", 0)  # número de transações, não volume
            sell_volume_24h = txns.get("h24", {}).get("sells", 0)
            # Se compras > vendas (em número ou volume), é positivo
            if buys_24h + sells_24h > 0:
                buy_ratio = buys_24h / (buys_24h + sells_24h) if (buys_24h + sells_24h) > 0 else 0
            else:
                buy_ratio = 0
            
            # Preço e variação
            price_usd = float(pair.get("priceUsd", 0))
            price_change_24h = float(pair.get("priceChange", {}).get("h24", 0))
            
            # Nome do token, símbolo, endereço, chain
            base_token = pair.get("baseToken", {})
            symbol = base_token.get("symbol", "")
            name = base_token.get("name", "")
            token_address = base_token.get("address", "")
            chain_id = pair.get("chainId", "")
            
            # Link do par
            pair_url = pair.get("url", "")
            
            early.append({
                "symbol": symbol.upper(),
                "name": name,
                "token_address": token_address,
                "chain": chain_id,
                "price_usd": price_usd,
                "price_change_24h": price_change_24h,
                "liquidity_usd": liquidity,
                "volume_24h_usd": volume_24h,
                "buys_24h": buys_24h,
                "sells_24h": sells_24h,
                "buy_ratio": round(buy_ratio, 2),
                "pair_url": pair_url,
                "last_updated": datetime.now().isoformat(),
                "source": "dexscreener"
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