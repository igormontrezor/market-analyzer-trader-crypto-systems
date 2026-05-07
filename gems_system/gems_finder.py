"""
GEMS FINDER - Abordagem inteligente para encontrar gems
Busca em ordem descendente para encontrar moedas com MC válido rapidamente
"""

import requests
import time
import json
import os
import io
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd
from accumulation_sector import (
    SilentAccumulationDetector,
    SectorCorrelationAnalyzer,
    enrich_gems_with_accumulation,
    build_sector_snapshot,
    load_sector_historical,
    print_accumulation_report,
    print_sector_report,
    get_sector,
)

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class GemsFinder:

    CACHE_FILE = "gems_cache.json"
    CACHE_DURATION = timedelta(hours=0)  # Forçar busca sempre (cache de 0 horas)

    def __init__(self):
        self.cache_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_path = os.path.join(self.cache_dir, 'gems_cache.json')
        self.snapshots_dir = os.path.join(self.cache_dir, 'snapshots')
        os.makedirs(self.snapshots_dir, exist_ok=True)
        self.daily_snapshots_dir = os.path.join(self.cache_dir, 'daily_snapshots')
        os.makedirs(self.daily_snapshots_dir, exist_ok=True)

        # Social Analyzer (Camada 4) - YouTube + Telegram
        self.social_analyzer = None
        try:
            from social_analyzer_yt_telegram import SocialAnalyzerYTTelegram as _SocialAnalyzerYTTelegram
        except Exception as e:
            print(f"⚠️ SocialAnalyzer desativado (falha no import): {e}")
        else:
            try:
                self.social_analyzer = _SocialAnalyzerYTTelegram()
            except Exception as e:
                print(f"⚠️ SocialAnalyzer desativado (falha ao inicializar): {e}")
                self.social_analyzer = None
        self.confirmed_gems_file = os.path.join(self.cache_dir, 'confirmed_gems.json')
        self.new_candidates_file = os.path.join(self.cache_dir, 'new_candidates.json')

        # Módulos de acumulação e setor
        self.accumulation_detector  = SilentAccumulationDetector()
        self.sector_analyzer        = SectorCorrelationAnalyzer()

        self.macro_dir = os.path.join(self.cache_dir, 'macro')
        os.makedirs(self.macro_dir, exist_ok=True)
        self.macro_timing_path = os.path.join(self.macro_dir, 'macro_timing.json')
        self.macro_raw_cache_path = os.path.join(self.macro_dir, 'macro_raw_cache.json')

    def _coingecko_get(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 20) -> Any:
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r.json()
        except Exception as e:
            raise RuntimeError(f"Falha ao acessar CoinGecko: {e}")

    def _load_macro_raw_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not os.path.exists(self.macro_raw_cache_path):
                return None
            with open(self.macro_raw_cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_macro_raw_cache(self, payload: Dict[str, Any]) -> None:
        try:
            with open(self.macro_raw_cache_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            return

    def _bb_percent(self, series: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.Series:
        ma = series.rolling(period, min_periods=period).mean()
        sd = series.rolling(period, min_periods=period).std(ddof=0)
        upper = ma + std_mult * sd
        lower = ma - std_mult * sd
        width = (upper - lower)
        bbp = (series - lower) / width
        return bbp

    def build_macro_timing(self,
                           days: int = 730,
                           bb_period: int = 20,
                           bb_std: float = 2.0,
                           cache_hours: int = 12) -> Optional[Dict[str, Any]]:

        now = datetime.now()
        cached = self._load_macro_raw_cache()
        if isinstance(cached, dict):
            fetched_at = cached.get('fetched_at')
            try:
                fetched_at_dt = datetime.fromisoformat(fetched_at) if fetched_at else None
            except Exception:
                fetched_at_dt = None
            if fetched_at_dt and (now - fetched_at_dt) < timedelta(hours=cache_hours):
                raw = cached.get('raw')
            else:
                raw = None
        else:
            raw = None

        if raw is None:
            base = "https://api.coingecko.com/api/v3"
            total_chart = self._coingecko_get(
                f"{base}/global/market_cap_chart",
                params={"vs_currency": "usd", "days": days}
            )

            top10 = self._coingecko_get(
                f"{base}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 10,
                    "page": 1,
                    "sparkline": False
                }
            )
            top10_ids = [c.get('id') for c in top10 if isinstance(c, dict) and c.get('id')]

            top10_charts = {}
            for cid in top10_ids:
                data = self._coingecko_get(
                    f"{base}/coins/{cid}/market_chart",
                    params={"vs_currency": "usd", "days": days}
                )
                top10_charts[cid] = data.get('market_caps', []) if isinstance(data, dict) else []

            usdt_chart = self._coingecko_get(
                f"{base}/coins/tether/market_chart",
                params={"vs_currency": "usd", "days": days}
            )

            raw = {
                "total_market_cap": total_chart.get('market_cap', []) if isinstance(total_chart, dict) else [],
                "top10_ids": top10_ids,
                "top10_market_caps": top10_charts,
                "usdt_market_caps": usdt_chart.get('market_caps', []) if isinstance(usdt_chart, dict) else [],
            }
            self._save_macro_raw_cache({"fetched_at": now.isoformat(), "raw": raw})

        try:
            total_points = raw.get('total_market_cap', [])
            if not total_points:
                return None

            total_df = pd.DataFrame(total_points, columns=['ts', 'total_mc'])
            total_df['dt'] = pd.to_datetime(total_df['ts'], unit='ms')
            total_df = total_df.dropna(subset=['dt']).set_index('dt').sort_index()
            total = total_df['total_mc'].astype(float)

            top10_sum = pd.Series(0.0, index=total.index)
            for cid, pts in (raw.get('top10_market_caps') or {}).items():
                if not pts:
                    continue
                df = pd.DataFrame(pts, columns=['ts', 'mc'])
                df['dt'] = pd.to_datetime(df['ts'], unit='ms')
                df = df.dropna(subset=['dt']).set_index('dt').sort_index()
                s = df['mc'].astype(float).reindex(total.index, method='nearest')
                top10_sum = top10_sum.add(s.ffill().bfill(), fill_value=0.0)

            usdt_pts = raw.get('usdt_market_caps', [])
            usdt_df = pd.DataFrame(usdt_pts, columns=['ts', 'usdt_mc'])
            usdt_df['dt'] = pd.to_datetime(usdt_df['ts'], unit='ms')
            usdt_df = usdt_df.dropna(subset=['dt']).set_index('dt').sort_index()
            usdt_mc = usdt_df['usdt_mc'].astype(float).reindex(total.index, method='nearest')
            usdt_mc = usdt_mc.ffill().bfill()

            others_mc = (total - top10_sum).clip(lower=0.0)
            usdt_d = (usdt_mc / total).clip(lower=0.0)

            weekly_total = total.resample('W').last()
            weekly_others = others_mc.resample('W').last()
            weekly_usdt_d = usdt_d.resample('W').last()

            monthly_total = total.resample('M').last()
            monthly_others = others_mc.resample('M').last()
            monthly_usdt_d = usdt_d.resample('M').last()

            weekly_others_bbp = self._bb_percent(weekly_others, period=bb_period, std_mult=bb_std)
            weekly_usdt_bbp = self._bb_percent(weekly_usdt_d, period=bb_period, std_mult=bb_std)
            monthly_others_bbp = self._bb_percent(monthly_others, period=bb_period, std_mult=bb_std)
            monthly_usdt_bbp = self._bb_percent(monthly_usdt_d, period=bb_period, std_mult=bb_std)

            last_week = weekly_others_bbp.dropna().index.max() if not weekly_others_bbp.dropna().empty else None
            last_month = monthly_usdt_bbp.dropna().index.max() if not monthly_usdt_bbp.dropna().empty else None

            def _to_float(v):
                try:
                    return float(v)
                except Exception:
                    return None

            weekly_state = {
                "date": last_week.strftime('%Y-%m-%d') if last_week else None,
                "others_bbp": _to_float(weekly_others_bbp.loc[last_week]) if last_week else None,
                "usdt_d_bbp": _to_float(weekly_usdt_bbp.loc[last_week]) if last_week else None,
                "others_touch_low": bool(last_week and weekly_others_bbp.loc[last_week] < 0),
                "others_touch_high": bool(last_week and weekly_others_bbp.loc[last_week] > 1),
                "usdt_touch_low": bool(last_week and weekly_usdt_bbp.loc[last_week] < 0),
                "usdt_touch_high": bool(last_week and weekly_usdt_bbp.loc[last_week] > 1),
            }

            monthly_state = {
                "date": last_month.strftime('%Y-%m-%d') if last_month else None,
                "others_bbp": _to_float(monthly_others_bbp.loc[last_month]) if last_month else None,
                "usdt_d_bbp": _to_float(monthly_usdt_bbp.loc[last_month]) if last_month else None,
                "others_touch_low": bool(last_month and monthly_others_bbp.loc[last_month] < 0),
                "others_touch_high": bool(last_month and monthly_others_bbp.loc[last_month] > 1),
                "usdt_touch_low": bool(last_month and monthly_usdt_bbp.loc[last_month] < 0),
                "usdt_touch_high": bool(last_month and monthly_usdt_bbp.loc[last_month] > 1),
            }

            monthly_usdt_bbp_clean = monthly_usdt_bbp.dropna()
            usdt_exit_from_top = False
            if len(monthly_usdt_bbp_clean) >= 2:
                prev = monthly_usdt_bbp_clean.iloc[-2]
                curr = monthly_usdt_bbp_clean.iloc[-1]
                usdt_exit_from_top = bool(prev > 1 and curr <= 1)

            regime = {
                "buy_mode": bool(usdt_exit_from_top),
                "sell_mode": bool(monthly_state["usdt_touch_low"]),
                "usdt_exit_from_top": bool(usdt_exit_from_top),
            }

            signal = {
                "weekly_buy_trigger": bool(regime["buy_mode"] and weekly_state["others_touch_low"]),
                "weekly_sell_trigger": bool(regime["sell_mode"] and weekly_state["others_touch_high"]),
            }

            payload = {
                "generated_at": now.isoformat(),
                "config": {
                    "days": days,
                    "bb_period": bb_period,
                    "bb_std": bb_std,
                    "others_definition": "TOTAL_MC - sum(TOP10_MC)",
                    "touch_low": "bbp < 0",
                    "touch_high": "bbp > 1",
                },
                "weekly": weekly_state,
                "monthly": monthly_state,
                "regime": regime,
                "signal": signal,
                "latest": {
                    "others_mc": _to_float(others_mc.iloc[-1]) if not others_mc.empty else None,
                    "usdt_d": _to_float(usdt_d.iloc[-1]) if not usdt_d.empty else None,
                    "total_mc": _to_float(total.iloc[-1]) if not total.empty else None,
                }
            }

            try:
                with open(self.macro_timing_path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

            return payload

        except Exception:
            return None

    def load_cache(self) -> Optional[Dict[str, Any]]:
        """Carrega dados do cache se ainda for válido"""
        try:
            if not os.path.exists(self.cache_path):
                return None

            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # ✅ CORREÇÃO: Validar timestamps antes de converter
            timestamp_str = cache_data.get('timestamp', '')
            expires_at_str = cache_data.get('expires_at', '')

            if not timestamp_str or not expires_at_str:
                print("⚠️ Cache inválido: timestamps ausentes")
                return None

            try:
                cache_time = datetime.fromisoformat(timestamp_str)
                expires_at = datetime.fromisoformat(expires_at_str)
            except ValueError as e:
                print(f"⚠️ Cache inválido: timestamps mal formatados - {e}")
                return None

            if datetime.now() >= expires_at:
                print(f"⏰ Cache expirou em: {expires_at.strftime('%H:%M:%S')}")
                return None
            else:
                print(f"✅ Usando cache (válido até: {expires_at.strftime('%H:%M:%S')})")

            # ✅ CORREÇÃO: Retornar cache completo para ter acesso ao cached_time
            return cache_data

        except Exception as e:
            print(f"⚠️ Erro ao carregar cache ({self.cache_path}): {e}")
            return None

    def save_cache(self, data: List[Dict[str, Any]]) -> None:
        """Salva dados no cache"""
        try:
            now = datetime.now()
            cache_data = {
                'cached_time': now,  # ✅ CORREÇÃO: Adicionar cached_time para o código encontrar
                'timestamp': now.isoformat(),
                'expires_at': (now + self.CACHE_DURATION).isoformat(),
                'data': data
            }

            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)

            print(f"💾 Cache salvo. Expira em: {(now + self.CACHE_DURATION).strftime('%H:%M:%S')}")

        except Exception as e:
            print(f"⚠️ Erro ao salvar cache ({self.cache_path}): {e}")
            return

    def find_gems_smart(self,
                       min_market_cap: int = 1_000_000,
                       max_market_cap: int = 50_000_000,
                       min_volume: int = 200_000,
                       max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Busca inteligente de gems:
        1. Começa das moedas maiores (market_cap_desc)
        2. Para quando encontrar suficientes gems
        3. Evita rate limits
        """

        print("💎 GEMS FINDER - Busca inteligente...")
        print(f"🎯 Alvo: MC ${min_market_cap:,}-${max_market_cap:,}, Volume >${min_volume:,}")

        # Tentar cache primeiro
        cached = self.load_cache()
        if cached and isinstance(cached, dict):
            # ✅ CORREÇÃO: Só usar cache se for dict válido
            cache_data = cached.get('data', cached)
            if isinstance(cache_data, list):
                print(f"✅ Usando cache: {len(cache_data)} gems")
                return cache_data[:max_results]
            else:
                print("⚠️ Cache corrompido (data não é lista) - buscando novos dados")
        elif cached:
            print("⚠️ Cache corrompido (não é dict) - buscando novos dados")

        gems = []
        page = 1
        url = "https://api.coingecko.com/api/v3/coins/markets"

        btc_change_24h: Optional[float] = None
        btc_change_7d: Optional[float] = None

        max_pages = 300  # Busca completa sem parada antecipada
        min_mc_found = float('inf')
        target_mc = min_market_cap  # 30M
        reached_target = False

        print(f"🔍 Busca COMPLETA: 50M → {target_mc:,} (até página {max_pages})")
        print(f"⚡ Continuar buscando até encontrar MCs próximos a ${target_mc:,} MESMO com 10+ gems")

        while page <= max_pages and not reached_target:
            print(f"📄 Página {page} (gems encontradas: {len(gems)})...")

            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",  #
                "per_page": 250,
                "page": page,
                "price_change_percentage": "7d,30d",  # 🔥 Para resiliência de preço
                "sparkline": False
            }

            try:
                r = requests.get(url, params=params, timeout=10)

                if r.status_code == 200:
                    coins = r.json()
                    if not coins:
                        break

                    # Processar moedas desta página
                    page_gems_found = 0
                    for coin in coins:
                        symbol = coin.get('symbol')
                        if not symbol:
                            continue

                        if btc_change_24h is None and symbol.lower() == 'btc':
                            btc_change_24h = coin.get('price_change_percentage_24h')
                            btc_change_7d = coin.get('price_change_percentage_7d')

                        market_cap = coin.get('market_cap')
                        volume = coin.get('total_volume', 0) or 0

                        # Ignorar sem market cap
                        if market_cap is None or market_cap <= 0:
                            continue

                        # Verificar se está na faixa de gems
                        if market_cap < min_market_cap:
                            # Atingiu MC abaixo do alvo - continuar buscando mais
                            print(f" MC=${market_cap:,} (abaixo de {target_mc:,}) - continue searching...")
                            # Não parar - continuar buscando até encontrar mais gems abaixo de 30M
                            continue

                        if market_cap > max_market_cap:
                            continue  # Muito grande, pular

                        if volume < min_volume:
                            continue  # Volume baixo demais

                        # 📊 FILTRA RATIO VOLUME/MC (ESSENCIAL) - 3 ZONAS INTELIGENTES
                        volume_mc_ratio = volume / market_cap

                        # 🔴 ZONA 1: Descartar (ratio < 0.2)
                        if volume_mc_ratio < 0.2:
                            print(f"❌ {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (< 0.2) - MORTO - dispensar")
                            continue

                        # 🟡 ZONA 2: Early Accumulation (0.2 <= ratio < 0.5)
                        if 0.2 <= volume_mc_ratio < 0.5:
                            coin['zone'] = 'early_accumulation'  # Fundo real
                            print(f"🟡 {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (0.2-0.5) - ACUMULAÇÃO INICIAL - POTENCIAL FUNDO")

                        # 🟠 ZONA 3: Strong (0.5 <= ratio < 1.0)
                        elif 0.5 <= volume_mc_ratio < 1.0:
                            coin['zone'] = 'strong'
                            print(f"🟠 {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (0.5-1.0) - FORTE - OK")

                        # 🔥 ZONA 4: Breakout (ratio >= 1.0)
                        else:  # ratio >= 1.0
                            coin['zone'] = 'breakout'
                            print(f"🔥 {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (>= 1.0) - BREAKOUT - PRIORIDADE MÁXIMA!")

                        # 🛡️ FILTROS DE QUALIDADE DE VOLUME (NÍVEL INSTITUCIONAL)
                        # A) Verificar se volume não é suspeito (muito alto vs MC sem lógica)
                        if volume_mc_ratio > 3.0:  # Ratio > 3 é extremamente suspeito
                            print(f"⚠️ {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (> 3.0) - VOLUME SUSPEITO - análise manual")
                            # Não descarta, mas marca para atenção

                        # B) Verificar liquidez mínima (evitar armadilhas)
                        # Usamos market_cap como proxy de liquidez (MC baixo + volume alto = suspeito)
                        if market_cap < 20_000_000 and volume_mc_ratio > 1.5:
                            print(f"⚠️ {coin['symbol']}: MC=${market_cap:,} baixo + Vol/MC={volume_mc_ratio:.2f} alto - POSSÍVEL ARMADILHA")
                            # Não descarta, mas alerta

                        # C) Verificar distribuição de volume (via market cap como proxy)
                        # Se MC é muito baixo mas volume é altíssimo, pode ser manipulado
                        if market_cap < 15_000_000 and volume > market_cap * 2:
                            print(f"⚠️ {coin['symbol']}: Volume 2x MC - POSSÍVEL MANIPULAÇÃO - atenção")

                        # 🚨 D) FILTRO ANTI-WASH TRADING - Volume alto sem movimento de preço
                        price_change_24h = coin.get('price_change_percentage_24h', 0)
                        if volume_mc_ratio > 1.5 and abs(price_change_24h) < 2:
                            print(f"🚨 {coin['symbol']}: Volume alto ({volume_mc_ratio:.2f}x MC) + preço parado ({price_change_24h:.2f}%) - POSSÍVEL WASH TRADING - análise manual")
                            # Não descarta, mas marca como suspeito para atenção manual
                            coin['suspected_wash_trading'] = True
                        else:
                            coin['suspected_wash_trading'] = False

                        if volume_mc_ratio >= 1.0:
                            print(f"🔥 {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (>= 1.0) - PRIORIDADE MÁXIMA!")
                        else:
                            print(f"✅ {coin['symbol']}: Vol/MC={volume_mc_ratio:.2f} (>= 0.5) - OK")

                        # 🛡️ FILTRA FDV - Fully Diluted Valuation (AJUSTADO)
                        fdv = coin.get('fully_diluted_valuation')
                        if fdv is not None and fdv > 0 and market_cap > 0:
                            # ✅ CORREÇÃO: Proteger contra divisão por zero
                            fdv_diff_percent = ((fdv - market_cap) / market_cap) * 100
                            if fdv_diff_percent > 80:  # FDV mais de 80% maior que MC (inflação muito alta)
                                print(f"❌ {coin['symbol']}: FDV=${fdv:,} (+{fdv_diff_percent:.1f}% vs MC) - INFLAÇÃO MUITO ALTA - dispensar")
                                continue
                            elif fdv_diff_percent > 30:  # FDV entre 30-80% (atenção)
                                print(f"⚠️ {coin['symbol']}: FDV=${fdv:,} (+{fdv_diff_percent:.1f}% vs MC) - ATENÇÃO - continuar")
                            else:
                                print(f"✅ {coin['symbol']}: FDV=${fdv:,} (+{fdv_diff_percent:.1f}% vs MC) - INFLAÇÃO OK")
                        else:
                            print(f"⚠️ {coin['symbol']}: Sem dados FDV - continuar análise")

                        # �️ FILTRO CRÍTICO: SUPPLY UNLOCK RISK
                        supply_safe = self.check_supply_unlock_risk(coin)
                        if not supply_safe:
                            print(f"� {coin['symbol']}: ALTO RISCO DE INFLAÇÃO - Supply unlock perigoso - dispensar")
                            continue
                        else:
                            print(f"✅ {coin['symbol']}: Supply seguro - sem risco de inflação excessiva")

                        # 🔥 FILTRO 2: RESILIÊNCIA DE PREÇO (pullback saudável refinado)
                        price_resilience = self.check_price_resilience(coin)
                        price_change_30d = coin.get('price_change_percentage_30d', 0)
                        price_change_7d = coin.get('price_change_percentage_7d', 0)

                        if price_resilience:
                            print(f"💪 {coin['symbol']}: PULLBACK FORTE - 30d: +{price_change_30d:.1f}% (>15%), 7d: {price_change_7d:.1f}% (saudável)!")
                        elif price_change_30d > 0 and price_change_7d < 0:
                            print(f"📊 {coin['symbol']}: Pullback fraco - 30d: +{price_change_30d:.1f}% (<15%), 7d: {price_change_7d:.1f}%")
                        else:
                            print(f"📈 {coin['symbol']}: Preço normal (sem pullback saudável)")

                        # 🚀 FILTRO DE INTERESSE REAL (MOMENTUM/ENGAGEMENT)
                        price_change_7d = coin.get('price_change_percentage_7d', 0)
                        if price_change_7d > 20:
                            coin['momentum'] = 'high'
                            print(f"🚀 {coin['symbol']}: MOMENTUM ALTO - +{price_change_7d:.1f}% em 7d - MERCADO ATENTO!")
                        elif price_change_7d > 10:
                            coin['momentum'] = 'medium'
                            print(f"📈 {coin['symbol']}: MOMENTUM MÉDIO - +{price_change_7d:.1f}% em 7d - atenção crescente")
                        else:
                            coin['momentum'] = 'low'
                            print(f"📊 {coin['symbol']}: MOMENTUM BAIXO - {price_change_7d:.1f}% em 7d - mercado quieto")

                        # 🎯 BÔNUS ESPECIAL: OURO PURO - Pullback + Volume Real
                        if price_resilience and volume_mc_ratio > 0.7:
                            print(f"👑 {coin['symbol']}: OURO PURO - Pullback saudável + Volume real ({volume_mc_ratio:.2f}x MC)!")
                            coin['is_gold'] = True
                        elif price_resilience:
                            print(f"💎 {coin['symbol']}: Pullback saudável mas volume baixo ({volume_mc_ratio:.2f}x MC) - potencial")
                            coin['is_gold'] = False
                        else:
                            coin['is_gold'] = False

                        # GEM ENCONTRADA!
                        gem_change_24h = coin.get('price_change_percentage_24h')
                        gem_change_7d = coin.get('price_change_percentage_7d')
                        btc_24h = btc_change_24h if isinstance(btc_change_24h, (int, float)) else None
                        btc_7d = btc_change_7d if isinstance(btc_change_7d, (int, float)) else None

                        rs_24h = (gem_change_24h - btc_24h) if isinstance(gem_change_24h, (int, float)) and isinstance(btc_24h, (int, float)) else None
                        rs_7d = (gem_change_7d - btc_7d) if isinstance(gem_change_7d, (int, float)) and isinstance(btc_7d, (int, float)) else None

                        coin['btc_change_24h'] = btc_24h
                        coin['btc_change_7d'] = btc_7d
                        coin['rs_24h'] = rs_24h
                        coin['rs_7d'] = rs_7d
                        coin['rs_available'] = (rs_24h is not None or rs_7d is not None)

                        coin['rs_strong_24h'] = (
                            isinstance(rs_24h, (int, float)) and isinstance(btc_24h, (int, float)) and
                            btc_24h < 0 and rs_24h >= 2.0
                        )
                        coin['rs_leader_24h'] = (
                            isinstance(gem_change_24h, (int, float)) and isinstance(btc_24h, (int, float)) and
                            btc_24h < 0 and gem_change_24h > 0
                        )

                        gems.append(coin)
                        page_gems_found += 1
                        print(f" {coin['symbol']}: MC=${market_cap:,}, Vol=${volume:,}")

                        # Atualizar menor MC encontrado
                        if market_cap < min_mc_found:
                            min_mc_found = market_cap
                            print(f" Novo menor MC: ${min_mc_found:,.0f}")

                            # Verificar se chegou perto do alvo (30M)
                            if min_mc_found <= target_mc + 5_000_000:  # 35M
                                print(f"🎯 Atingimos MCs próximos a ${target_mc:,}!")
                                reached_target = True
                                break

                        # NÃO parar com 10 gems - continuar buscando até 30M

                    # Sem parada antecipada - busca completa
                    if page_gems_found == 0:
                        print(f" Página {page}: continuando busca (sem gems na faixa)")
                    else:
                        print(f" Página {page}: {page_gems_found} gems encontradas")

                    page += 1
                    # Delay adaptativo: aumenta conforme avança nas páginas
                    base_delay = 1
                    adaptive_delay = base_delay + (page // 20)  # +1s a cada 20 páginas
                    time.sleep(adaptive_delay)

                elif r.status_code == 429:
                    # Rate limit inteligente com backoff exponencial
                    wait_time = min(30, 15 * (1 + (page // 10)))  # Aumenta progressivamente
                    print(f"⏳ Rate limit... esperando {wait_time}s (página {page})")
                    time.sleep(wait_time)

                else:
                    print(f"❌ HTTP {r.status_code}")
                    break

            except Exception as e:
                print(f"❌ Erro: {e}")
                break

        print(f"🎯 Total encontrado: {len(gems)} gems")
        print(f"📍 Menor MC encontrado: ${min_mc_found:,.0f}")
        print(f"🎯 Alvo atingido: {'SIM' if reached_target else 'NÃO (continuaria se mais páginas)'}")

        # Ordenar por prioridade: MAIOR ratio Volume/MC (ESSENCIAL), menor market cap depois
        if gems:
            def sort_key(x):
                volume = x.get('total_volume', 0) or 0
                mc = x.get('market_cap', 0)
                volume_mc_ratio = volume / mc if mc > 0 else 0
                return (-volume_mc_ratio, mc)  # Maior ratio primeiro, menor MC depois

            gems.sort(key=sort_key)
            print(f"📊 Ordenado por: MAIOR ratio Volume/MC (ESSENCIAL) + menor MC")

            # Mostrar ranking final
            for i, gem in enumerate(gems[:5], 1):
                mc = gem.get('market_cap', 0)
                vol = gem.get('total_volume', 0) or 0
                ratio = vol / mc if mc > 0 else 0
                print(f"  {i}. {gem['symbol']}: MC=${mc:,}, Vol=${vol:,}, Ratio={ratio:.2f}")

        # NÃO salvar cache aqui (será salvo no final após todas as faixas)

        return gems

    def save_daily_snapshot(self, gems: List[Dict[str, Any]]):
        """Salva snapshot diário consolidado para análise histórica"""
        today = datetime.now().strftime('%Y%m%d')
        snapshot_file = os.path.join(self.daily_snapshots_dir, f'daily_{today}.json')

        # Processar todas as gems com ratio
        processed_gems = []
        for gem in gems:
            symbol = gem.get('symbol')
            name = gem.get('name')
            if not symbol or not name:
                continue
            volume = gem.get('total_volume', 0) or 0
            mc = gem.get('market_cap', 0)
            ratio = volume / mc if mc > 0 else 0

            processed_gems.append({
                'symbol': symbol,
                'name': name,
                'market_cap': mc,
                'volume': volume,
                'ratio': ratio,
                'fdv': gem.get('fully_diluted_valuation'),
                'priority': 'max' if ratio >= 1.0 else 'normal',
                'zone': gem.get('zone', 'unknown'),
                'volume_recovery': gem.get('volume_recovery', False),
                'price_resilience': gem.get('price_resilience', False),
                'is_gold': gem.get('is_gold', False),
                'price_change_7d': gem.get('price_change_percentage_7d', 0),
                'price_change_30d': gem.get('price_change_percentage_30d', 0),
                'suspected_wash_trading': gem.get('suspected_wash_trading', False),
                'momentum': gem.get('momentum', 'low'),
                'timeframe_classification': gem.get('timeframe_classification', 'INSUFFICIENT_DATA')
            })

        # Ordenar por market cap crescente (menor para maior)
        processed_gems.sort(key=lambda x: x['market_cap'])

        snapshot_data = {
            'date': today,
            'timestamp': datetime.now().isoformat(),
            'total_gems': len(processed_gems),
            'gems': processed_gems
        }

        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Snapshot diário CONSOLIDADO salvo: daily_{today}.json ({len(processed_gems)} gems)")
        print(f"📊 Ordenado por: Market Cap crescente (menor → maior)")

    def load_yesterday_snapshot(self) -> Optional[Dict]:
        """Carrega snapshot de ontem para comparação"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        snapshot_file = os.path.join(self.daily_snapshots_dir, f'daily_{yesterday}.json')

        if os.path.exists(snapshot_file):
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def load_historical_snapshots(self, days: int = 5) -> Dict[str, Dict]:
        """Carrega snapshots históricos para análise de persistência"""
        historical_data = {}

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            snapshot_file = os.path.join(self.daily_snapshots_dir, f'daily_{date}.json')

            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    snapshot = json.load(f)
                    historical_data[date] = {gem['symbol']: gem for gem in snapshot['gems']}

        return historical_data

    def count_strong_days(self, symbol: str, historical_data: Dict[str, Dict], days: int = 14) -> int:
        """Conta dias consecutivos com ratio > 0.5 (até 14 dias)"""
        count = 0

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            if date in historical_data:
                day_data = historical_data[date]
                if symbol in day_data:
                    ratio = day_data[symbol]['ratio']
                    if ratio > 0.5:
                        count += 1

        return count

    def analyze_timeframe_classification(self, symbol: str, historical_data: Dict[str, Dict]) -> Dict[str, Any]:
        """Análise multi-timeframe: Curto, Médio e Longo prazo"""
        today = datetime.now().strftime('%Y%m%d')

        # 🟢 Curto Prazo (24h) - Detecção
        short_analysis = {
            'has_spike': False,
            'momentum_initial': 'low',
            'volume_mc_ratio': 0,
            'is_candidate': False
        }

        # 🟡 Médio Prazo (3-7 dias) - Validação
        medium_analysis = {
            'persistence_days': 0,
            'volume_recovery_consistent': False,
            'volatility_reducing': False,
            'is_emerging_leader': False
        }

        # 🔵 Longo Prazo (7-14 dias) - Confirmação
        long_analysis = {
            'trend_clear': False,
            'sustainable_growth': False,
            'consistency_score': 0,
            'is_confirmed_leader': False
        }

        if today in historical_data and symbol in historical_data[today]:
            today_data = historical_data[today][symbol]

            # 🟢 Análise Curto Prazo
            short_analysis['volume_mc_ratio'] = today_data.get('ratio', 0)
            short_analysis['momentum_initial'] = today_data.get('momentum', 'low')

            # Volume spike > 1.0 = candidato
            if short_analysis['volume_mc_ratio'] > 1.0:
                short_analysis['has_spike'] = True
                short_analysis['is_candidate'] = True
            elif short_analysis['volume_mc_ratio'] > 0.7:
                short_analysis['is_candidate'] = True  # Volume forte

            # 🟡 Análise Médio Prazo (3-7 dias)
            strong_days_3 = self.count_strong_days(symbol, historical_data, days=3)
            strong_days_7 = self.count_strong_days(symbol, historical_data, days=7)

            medium_analysis['persistence_days'] = strong_days_7

            # Volume recovery consistente (últimos 3 dias)
            if strong_days_3 >= 2:  # 2/3 dias fortes
                medium_analysis['volume_recovery_consistent'] = True

            # Candidato forte: 3+ dias persistentes
            if strong_days_3 >= 3:
                medium_analysis['is_emerging_leader'] = True

            # 🔵 Análise Longo Prazo (7-14 dias)
            strong_days_14 = self.count_strong_days(symbol, historical_data, days=14)

            # Tendência clara: 7+ dias fortes em 14
            if strong_days_14 >= 7:
                long_analysis['trend_clear'] = True
                long_analysis['sustainable_growth'] = True

            # Score de consistência (0-100)
            if strong_days_14 > 0:
                long_analysis['consistency_score'] = (strong_days_14 / 14) * 100

            # Líder emergente: 5-7 dias persistentes
            if 5 <= strong_days_7 <= 7:
                medium_analysis['is_emerging_leader'] = True

            # Líder confirmado: 7+ dias persistentes
            if strong_days_7 >= 7:
                long_analysis['is_confirmed_leader'] = True

        return {
            'short_term': short_analysis,
            'medium_term': medium_analysis,
            'long_term': long_analysis,
            'classification': self.get_timeframe_classification(short_analysis, medium_analysis, long_analysis)
        }

    def get_timeframe_classification(self, short: Dict, medium: Dict, long: Dict) -> str:
        """Classificação final baseada nas três camadas de tempo"""
        if long['is_confirmed_leader']:
            return 'LEADER_CONFIRMED'
        elif medium['is_emerging_leader'] and medium['persistence_days'] >= 5:
            return 'LEADER_EMERGING'
        elif medium['is_emerging_leader']:
            return 'CANDIDATE_STRONG'
        elif short['is_candidate']:
            return 'CANDIDATE_INITIAL'
        else:
            return 'MONITORING'

    def analyze_flow_acceleration(self, symbol: str, historical_data: Dict[str, Dict]) -> Dict[str, Any]:
        """Analisa aceleração do fluxo (hoje vs ontem vs anteontem)"""
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        day_before = (datetime.now() - timedelta(days=2)).strftime('%Y%m%d')

        acceleration_data = {
            'has_acceleration': False,
            'acceleration_strength': 0,
            'trend': 'stable',
            'ratios': {}
        }

        # Pegar ratios dos 3 dias
        if today in historical_data and yesterday in historical_data and day_before in historical_data:
            today_data = historical_data[today]
            yesterday_data = historical_data[yesterday]
            day_before_data = historical_data[day_before]

            if (symbol in today_data and symbol in yesterday_data and symbol in day_before_data):
                ratio_today = today_data[symbol]['ratio']
                ratio_yesterday = yesterday_data[symbol]['ratio']
                ratio_day_before = day_before_data[symbol]['ratio']

                acceleration_data['ratios'] = {
                    'today': ratio_today,
                    'yesterday': ratio_yesterday,
                    'day_before': ratio_day_before
                }

                # Calcular crescimentos
                growth_24h = ratio_today / ratio_yesterday if ratio_yesterday > 0 else 0
                growth_48h = ratio_yesterday / ratio_day_before if ratio_day_before > 0 else 0

                # 🚀 DETECTAR ACELERAÇÃO
                if growth_24h > growth_48h * 1.1:  # Crescimento acelerando >10%
                    acceleration_data['has_acceleration'] = True
                    acceleration_data['acceleration_strength'] = growth_24h / growth_48h if growth_48h > 0 else 2
                    acceleration_data['trend'] = 'accelerating'
                elif growth_24h < growth_48h * 0.9:  # Crescimento desacelerando >10%
                    acceleration_data['trend'] = 'decelerating'
                else:
                    acceleration_data['trend'] = 'stable'

        return acceleration_data

    def check_volume_persistence(self, symbol: str, historical_data: Dict[str, Dict]) -> bool:
        """Verifica se o volume não caiu mais de 30% de ontem para hoje"""
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        if today in historical_data and yesterday in historical_data:
            today_data = historical_data[today]
            yesterday_data = historical_data[yesterday]

            if symbol in today_data and symbol in yesterday_data:
                ratio_now = today_data[symbol]['ratio']
                ratio_24h = yesterday_data[symbol]['ratio']

                # Se volume caiu mais de 30%, não é persistente
                if ratio_now < ratio_24h * 0.7:
                    return False

        return True

    def check_volume_recovery(self, symbol: str, historical_data: Dict[str, Dict]) -> bool:
        """🔥 FILTRO DE 'RECUPERAÇÃO DE VOLUME' - Detecta capital entrando de verdade"""
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        if today in historical_data and yesterday in historical_data:
            today_data = historical_data[today]
            yesterday_data = historical_data[yesterday]

            if symbol in today_data and symbol in yesterday_data:
                vol_today = today_data[symbol].get('total_volume', 0)
                vol_yesterday = yesterday_data[symbol].get('total_volume', 0)

                # 🧠 Dinheiro entrando: volume hoje > 30% acima de ontem
                return vol_today > vol_yesterday * 1.3

        return False

    def check_price_resilience(self, coin: Dict[str, Any]) -> bool:
        """Verifica se a moeda está em pullback saudável (30d > 15%, 7d entre -15% e 0%)"""
        price_change_30d = coin.get('price_change_percentage_30d', 0)
        price_change_7d = coin.get('price_change_percentage_7d', 0)

        # 🎯 Lógica refinada: Qualidade sobre quantidade
        # 30d > 15% = tendência real e forte
        # -15% < 7d < 0 = pullback saudável (sem dump)
        if price_change_30d > 15 and -15 < price_change_7d < 0:
            return True
        return False

    def check_supply_unlock_risk(self, coin: Dict[str, Any]) -> bool:
        """🛡️ FILTRO CRÍTICO - Supply Unlock Risk (inflação futura)"""
        circulating = coin.get('circulating_supply', 0)
        total = coin.get('total_supply', 0)

        if total and circulating:
            circulating_ratio = circulating / total

            # 🚨 Muita inflação futura: menos de 30% em circulação
            if circulating_ratio < 0.3:
                return False  # Risco alto

        return True  # Seguro

    def analyze_growth(self, current_gems: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Analisa crescimento com aceleração do fluxo e qualidade de volume (LÍDERES DE ALTSEASON)"""
        # Carregar dados históricos para análise de persistência
        historical_data = self.load_historical_snapshots(days=5)

        if len(historical_data) < 3:
            print("⚠️ Sem dados históricos suficientes (precisa 3+ dias) - primeira execução")
            return [], []

        # Pegar dados de ontem para comparação direta
        yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        if yesterday_date not in historical_data:
            print("⚠️ Sem dados de ontem - primeira execução")
            return [], []

        yesterday_gems = historical_data[yesterday_date]
        confirmed_gems = []
        new_strong_candidates = []

        print(f"🔍 Analisando PERSISTÊNCIA + ACELERAÇÃO vs histórico ({len(historical_data)} dias, {len(yesterday_gems)} gems ontem)")

        for current_gem in current_gems:
            symbol = current_gem['symbol']
            ratio_now = current_gem['ratio']

            if symbol in yesterday_gems:
                yesterday_gem = yesterday_gems[symbol]
                ratio_24h_ago = yesterday_gem['ratio']

                # ✅ CORREÇÃO: Growth percentual (normalizado)
                growth_percent = ratio_now / ratio_24h_ago if ratio_24h_ago > 0 else 0

                # 🧠 PERSISTÊNCIA: Contar dias fortes consecutivos
                strong_days = self.count_strong_days(symbol, historical_data, days=3)

                # 🛡️ VOLUME PERSISTENTE: Verificar se não está perdendo força
                volume_persistent = self.check_volume_persistence(symbol, historical_data)

                # 🚀 ACELERAÇÃO DO FLUXO: Analise de 3 dias
                acceleration = self.analyze_flow_acceleration(symbol, historical_data)

                # 🔥 CRITÉRIOS FINAIS DE LÍDER DE ALTSEASON (COM ACELERAÇÃO)
                if (ratio_now > 0.5 and
                    ratio_24h_ago > 0.5 and
                    growth_percent > 1.2 and  # 20% crescimento
                    strong_days >= 2 and      # Mínimo 2 dias fortes
                    volume_persistent and       # Volume não caindo >30%
                    acceleration['has_acceleration']):  # 🚀 FLUXO ACELERANDO

                    # 🚀 PRIORIDADES EXTREMAS (COM ACELERAÇÃO)
                    if ratio_now >= 1.5:
                        priority = 'extrema'  # Fluxo absurdo + aceleração
                    elif ratio_now >= 1.0:
                        priority = 'maxima'   # Muito forte + aceleração
                    else:
                        priority = 'alta'     # Forte + aceleração

                    confirmed_gem = {
                        'symbol': symbol,
                        'name': current_gem['name'],
                        'confirmed_at': datetime.now().isoformat(),
                        'ratio_now': ratio_now,
                        'ratio_24h_ago': ratio_24h_ago,
                        'growth_percent': (growth_percent - 1) * 100,
                        'strong_days': strong_days,
                        'acceleration_strength': acceleration['acceleration_strength'],
                        'trend': acceleration['trend'],
                        'market_cap': current_gem['market_cap'],
                        'volume': current_gem.get('total_volume', 0),
                        'priority': priority,
                        'status': 'confirmed',
                        'type': 'lider_altseason',  # 🎯 Identificador de líder
                        'quality_score': self.calculate_quality_score(ratio_now, strong_days, acceleration['acceleration_strength'])
                    }
                    confirmed_gems.append(confirmed_gem)
                    print(f"🚀 LÍDER ACELERADO: {symbol} - {priority.upper()} - {confirmed_gem['growth_percent']:.1f}% crescimento ({strong_days} dias) - ACELERAÇÃO {acceleration['trend']}")

            else:
                # ✅ FALLBACK: Nova entrada forte com aceleração
                if ratio_now > 0.8:  # Nova gem muito forte
                    priority = 'extrema' if ratio_now >= 1.5 else 'maxima' if ratio_now >= 1.0 else 'alta'

                    new_candidate = {
                        'symbol': symbol,
                        'name': current_gem['name'],
                        'detected_at': datetime.now().isoformat(),
                        'ratio_now': ratio_now,
                        'market_cap': current_gem['market_cap'],
                        'volume': current_gem.get('total_volume', 0),
                        'priority': priority,
                        'status': 'new_strong_candidate',
                        'reason': 'Nova entrada forte (> 0.8)',
                        'type': 'potencial_lider',  # 🚀 Futura líder
                        'quality_score': self.calculate_quality_score(ratio_now, 1, 1.0)  # Nova entrada = baseline
                    }
                    new_strong_candidates.append(new_candidate)
                    print(f"🚀 POTENCIAL LÍDER: {symbol} - {priority.upper()} - ratio {ratio_now:.2f} (nova entrada)")

        return confirmed_gems, new_strong_candidates

    def calculate_quality_score(self, ratio: float, strong_days: int, acceleration_strength: float) -> float:
        """Calcula score de qualidade combinando múltiplos fatores"""
        # Fatores ponderados
        ratio_score = min(ratio / 2.0, 1.0) * 40  # Ratio até 2.0 = 40%
        persistence_score = min(strong_days / 3.0, 1.0) * 35  # 3 dias fortes = 35%
        acceleration_score = min(acceleration_strength / 2.0, 1.0) * 25  # 2x aceleração = 25%

        return ratio_score + persistence_score + acceleration_score

    def update_new_candidates(self, new_candidates: List[Dict[str, Any]]):
        """Salva novas candidatas fortes"""
        if not new_candidates:
            return

        existing_candidates = []

        # Carregar candidatas existentes
        if os.path.exists(self.new_candidates_file):
            with open(self.new_candidates_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_candidates = existing_data.get('new_candidates', [])

        # Adicionar novas candidatas (sem duplicar)
        existing_symbols = {c['symbol'] for c in existing_candidates}
        for candidate in new_candidates:
            if candidate['symbol'] not in existing_symbols:
                existing_candidates.append(candidate)

        # Salvar arquivo atualizado
        final_data = {
            'last_updated': datetime.now().isoformat(),
            'total_candidates': len(existing_candidates),
            'new_candidates': existing_candidates
        }

        with open(self.new_candidates_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)

        print(f"🚀 Novas candidatas fortes: {len(new_candidates)} (total: {len(existing_candidates)})")

    def update_confirmed_gems(self, confirmed_gems: List[Dict[str, Any]]):
        """Atualiza arquivo de gems confirmadas (não duplica) - ORDENADO POR MC"""
        existing_confirmed = {}

        # Carregar gems confirmadas existentes
        if os.path.exists(self.confirmed_gems_file):
            with open(self.confirmed_gems_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_confirmed = {gem['symbol']: gem for gem in existing_data.get('confirmed_gems', [])}

        # Atualizar ou adicionar novas confirmações
        for new_gem in confirmed_gems:
            symbol = new_gem['symbol']
            existing_confirmed[symbol] = new_gem  # Substitui com dados mais recentes

        # Ordenar por market cap crescente
        confirmed_list = sorted(existing_confirmed.values(), key=lambda x: x['market_cap'])

        # Salvar arquivo atualizado
        final_data = {
            'last_updated': datetime.now().isoformat(),
            'total_confirmed': len(existing_confirmed),
            'confirmed_gems': confirmed_list
        }

        with open(self.confirmed_gems_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)

        print(f"💎 Gems confirmadas atualizadas: {len(existing_confirmed)} totais (ordenadas por MC crescente)")

    def find_gems_by_ranges(self) -> tuple[Dict[str, List[Dict[str, Any]]], bool]:
        """
        Busca gems em faixas específicas: 50M e 10M
        Retorna: (gems_data, is_new_data)
        """
        print("🚀 GEMS FINDER - Busca por Faixas Específicas")
        print("=" * 50)
        print(f"⏱️ Cache válido por: {self.CACHE_DURATION}")

        # Verificar se cache expirou
        cache_expired = False
        try:
            if not os.path.exists(self.cache_path):
                cache_expired = True
            else:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                expires_at = datetime.fromisoformat(cache_data.get('expires_at', ''))
                if datetime.now() >= expires_at:
                    cache_expired = True
        except:
            cache_expired = True

        # Faixas solicitadas
        ranges = [
            {"name": "50m_range", "min_mc": 30_000_000, "max_mc": 50_000_000, "min_volume": 1_000_000, "max_results": 10},
            {"name": "10m_range", "min_mc": 10_000_000, "max_mc": 20_000_000, "min_volume": 500_000, "max_results": 10},
        ]

        all_gems = {}
        new_data_found = False

        # Verificar se temos cache válido para usar
        cached = self.load_cache()

        # ✅ CORREÇÃO: Extrair dados do cache corretamente
        if cached and isinstance(cached, dict):
            cached_gems = cached.get('data', [])
            cache_valid = isinstance(cached_gems, list)
        else:
            cached_gems = []
            cache_valid = False

        if cache_valid:
            print(f"✅ Usando cache existente: {len(cached_gems)} gems")
            new_data_found = False
        else:
            print("🔄 Cache expirado ou inexistente - Buscando dados novos...")
            new_data_found = True

        for range_config in ranges:
            print(f"\n🔍 Processando faixa {range_config['name']}: MC ${range_config['min_mc']:,}-${range_config['max_mc']:,}")

            if cache_valid and cached_gems:
                # Filtrar gems do cache para esta faixa
                filtered_gems = self._filter_gems_by_range(cached_gems, range_config)
                print(f"📋 Cache: {len(filtered_gems)} gems encontradas")
            else:
                # Buscar dados novos da API
                gems = self.find_gems_smart(
                    min_market_cap=range_config["min_mc"],
                    max_market_cap=range_config["max_mc"],
                    min_volume=range_config["min_volume"],
                    max_results=range_config["max_results"]
                )
                filtered_gems = gems
                print(f"🔄 API: {len(filtered_gems)} gems encontradas")

            all_gems[range_config["name"]] = filtered_gems
            print(f"✅ {range_config['name']}: {len(filtered_gems)} gems")

            # Pausa entre faixas (só se buscou da API)
            if not cache_valid:
                time.sleep(2)

        # 💾 Salvar cache compartilhado apenas se buscou dados novos
        if not cache_valid and new_data_found:
            # Consolidar todas as gems para o cache compartilhado
            all_gems_for_cache = []
            for range_name, gems in all_gems.items():
                all_gems_for_cache.extend(gems)

            # 🔥 REMOVER DUPLICADOS por símbolo antes de salvar
            unique_gems = {}
            for gem in all_gems_for_cache:
                symbol = gem.get('symbol', '')
                if symbol and symbol not in unique_gems:
                    unique_gems[symbol] = gem

            # Converter de volta para lista
            deduplicated_gems = list(unique_gems.values())

            print(f"🔄 Cache original: {len(all_gems_for_cache)} gems")
            print(f"✅ Cache deduplicado: {len(deduplicated_gems)} gems únicas")

            # Salvar cache compartilhado com 12h de validade
            self.save_cache(deduplicated_gems)
            print(f"💾 Cache compartilhado salvo: {len(deduplicated_gems)} gems totais")
        elif cache_valid:
            print("📋 Cache válido - Nenhum cache atualizado")

        # 🧠 SISTEMA DE LÍDERES DE ALTSEASON - CONSOLIDADO
        if new_data_found:
            print("\n🧠 SISTEMA DE LÍDERES DE ALTSEASON - CONSOLIDADO")
            print("=" * 50)
            print("🎯 OBJETIVO: Identificar protagonistas da bullrun (não fundo)")

            # 🚀 Otimização: Carregar histórico para análise multi-timeframe
            historical_data = self.load_historical_snapshots(days=14)  # Para análise completa
            has_historical_data = len(historical_data) >= 1

            # Consolidar todas as gems das duas faixas em uma lista única
            all_gems_list = []
            for range_name, gems in all_gems.items():
                print(f"📊 {range_name}: {len(gems)} gems")
                # Adicionar ratio e novos filtros às gems
                for gem in gems:
                    volume = gem.get('total_volume', 0) or 0
                    mc = gem.get('market_cap', 0)
                    gem['ratio'] = volume / mc if mc > 0 else 0
                    gem['range'] = range_name  # Marcar a faixa de origem

                    # 🔥 Aplicar novos filtros (histórico já carregado)
                    gem['volume_recovery'] = self.check_volume_recovery(gem['symbol'], historical_data) if has_historical_data else False
                    gem['price_resilience'] = self.check_price_resilience(gem)

                    # Verificar se é OURO PURO (Pullback + Volume Real)
                    gem['is_gold'] = gem['price_resilience'] and gem['ratio'] > 0.7  # Pullback + Volume real

                    # Análise Multi-Timeframe (sistema robusto)
                    if has_historical_data:
                        timeframe_analysis = self.analyze_timeframe_classification(gem['symbol'], historical_data)
                        gem['timeframe_analysis'] = timeframe_analysis
                        gem['timeframe_classification'] = timeframe_analysis['classification']

                        # Logs detalhados da classificação
                        classification = timeframe_analysis.get('classification', 'INSUFFICIENT_DATA')
                        persistence_days = timeframe_analysis.get('medium_term', {}).get('persistence_days', 0)

                        if classification == 'LEADER_CONFIRMED':
                            print(f" {gem['symbol']}: LÍDER CONFIRMADO - {persistence_days} dias persistentes!")
                        elif classification == 'LEADER_EMERGING':
                            print(f"🌟 {gem['symbol']}: LÍDER EMERGENTE - {persistence_days} dias de força!")
                        elif classification == 'CANDIDATE_STRONG':
                            print(f"💪 {gem['symbol']}: CANDIDATO FORTE - potencial de liderança!")
                        elif classification == 'CANDIDATE_INITIAL':
                            print(f"🔍 {gem['symbol']}: CANDIDATO INICIAL - monitorar!")
                        else:
                            print(f"📊 {gem['symbol']}: EM MONITORAMENTO - aguardar sinais!")

                        # 🧠 CAMADA 4: VALIDAÇÃO SOCIAL (critério ajustado)
                        gem_ratio = gem.get('ratio', 0)
                        if self.social_analyzer and gem_ratio > 0.5 and persistence_days >= 1:
                            social_result = self.social_analyzer.check_social_validation(gem['symbol'], gem_ratio, persistence_days, gem.get('name', gem['symbol']))
                            # ✅ Converter dict para JSON string para evitar parse errors
                            import json
                            gem['social_analysis'] = json.dumps(social_result)
                            self.social_analyzer.print_social_analysis(gem['symbol'], social_result)
                        else:
                            # ✅ Converter dict para JSON string para evitar parse errors
                            import json
                            gem['social_analysis'] = json.dumps({'should_analyze': False, 'combined_validation': 'NOT_APPLICABLE'})

                    else:
                        gem['timeframe_classification'] = 'INSUFFICIENT_DATA'
                        # ✅ Converter dict para JSON string para evitar parse errors
                        import json
                        gem['social_analysis'] = json.dumps({'should_analyze': False, 'combined_validation': 'INSUFFICIENT_DATA'})
                        print(f"📊 {gem['symbol']}: Dados insuficientes - primeira execução")

                all_gems_list.extend(gems)

            # 🔄 Análise Multi-Timeframe consolidada
            timeframe_counts = {
                'LEADER_CONFIRMED': 0,
                'LEADER_EMERGING': 0,
                'CANDIDATE_STRONG': 0,
                'CANDIDATE_INITIAL': 0,
                'MONITORING': 0,
                'INSUFFICIENT_DATA': 0
            }
            social_counts = {
                'SOCIAL_EXPLOSION': 0,
                'SOCIAL_STRONG': 0,
                'SOCIAL_MODERATE': 0,
                'SOCIAL_LOW': 0,
                'SOCIAL_WEAK': 0,
                'NO_DATA': 0,
                'NOT_APPLICABLE': 0
            }

            for gem in all_gems_list:
                classification = gem.get('timeframe_classification', 'INSUFFICIENT_DATA')
                timeframe_counts[classification] = timeframe_counts.get(classification, 0) + 1
                # ✅ Parse social_analysis se for string
                social_analysis = gem.get('social_analysis', '{}')
                if isinstance(social_analysis, str):
                    import json
                    try:
                        social_analysis = json.loads(social_analysis)
                    except:
                        social_analysis = {}
                social_val = social_analysis.get('combined_validation', 'NO_DATA')
                social_counts[social_val] = social_counts.get(social_val, 0) + 1

            print(f"\n🔄 ANÁLISE MULTI-TIMEFRAME:")
            print(f"  🏆 LÍDERES CONFIRMADOS: {timeframe_counts['LEADER_CONFIRMED']} gems")
            print(f"  🌟 LÍDERES EMERGENTES: {timeframe_counts['LEADER_EMERGING']} gems")
            print(f"  💪 CANDIDATOS FORTES: {timeframe_counts['CANDIDATE_STRONG']} gems")
            print(f"  🔍 CANDIDATOS INICIAIS: {timeframe_counts['CANDIDATE_INITIAL']} gems")
            print(f"  📊 EM MONITORAMENTO: {timeframe_counts['MONITORING']} gems")
            print(f"  ⚠️ DADOS INSUFICIENTES: {timeframe_counts['INSUFFICIENT_DATA']} gems")

            print(f"\n🧠 ANÁLISE SOCIAL (YouTube + Telegram):")
            print(f"  🔥 EXPLOSÃO SOCIAL: {social_counts['SOCIAL_EXPLOSION']} gems")
            print(f"  💪 ATENÇÃO FORTE: {social_counts['SOCIAL_STRONG']} gems")
            print(f"  📊 ATENÇÃO MODERADA: {social_counts['SOCIAL_MODERATE']} gems")
            print(f"  📈 ATENÇÃO BAIXA: {social_counts['SOCIAL_LOW']} gems")
            print(f"  ❌ ATENÇÃO FRACA: {social_counts['SOCIAL_WEAK']} gems")
            print(f"  ⚠️ SEM DADOS: {social_counts['NO_DATA']} gems")
            print(f"  📊 NÃO APLICÁVEL: {social_counts['NOT_APPLICABLE']} gems")

            # Mostrar líderes confirmados e emergentes
            confirmed_leaders = [g for g in all_gems_list if g.get('timeframe_classification') == 'LEADER_CONFIRMED']
            emerging_leaders = [g for g in all_gems_list if g.get('timeframe_classification') == 'LEADER_EMERGING']

            if confirmed_leaders:
                print(f"\n🏆 LÍDERES CONFIRMADOS (7+ dias persistentes):")
                for leader in confirmed_leaders[:3]:
                    # ✅ Parse timeframe_analysis se for string
                    timeframe_analysis = leader.get('timeframe_analysis', '{}')
                    if isinstance(timeframe_analysis, str):
                        import json
                        try:
                            timeframe_analysis = json.loads(timeframe_analysis)
                        except:
                            timeframe_analysis = {}
                    persistence = timeframe_analysis.get('medium_term', {}).get('persistence_days', 0)
                    print(f"  🥇 {leader['symbol']}: {persistence} dias, MC=${leader['market_cap']:,}")

            if emerging_leaders:
                print(f"\n🌟 LÍDERES EMERGENTES (5-7 dias persistentes):")
                for leader in emerging_leaders[:3]:
                    # ✅ Parse timeframe_analysis se for string
                    timeframe_analysis = leader.get('timeframe_analysis', '{}')
                    if isinstance(timeframe_analysis, str):
                        import json
                        try:
                            timeframe_analysis = json.loads(timeframe_analysis)
                        except:
                            timeframe_analysis = {}
                    persistence = timeframe_analysis.get('medium_term', {}).get('persistence_days', 0)
                    print(f"  🌟 {leader['symbol']}: {persistence} dias, MC=${leader['market_cap']:,}")

            # ── Enriquecer com setor ──────────────────────────────────────────
            for gem in all_gems_list:
                gem['sector'] = get_sector(
                    gem.get('symbol', '').lower(),
                    gem.get('categories', [])
                )

            # ── 1. ACUMULAÇÃO SILENCIOSA ──────────────────────────────────────
            historical_data_full = self.load_historical_snapshots(days=30)
            if historical_data_full:
                all_gems_list = enrich_gems_with_accumulation(
                    all_gems_list,
                    historical_data_full,
                    self.accumulation_detector
                )
                print_accumulation_report(all_gems_list)
            else:
                for gem in all_gems_list:
                    gem['accumulation_score']     = 0.0
                    gem['accumulation_signal']    = 'none'
                    gem['accumulation_slope']     = 0.0
                    gem['is_silent_accumulation'] = False
                    gem['accumulation_reason']    = 'Histórico insuficiente'

            # ── 2. CORRELAÇÃO SETORIAL ───────────────────────────────────────
            sector_snapshots = load_sector_historical(
                self.snapshots_dir, days=14
            )
            # Adicionar snapshot atual ao histórico setorial
            sector_snapshots.append(build_sector_snapshot(all_gems_list))

            sector_result = self.sector_analyzer.analyze_historical(sector_snapshots)
            print_sector_report(sector_result)

            # Guardar resultado para salvar no enhanced snapshot
            self._last_sector_result = sector_result

            # ── Salvar snapshot único consolidado ─────────────────────────────
            self.save_daily_snapshot(all_gems_list)

            # ── Análise de crescimento e líderes (lógica original) ────────────
            confirmed_leaders, new_potentials = self.analyze_growth(all_gems_list)

            if confirmed_leaders:
                self.update_confirmed_gems(confirmed_leaders)
                print(f"\n🔥 {len(confirmed_leaders)} LÍDERES DE ALTSEASON confirmados!")
                for leader in confirmed_leaders:
                    print(f"  🚀 {leader['symbol']}: {leader['priority'].upper()} - "
                          f"{leader['growth_percent']:.1f}% crescimento ({leader['strong_days']} dias fortes)")
            else:
                print("\n⏳ Nenhum líder confirmado hoje (sem persistência suficiente)")

            if new_potentials:
                self.update_new_candidates(new_potentials)
                print(f"\n🚀 {len(new_potentials)} POTENCIAIS LÍDERES detectados!")
                for potential in new_potentials:
                    print(f"  ⭐ {potential['symbol']}: {potential['priority'].upper()} - "
                          f"ratio {potential['ratio_now']:.2f} (nova entrada)")
            else:
                print("\n📊 Nenhum potencial líder detectado hoje")

        return all_gems, new_data_found

    def _filter_gems_by_range(self, gems: List[Dict[str, Any]], range_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filtra gems do cache pela faixa específica"""
        filtered = []
        for gem in gems:
            mc = gem.get('market_cap', 0)
            vol = gem.get('total_volume', 0) or 0

            if (range_config['min_mc'] <= mc <= range_config['max_mc'] and
                vol >= range_config['min_volume']):
                filtered.append(gem)

        return filtered[:range_config['max_results']]

    def save_snapshots(self, gems_data: Dict[str, List[Dict[str, Any]]]):
        """
        Salva snapshots para análise histórica
        Otimizado: arquivo único consolidado com nome baseado no range completo
        """
        import pandas as pd

        # ✅ CORREÇÃO: Usar data do cache se disponível para manter consistência
        cached = self.load_cache()
        if cached and cached.get('cached_time'):
            # Usar timestamp do cache para manter consistência
            cached_time = cached['cached_time']
            # ✅ CORREÇÃO: Converter string para datetime se necessário
            if isinstance(cached_time, str):
                cache_time = datetime.fromisoformat(cached_time)
            else:
                cache_time = cached_time
            date_str = cache_time.strftime("%Y%m%d_%H%M%S")
            print(f"\n💾 Salvando snapshots (usando data do cache): {date_str}")
        else:
            # Fallback para timestamp atual (só se não tiver cache)
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"\n💾 Salvando snapshots (dados novos): {date_str}")

        # Criar diretório de snapshots
        snapshots_dir = os.path.join(os.path.dirname(__file__), 'data', 'snapshots')
        os.makedirs(snapshots_dir, exist_ok=True)

        # 🚀 Otimização: Consolidar todas as gems em um único arquivo
        all_gems = []
        range_limits = []

        for range_name, gems in gems_data.items():
            if gems:
                # Adicionar info da faixa em cada gem
                for gem in gems:
                    gem['source_range'] = range_name
                all_gems.extend(gems)

                # Extrair limites do range para o nome do arquivo
                if '10m' in range_name:
                    range_limits.append('10M')
                elif '50m' in range_name:
                    range_limits.append('50M')
                elif 'test' in range_name:
                    range_limits.append('TEST')

        # Remover duplicatas por símbolo (manter a primeira ocorrência)
        unique_gems = {}
        for gem in all_gems:
            symbol = gem.get('symbol', '')
            if symbol and symbol not in unique_gems:
                unique_gems[symbol] = gem

        final_gems = list(unique_gems.values())

        if final_gems:
            df_all = pd.DataFrame(final_gems)

            # 🎯 Nome inteligente baseado nos ranges presentes
            if len(range_limits) >= 2:
                range_name = f"{min(range_limits)}_to_{max(range_limits)}"
            else:
                range_name = range_limits[0] if range_limits else 'consolidated'

            # Snapshot único consolidado
            consolidated_file = os.path.join(snapshots_dir, f"gems_{range_name}_{date_str}.csv")
            df_all.to_csv(consolidated_file, index=False)

            print(f"  ✅ {range_name}: {len(final_gems)} gems únicas")
            print(f"  📁 Arquivo: {consolidated_file}")
            print(f"  💾 Ranges presentes: {', '.join(range_limits)}")

        return date_str

    def calculate_final_scores(self, gems_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        🚀 Calcula scores finais e enriquece dados com ranking
        Não altera lógica principal, apenas adiciona colunas
        """
        enriched_data = {}

        for range_name, gems in gems_data.items():
            enriched_gems = []

            for gem in gems:
                # 🔢 Score Quantitativo (baseado em ratio e indicadores)
                quant_score = self._calculate_quant_score(gem)

                # 🧠 Score Social (se existir análise social)
                social_analysis = gem.get('social_analysis', '{}')
                if isinstance(social_analysis, str):
                    # ✅ Parse JSON string para dict
                    import json
                    try:
                        social_analysis = json.loads(social_analysis)
                    except:
                        social_analysis = {}

                social_validation = social_analysis.get('combined_validation', 'NOT_APPLICABLE')
                social_score = self.social_analyzer.social_score(social_validation) if self.social_analyzer else 0

                # 🏆 Score Final (ponderado)
                final_score = (quant_score * 0.6) + (social_score * 0.4)

                # Enriquecer gem com scores
                enriched_gem = gem.copy()
                enriched_gem.update({
                    'quant_score': round(quant_score, 2),
                    'social_score': social_score,
                    'final_score': round(final_score, 2)
                })

                enriched_gems.append(enriched_gem)

            # 🏆 Ordenar por Leader confirmado primeiro, depois por final_score (maior primeiro)
            enriched_gems.sort(key=lambda x: (
                x.get('is_confirmed_leader', False),  # Líderes primeiro
                x.get('persistence_days', 0),          # Mais persistência depois
                x['final_score']                        # Score por último
            ), reverse=True)

            # Adicionar ranking
            for i, gem in enumerate(enriched_gems, 1):
                gem['ranking'] = i

            enriched_data[range_name] = enriched_gems

        return enriched_data

    def _calculate_quant_score(self, gem: Dict[str, Any]) -> float:
        """
        🔢 Score quantitativo baseado em indicadores técnicos
        Escala: -1 a 3 (similar ao social_score)
        """
        score = 0.0

        # 📊 Ratio Volume/MC (fator principal)
        ratio = gem.get('ratio', 0)
        if ratio >= 1.0:
            score += 1.5  # Breakout
        elif ratio >= 0.7:
            score += 1.0  # Strong
        elif ratio >= 0.5:
            score += 0.5  # Moderate
        elif ratio >= 0.2:
            score += 0.0  # Low (neutro)
        else:
            score -= 0.5  # Muito baixo

        # 💪 Resiliência de Preço (pullback saudável)
        if gem.get('price_resilience', False):
            score += 0.5

        # 👑 Potencial Ouro (pullback + volume real)
        if gem.get('is_gold', False):
            score += 0.5

        # 🚀 Momentum (interesse real)
        momentum = gem.get('momentum', 'low')
        if momentum == 'high':
            score += 0.3
        elif momentum == 'medium':
            score += 0.1

        # 🚨 Penalidade por Wash Trading
        if gem.get('suspected_wash_trading', False):
            score -= 0.3

        # 🔥 Recuperação de Volume
        if gem.get('volume_recovery', False):
            score += 0.2

        rs_24h = gem.get('rs_24h')
        rs_7d = gem.get('rs_7d')
        btc_24h = gem.get('btc_change_24h')
        btc_7d = gem.get('btc_change_7d')

        if isinstance(rs_24h, (int, float)) and isinstance(btc_24h, (int, float)):
            if btc_24h < 0 and rs_24h >= 4.0:
                score += 0.4
            elif btc_24h < 0 and rs_24h >= 2.0:
                score += 0.2
            elif rs_24h >= 2.0:
                score += 0.1

        if isinstance(rs_7d, (int, float)) and isinstance(btc_7d, (int, float)):
            if btc_7d < 0 and rs_7d >= 6.0:
                score += 0.2
            elif btc_7d < 0 and rs_7d >= 3.0:
                score += 0.1

        # Normalizar para escala -1 a 3
        score = max(-1.0, min(3.0, score))

        return score

    def save_enhanced_snapshots(self, gems_data: Dict[str, List[Dict[str, Any]]], date_str: str):
        """
        💾 Salva snapshots enriquecidos com scores e ranking
        Otimizado: arquivo único consolidado com colunas de eventos especiais
        """
        import pandas as pd

        # ✅ CORREÇÃO: Usar date_str passado como parâmetro (consistente com cache)
        if not date_str:
            # Fallback: usar data do cache se disponível
            cached = self.load_cache()
            if cached and cached.get('cached_time'):
                cached_time = cached['cached_time']
                # ✅ CORREÇÃO: Converter string para datetime se necessário
                if isinstance(cached_time, str):
                    cache_time = datetime.fromisoformat(cached_time)
                else:
                    cache_time = cached_time
                date_str = cache_time.strftime("%Y%m%d_%H%M%S")
            else:
                date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        snapshots_dir = os.path.join(os.path.dirname(__file__), 'data', 'snapshots')

        # Calcular scores finais
        enriched_data = self.calculate_final_scores(gems_data)

        print(f"\n🏆 Salvando snapshots com scores e ranking (data: {date_str})...")

        # 🚀 Otimização: Consolidar todas as gems enriquecidas
        all_gems = []
        range_limits = []

        for range_name, gems in enriched_data.items():
            if gems:
                # Adicionar info da faixa em cada gem
                for gem in gems:
                    gem['source_range'] = range_name
                all_gems.extend(gems)

                # Extrair limites do range para o nome do arquivo
                if '10m' in range_name:
                    range_limits.append('10M')
                elif '50m' in range_name:
                    range_limits.append('50M')
                elif 'test' in range_name:
                    range_limits.append('TEST')

        # Remover duplicatas por símbolo (manter a de maior score)
        unique_gems = {}
        for gem in all_gems:
            symbol = gem.get('symbol', '')
            if symbol:
                if symbol not in unique_gems or gem.get('final_score', 0) > unique_gems[symbol].get('final_score', 0):
                    unique_gems[symbol] = gem

        final_gems = list(unique_gems.values())

        if final_gems:
            # 🏆 Adicionar contadores de persistência cumulativa
            from persistence_tracker import PersistenceTracker
            tracker = PersistenceTracker()
            final_gems = tracker.update_persistence_counts(final_gems)

            # 🏆 Ordenação FINAL após mesclagem de todos os ranges
            final_gems.sort(key=lambda x: (
                x.get('is_confirmed_leader', False),  # Líderes primeiro
                x.get('persistence_days', 0),          # Mais persistência depois
                x['final_score']                        # Score por último
            ), reverse=True)

            # ── Colunas de acumulação silenciosa ─────────────────────────────────
            for gem in final_gems:
                gem.setdefault('accumulation_score',     0.0)
                gem.setdefault('accumulation_signal',    'none')
                gem.setdefault('accumulation_slope',     0.0)
                gem.setdefault('is_silent_accumulation', False)
                gem.setdefault('sector',                 'Other')

            # ── Colunas de setor (já populadas em find_gems_by_ranges) ───────────
            # (nada extra a fazer aqui — sector já está em cada gem)

            # 🎯 Enriquecer com colunas de eventos especiais
            for gem in final_gems:
                # 📊 Persistência (referência visual)
                # ✅ Parse timeframe_analysis se for string
                timeframe_analysis = gem.get('timeframe_analysis', '{}')
                if isinstance(timeframe_analysis, str):
                    import json
                    try:
                        timeframe_analysis = json.loads(timeframe_analysis)
                    except:
                        timeframe_analysis = {}
                persistence_days = timeframe_analysis.get('medium_term', {}).get('persistence_days', 0)
                gem['persistence_days'] = persistence_days

                # 🏆 Líder confirmado (>7 dias)
                gem['is_confirmed_leader'] = gem.get('timeframe_classification') == 'LEADER_CONFIRMED'

                # 🔥 Explosão social
                social_analysis = gem.get('social_analysis', '{}')
                if isinstance(social_analysis, str):
                    # ✅ Parse JSON string para dict
                    import json
                    try:
                        social_analysis = json.loads(social_analysis)
                    except:
                        social_analysis = {}

                gem['social_explosion'] = social_analysis.get('combined_validation') == 'SOCIAL_EXPLOSION'

                # 🧠 Validação social (completa)
                gem['social_validation'] = social_analysis.get('combined_validation', 'NOT_APPLICABLE')

                # 💪 RS vs BTC forte (usar campo já calculado)
                gem['rs_strong'] = gem.get('rs_strong_24h', False)

            df_all = pd.DataFrame(final_gems)

            # 🎯 Nome inteligente baseado nos ranges presentes
            if len(range_limits) >= 2:
                range_name = f"{min(range_limits)}_to_{max(range_limits)}"
            else:
                range_name = range_limits[0] if range_limits else 'consolidated'

            # Snapshot único enriquecido
            enhanced_file = os.path.join(snapshots_dir, f"gems_{range_name}_enhanced_{date_str}.csv")
            df_all.to_csv(enhanced_file, index=False)
            print(f"  🏆 {range_name} enhanced: {len(final_gems)} gems com scores + eventos especiais")
            print(f"  📁 Arquivo: {enhanced_file}")

            # 🗑️ Deletar arquivo bruto após criar enhanced
            consolidated_file = os.path.join(snapshots_dir, f"gems_{range_name}_{date_str}.csv")
            if os.path.exists(consolidated_file):
                os.remove(consolidated_file)
                print(f"  🗑️ Arquivo bruto deletado: {consolidated_file}")

            # 📊 Mostrar top 10 por final_score
            print(f"\n🏆 TOP 10 GEMS POR FINAL SCORE:")
            print("-" * 120)
            for i, gem in enumerate(final_gems[:10], 1):
                mc = gem['market_cap']
                vol = gem.get('total_volume', 0) or 0
                ratio = vol / mc if mc > 0 else 0
                final_score = gem['final_score']
                persistence = gem.get('persistence_days', 0)
                rs_flag = "💪" if gem.get('rs_strong', False) else "  "
                leader_flag = "👑" if gem.get('is_confirmed_leader', False) else "  "
                social_flag = "🔥" if gem.get('social_explosion', False) else "  "

                print(f"{i:2d}. {gem['symbol']:8s} | MC: ${mc:12,.0f} | Ratio: {ratio:.2f} | Final: {final_score:5.2f} | {persistence:2d}d {rs_flag}{leader_flag}{social_flag} | {gem['name']}")

            # 📈 Estatísticas dos eventos especiais
            confirmed_count = sum(1 for g in final_gems if g.get('is_confirmed_leader', False))
            social_count = sum(1 for g in final_gems if g.get('social_explosion', False))
            rs_count = sum(1 for g in final_gems if g.get('rs_strong', False))

            print(f"\n📊 EVENTOS ESPECIAIS DETECTADOS:")
            print(f"  👑 Líderes confirmados: {confirmed_count}")
            print(f"  🔥 Explosões sociais: {social_count}")
            print(f"  💪 RS vs BTC forte: {rs_count}")

            # ── Resumo setorial no terminal ───────────────────────────────────────
            sector_result = getattr(self, '_last_sector_result', None)
            if sector_result:
                hot  = sector_result.get('hot_sectors', [])
                warm = sector_result.get('warming_sectors', [])
                alert= sector_result.get('current_alert', 'COLD')
                print(f"\n🏭 RESUMO SETORIAL: {alert} | "
                      f"Setores quentes: {', '.join(hot) if hot else 'nenhum'} | "
                      f"Aquecendo: {', '.join(s['sector'] for s in warm[:3])}")

    def analyze_gems(self, gems: List[Dict[str, Any]]) -> None:
        """Análise detalhada das gems encontradas"""
        if not gems:
            print("❌ Nenhuma gem para analisar")
            return

        print(f"\n📊 ANÁLISE DAS {len(gems)} GEMS:")
        print("=" * 80)

        # Estatísticas
        market_caps = [g['market_cap'] for g in gems]
        volumes = [g.get('total_volume', 0) or 0 for g in gems]

        print(f"Market Cap - Médio: ${sum(market_caps)/len(market_caps):,.0f}")
        print(f"Market Cap - Min: ${min(market_caps):,}, Max: ${max(market_caps):,}")
        print(f"Volume - Médio: ${sum(volumes)/len(volumes):,.0f}")
        print(f"Volume - Min: ${min(volumes):,}, Max: ${max(volumes):,}")

        # 🔥 Estatísticas dos novos filtros e zonas
        volume_recovery_count = sum(1 for g in gems if g.get('volume_recovery', False))
        price_resilience_count = sum(1 for g in gems if g.get('price_resilience', False))
        gold_count = sum(1 for g in gems if g.get('is_gold', False))

        # 📊 Análise das zonas
        zone_counts = {}
        for gem in gems:
            zone = gem.get('zone', 'unknown')
            zone_counts[zone] = zone_counts.get(zone, 0) + 1

        print(f"\n🔥 ANÁLISE DAS ZONAS:")
        print(f"  🟡 Early Accumulation (fundo): {zone_counts.get('early_accumulation', 0)} gems")
        print(f"  🟠 Strong (0.5-1.0): {zone_counts.get('strong', 0)} gems")
        print(f"  🔥 Breakout (>1.0): {zone_counts.get('breakout', 0)} gems")

        # 🚨 Estatísticas de Wash Trading
        wash_trading_count = sum(1 for g in gems if g.get('suspected_wash_trading', False))

        # 🚀 Estatísticas de Momentum (Interesse Real)
        momentum_counts = {'high': 0, 'medium': 0, 'low': 0}
        for gem in gems:
            momentum = gem.get('momentum', 'low')
            momentum_counts[momentum] = momentum_counts.get(momentum, 0) + 1

        print(f"\n💪 ANÁLISE DOS FILTROS:")
        print(f"  📊 Recuperação de Volume: {volume_recovery_count}/{len(gems)} ({volume_recovery_count/len(gems)*100:.1f}%)")
        print(f"  💪 Resiliência de Preço: {price_resilience_count}/{len(gems)} ({price_resilience_count/len(gems)*100:.1f}%)")
        print(f"  👑 POTENCIAL OURO: {gold_count}/{len(gems)} ({gold_count/len(gems)*100:.1f}%)")
        print(f"  🚨 WASH TRADING: {wash_trading_count}/{len(gems)} ({wash_trading_count/len(gems)*100:.1f}%)")
        print(f"\n🚀 ANÁLISE DE MOMENTUM (INTERESSE REAL):")
        print(f"  🔥 MOMENTUM ALTO (>20%): {momentum_counts['high']} gems")
        print(f"  📈 MOMENTUM MÉDIO (10-20%): {momentum_counts['medium']} gems")
        print(f"  📊 MOMENTUM BAIXO (<10%): {momentum_counts['low']} gems")

        print(f"\n💎 TOP 10 GEMS:")
        print("-" * 100)

        for i, gem in enumerate(gems[:10], 1):
            mc = gem['market_cap']
            vol = gem.get('total_volume', 0) or 0
            ratio = vol / mc if mc > 0 else 0

            # 🎯 Indicadores dos novos filtros
            vol_rec = "🔥" if gem.get('volume_recovery', False) else "📊"
            price_res = "💪" if gem.get('price_resilience', False) else "📈"
            gold = "👑" if gem.get('is_gold', False) else "  "
            wash = "🚨" if gem.get('suspected_wash_trading', False) else "  "

            # 🚀 Indicador de Momentum (Interesse Real)
            momentum = gem.get('momentum', 'low')
            if momentum == 'high':
                mom_icon = "🚀"
            elif momentum == 'medium':
                mom_icon = "📈"
            else:
                mom_icon = "📊"

            zone = gem.get('zone', 'unknown')[:1].upper()

            print(f"{i:2d}. {gem['symbol']:8s} | MC: ${mc:12,.0f} | Vol: ${vol:12,.0f} | Ratio: {ratio:.2f} | {zone} {vol_rec}{price_res}{gold}{wash}{mom_icon} | {gem['name']}")

def test_gems_finder():
    """Teste do finder de gems por faixas com snapshots"""
    print(" Testando GEMS FINDER - Faixas + Snapshots...")

    finder = GemsFinder()

    try:
        # Buscar por faixas específicas
        gems_data, is_new_data = finder.find_gems_by_ranges()

        # Análise de cada faixa
        for range_name, gems in gems_data.items():
            print(f"\n📊 ANÁLISE - {range_name.upper()}:")
            finder.analyze_gems(gems)

        # Salvar snapshots apenas se dados novos
        snapshot_date = None
        if is_new_data:
            snapshot_date = finder.save_snapshots(gems_data)
            print(f"\n💾 Novos dados encontrados - Snapshot criado!")

            # 🏆 Salvar enhanced snapshots com scores (apenas com dados novos)
            finder.save_enhanced_snapshots(gems_data, snapshot_date)
        else:
            print(f"\n📋 Usando dados existentes - Nenhum snapshot criado")

        # Resumo final
        total_gems = sum(len(gems) for gems in gems_data.values())
        print(f"\n🎉 GEMS FINDER CONCLUÍDO!")
        print(f"📊 Total de gems: {total_gems}")
        if snapshot_date:
            print(f"💾 Snapshot: {snapshot_date}")
        print(f"📁 Arquivos salvos para análise histórica:")
        print(f"   - snapshots/gems_*.csv (por faixa)")
        print(f"   - snapshots/gems_consolidated_*.csv (completo)")
        print(f"   - Cache válido por 12 horas (evita requisições excessivas)")
        print(f"   - Snapshots criados apenas com dados novos")

    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_gems_finder()
