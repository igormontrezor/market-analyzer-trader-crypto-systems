import requests
import os
from datetime import datetime

def get_btc_funding_rate_real():
    """Busca funding rate do BTC/USDT da Binance"""
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
        response = requests.get(url, timeout=5)
        rate = float(response.json().get('lastFundingRate', 0)) * 100

        # Registrar em CSV
        csv_path = os.path.join("data", "macro", "funding_rate_history.csv")
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        now = datetime.now()
        timestamp_hour = now.strftime("%Y-%m-%d %H:00:00")

        # Verificar se já registrou essa hora
        already_logged = False
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines and timestamp_hour in lines[-1]:
                        already_logged = True
            except:
                pass

        if not already_logged:
            file_exists = os.path.exists(csv_path)
            with open(csv_path, 'a', encoding='utf-8') as f:
                if not file_exists:
                    f.write("timestamp,funding_rate\n")
                f.write(f"{timestamp_hour},{rate:.6f}\n")

        return rate
    except:
        return 0.01

if __name__ == "__main__":
    rate = get_btc_funding_rate_real()
    print(f"Funding Rate atualizado: {rate:.6f}%")
