from gems_ai_filter import _load_results, _save_results, _fetch_coingecko_price
import time
from datetime import datetime

results = _load_results()
weekly = results.get("weekly")
if weekly:
    for pick in weekly["top_picks"]:
        if not pick.get("price_usd"):
            sym = pick["symbol"]
            print(f"🔍 Buscando preço para {sym}...")
            price = _fetch_coingecko_price(sym)
            if price > 0:
                pick["price_usd"] = price
                pick["price_date"] = datetime.now().isoformat()
                print(f"✅ {sym}: ${price}")
            else:
                print(f"❌ Não foi possível obter preço para {sym}")
            time.sleep(3)
    _save_results(results)
    print("🎯 Backfill concluído!")
else:
    print("Nenhum resultado semanal encontrado.")
