from dataclasses import dataclass
from typing import Dict

@dataclass
class Arbitration:
    exchanges: Dict[str, any]
    symbol: str

    def get_prices(self):
        prices = {}
        for name, exchange in self.exchanges.items():
            try:
                price = exchange.fetch_ticker(self.symbol)['last']
                prices[name] = price
            except Exception:
                continue
        return prices
