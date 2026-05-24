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

def load_training_data():
    """
    Carrega o histórico de performance e os snapshots correspondentes.
    Retorna X (features) e y (target: 1 se pct_change > 10, 0 caso contrário).
    """
    if not os.path.exists(PERF_FILE):
        return None, None
    with open(PERF_FILE, "r") as f:
        perf = json.load(f)

    if len(perf) < 30:
        print(f"Apenas {len(perf)} registros, mínimo 30 para treinar.")
        return None, None

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
        pick_date = entry.get("date")  # formato "YYYY-MM-DD"
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
        # Extrair features
        features = []
        for col in feature_cols:
            if col in row.columns:
                val = row.iloc[0][col]
                if pd.isna(val):
                    val = 0
                features.append(val)
            else:
                features.append(0)
        # Target: 1 se ganhou mais de 10%
        target = 1 if entry.get("pct_change", 0) > 10 else 0
        X_list.append(features)
        y_list.append(target)

    if len(X_list) < 20:
        print(f"Apenas {len(X_list)} amostras com features, treino cancelado.")
        return None, None

    return np.array(X_list), np.array(y_list)

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
    """
    Adiciona campo ml_score a cada pick do Claude.
    Usado pelo gems_ai_filter.py.
    """
    if not os.path.exists(MODEL_FILE):
        return claude_result
    model = joblib.load(MODEL_FILE)
    feature_cols = [
        "ratio", "drawdown_pct", "accumulation_score", "social_score",
        "rank_up", "vol_up", "smart_money_div", "seller_exhaustion",
        "composite_score"
    ]
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
        proba = model.predict_proba([X])[0, 1]  # probabilidade da classe 1 (WIN)
        pick["ml_score"] = round(proba, 3)
    return claude_result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="Treina o modelo")
    args = parser.parse_args()
    if args.train:
        train_model()
    else:
        print("Use --train para treinar o modelo.")
