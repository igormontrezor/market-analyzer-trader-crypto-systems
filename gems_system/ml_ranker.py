# gems_system/ml_ranker.py
import os
import sys
import json
import argparse
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import xgboost as xgb

# Caminhos relativos (ajuste conforme seu projeto)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PERF_FILE = os.path.join(DATA_DIR, "gems_ai_performance.json")
MODEL_FILE = os.path.join(DATA_DIR, "ml_ranker.pkl")
HISTORICAL_SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")  # para buscar features


def _load_macro_signals():
    macro_path = os.path.join(DATA_DIR, "macro_signals.json")
    if not os.path.exists(macro_path):
        return []
    try:
        with open(macro_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def _regime_winrate_upto_date(regime, target_date, macro_signals):
    """
    Calcula o winrate do regime especificado (ex: 'BUY_MACRO') para todos os sinais
    que ocorreram antes da target_date (inclusive). Ignora sinais futuros.
    Retorna float entre 0 e 1, ou 0.5 se não houver histórico suficiente.
    """
    relevant = []
    for sig in macro_signals:
        sig_date = sig.get("date")
        if sig_date and sig_date <= target_date:
            if sig.get("regime") == regime:
                # Usa outcome_7d se disponível, senão tenta outcome_30d
                outcome = sig.get("outcome_7d")
                if outcome is None:
                    outcome = sig.get("outcome_30d")
                if outcome in ("WIN", "LOSS"):
                    relevant.append(1 if outcome == "WIN" else 0)
    if len(relevant) < 3:
        return 0.5  # neutro
    return sum(relevant) / len(relevant)

def _one_hot_regime(regime):
    """Retorna um vetor de features one-hot para os regimes mais comuns."""
    regimes_list = ["BUY_MACRO", "BUY_CONFIRMED", "SUPER_BUY",
                    "SELL_MACRO", "SELL_CONFIRMED", "SUPER_SELL",
                    "CAPITULATION", "SELL_REBOUND", "NEUTRO"]
    return [1 if regime == r else 0 for r in regimes_list]

def load_training_data():
    """
    Carrega o histórico de performance e os snapshots correspondentes.
    Retorna X (features) e y (target: 1 se pct_change > 10, 0 caso contrário).
    Agora inclui features macro: winrate do regime + one-hot do regime.
    """
    if not os.path.exists(PERF_FILE):
        return None, None
    with open(PERF_FILE, "r") as f:
        perf = json.load(f)

    if len(perf) < 30:
        print(f"Apenas {len(perf)} registros, mínimo 30 para treinar.")
        return None, None

    # Carregar sinais macro
    macro_signals = _load_macro_signals()
    # Ordenar por data para facilitar busca do regime mais recente
    macro_signals_sorted = sorted(macro_signals, key=lambda x: x.get("date", ""))
    # Construir dicionário data -> regime (último regime conhecido até aquela data)
    regime_by_date = {}
    last_regime = "NEUTRO"
    for sig in macro_signals_sorted:
        date = sig.get("date")
        if date:
            last_regime = sig.get("regime", last_regime)
            regime_by_date[date] = last_regime
    # Função para obter regime em uma data específica (última data <= data)
    def get_regime_for_date(target_date):
        # Pega a última data que é <= target_date
        last_date = None
        for d in sorted(regime_by_date.keys()):
            if d <= target_date:
                last_date = d
            else:
                break
        if last_date:
            return regime_by_date[last_date]
        return "NEUTRO"

    # Lista de features que usamos (devem estar disponíveis nos snapshots)
    feature_cols = [
        "ratio", "drawdown_pct", "accumulation_score", "social_score",
        "rank_up", "vol_up", "smart_money_div", "seller_exhaustion",
        "composite_score"
    ]

    X_list = []
    y_list = []

    for entry in perf:
        # A data do pick é a chave para carregar o snapshot correspondente
        pick_date = entry.get("analysis_date") or entry.get("date")  # analysis_date é mais preciso
        if not pick_date:
            continue
        # Procurar o snapshot mais próximo (até 2 dias antes)
        snapshot_df = find_snapshot_near_date(pick_date)
        if snapshot_df is None:
            continue
        symbol = entry.get("symbol")
        # Buscar a linha do ativo no snapshot
        row = snapshot_df[snapshot_df["symbol"] == symbol]
        if row.empty:
            continue
        # Extrair features originais
        features = []
        for col in feature_cols:
            if col in row.columns:
                val = row.iloc[0][col]
                if pd.isna(val):
                    val = 0
                features.append(val)
            else:
                features.append(0)

        # --- Adicionar features macro ---
        # Obter regime na data da pick
        regime = get_regime_for_date(pick_date)
        # Calcular winrate histórico desse regime até a data da pick
        regime_winrate = _regime_winrate_upto_date(regime, pick_date, macro_signals)
        features.append(regime_winrate)
        # Adicionar one-hot do regime (opcional, mas recomendado)
        features.extend(_one_hot_regime(regime))

        # Target: 1 se ganhou mais de 10%
        target = 1 if entry.get("pct_change", 0) > 10 else 0
        X_list.append(features)
        y_list.append(target)

    if len(X_list) < 20:
        print(f"Apenas {len(X_list)} amostras com features, treino cancelado.")
        return None, None

    # Converter para arrays numpy
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    return X, y

def find_snapshot_near_date(date_str):
    """Encontra o snapshot mais próximo da data (até 2 dias antes)."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    # Listar todos os snapshots (arquivos CSV em data/snapshots)
    if not os.path.exists(HISTORICAL_SNAPSHOTS_DIR):
        return None
    files = [f for f in os.listdir(HISTORICAL_SNAPSHOTS_DIR) if f.endswith(".csv")]
    # Ordenar por data decrescente
    files.sort(reverse=True)
    for f in files:
        # Extrair data do nome do arquivo (ex: gems_10M_to_50M_20250315_143022_enhanced.csv)
        parts = f.split("_")
        # Procurar parte que parece data YYYYMMDD
        for part in parts:
            if len(part) == 8 and part.isdigit():
                file_date = datetime.strptime(part, "%Y%m%d").date()
                if file_date <= target_date and (target_date - file_date).days <= 2:
                    df = pd.read_csv(os.path.join(HISTORICAL_SNAPSHOTS_DIR, f))
                    return df
    return None

def train_model():
    print("Iniciando treinamento do modelo ML...")
    X, y = load_training_data()
    if X is None:
        print("Dados insuficientes para treinar.")
        return

    # Dividir treino/validação
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    # Modelo simples (pode ser XGBoost, mas evita dependência extra)
    model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.1,
    subsample=0.8,
    random_state=42,
    use_label_encoder=False,
    eval_metric='logloss'
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)
    acc = accuracy_score(y_val, y_pred)
    print(f"Acurácia na validação: {acc:.2f}")
    # Salvar modelo
    joblib.dump(model, MODEL_FILE)
    print(f"Modelo salvo em {MODEL_FILE}")

def ml_predict_picks(claude_result, df_agg):
    if not os.path.exists(MODEL_FILE):
        return claude_result
    model = joblib.load(MODEL_FILE)

    # Carregar macro signals para calcular winrate atual
    macro_signals = _load_macro_signals()
    current_date = datetime.now().strftime("%Y-%m-%d")
    # Obter regime atual – precisamos importar a função do gems_ai_filter
    try:
        from gems_ai_filter import _get_current_macro_regime
        current_regime = _get_current_macro_regime()
    except:
        current_regime = "NEUTRO"
    regime_winrate = _regime_winrate_upto_date(current_regime, current_date, macro_signals)
    one_hot = _one_hot_regime(current_regime)

    feature_cols = [
        "ratio", "drawdown_pct", "accumulation_score", "social_score",
        "rank_up", "vol_up", "smart_money_div", "seller_exhaustion",
        "composite_score"
    ]
    # Número de features macro adicionadas: 1 (winrate) + len(one_hot)
    # Precisamos saber quantas são – podemos usar a mesma lista de regimes definida em _one_hot_regime
    # Aqui usaremos um valor fixo baseado na função (9 regimes)
    NUM_MACRO_FEATURES = 1 + 9  # winrate + 9 one-hot (ajuste conforme lista)

    for pick in claude_result.get("top_picks", []):
        sym = pick["symbol"]
        row = df_agg[df_agg["symbol"] == sym]
        if row.empty:
            pick["ml_score"] = None
            continue
        X = []
        for col in feature_cols:
            if col in row.columns:
                val = row.iloc[0][col]
                if pd.isna(val):
                    val = 0
                X.append(val)
            else:
                X.append(0)
        # Adicionar features macro
        X.append(regime_winrate)
        X.extend(one_hot)
        # Garantir que o número de features bate com o modelo
        if len(X) != model.n_features_in_:
            print(f"⚠️ Número de features incompatível: modelo espera {model.n_features_in_}, temos {len(X)}")
            # Tentar truncar ou completar com zeros? Melhor pular.
            pick["ml_score"] = None
            continue
        proba = model.predict_proba([X])[0, 1]
        pick["ml_score"] = round(proba, 3)
    return claude_result
