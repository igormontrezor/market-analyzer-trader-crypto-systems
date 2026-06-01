import json
import os

DEAD_BAND = 0.002
PERF_FILE = os.path.join(os.path.expanduser("~"), ".montrezor_performance.json")

def limpar_performance():
    if not os.path.exists(PERF_FILE):
        print("Arquivo de performance não encontrado.")
        return

    with open(PERF_FILE, "r", encoding="utf-8") as f:
        perf = json.load(f)

    original_count = len(perf)
    # Filtra: mantém apenas registros onde o resultado 30d (se existir) tem |result| > DEAD_BAND
    # Se o registro não tiver result_30d, mantém (pode ser sinal recente)
    nova_perf = {}
    for sid, rec in perf.items():
        result = rec.get("result_30d")
        if result is None or abs(result) > DEAD_BAND:
            nova_perf[sid] = rec
        else:
            print(f"Removido: {rec.get('symbol')} {rec.get('direction')} {rec.get('timestamp')} -> retorno={result:.4%}")

    if len(nova_perf) < original_count:
        # faz backup antes de sobrescrever
        backup = PERF_FILE + ".backup"
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(perf, f, indent=2)
        print(f"Backup salvo em {backup}")

        with open(PERF_FILE, "w", encoding="utf-8") as f:
            json.dump(nova_perf, f, indent=2)
        print(f"Removidos {original_count - len(nova_perf)} registros com |retorno| <= {DEAD_BAND*100:.1f}%")
    else:
        print("Nenhum registro precisou ser removido.")

if __name__ == "__main__":
    limpar_performance()
