# gems_system/ml_ranker.py
import os
import sys
import json
import argparse
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb

# Caminhos relativos (ajuste conforme seu projeto)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PERF_FILE = os.path.join(DATA_DIR, "gems_ai_performance.json")
MODEL_FILE = os.path.join(DATA_DIR, "ml_ranker.pkl")
HISTORICAL_SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")  # para buscar features

MODELS_DIR = os.path.join(DATA_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)
VERSIONS_FILE = os.path.join(MODELS_DIR, "ml_model_versions.json")
MAX_VERSIONS = 10  # manter apenas as 10 versões mais recentes

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

    # Coletar todos os retornos percentuais dos picks
    all_returns = []
    for entry in perf:
        pct = entry.get("pct_change", 0)
        if pct is not None:
            all_returns.append(pct)

    # Se tivermos pelo menos 10 retornos positivos, calcular o percentil 70
    pos_returns = [r for r in all_returns if r > 0]
    if len(pos_returns) >= 10:
        dynamic_threshold = np.percentile(pos_returns, 70)   # 70º percentil (top 30%)
    else:
        # Fallback: usar 10% se dados insuficientes
        dynamic_threshold = 10.0

    print(f"🔧 Limiar dinâmico para target: {dynamic_threshold:.2f}% (baseado em {len(pos_returns)} retornos positivos)")


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
    date_list = []

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

        # --- Adicionar features derivadas (interações) ---
        # 1. ratio * regime_winrate
        ratio_val = features[feature_cols.index("ratio")] if "ratio" in feature_cols else 0
        ratio_interaction = ratio_val * regime_winrate
        features.append(ratio_interaction)

        # 2. drawdown_pct * regime_winrate
        drawdown_val = features[feature_cols.index("drawdown_pct")] if "drawdown_pct" in feature_cols else 0
        drawdown_interaction = drawdown_val * regime_winrate
        features.append(drawdown_interaction)

        # 3. composite_score * regime_winrate
        comp_score_val = features[feature_cols.index("composite_score")] if "composite_score" in feature_cols else 0
        comp_interaction = comp_score_val * regime_winrate
        features.append(comp_interaction)

        # 4. seller_exhaustion * regime_winrate (seller_exhaustion é booleano, converter para float)
        seller_val = features[feature_cols.index("seller_exhaustion")] if "seller_exhaustion" in feature_cols else 0
        seller_interaction = float(seller_val) * regime_winrate
        features.append(seller_interaction)

        # Target: 1 se ganhou mais de 10%
        target = 1 if entry.get("pct_change", 0) >= dynamic_threshold else 0
        X_list.append(features)
        y_list.append(target)
        date_list.append(pick_date)

    if X_list:
        combined = sorted(zip(date_list, X_list, y_list), key=lambda x: x[0])
        _, X_list, y_list = zip(*combined)
        X_list = list(X_list)
        y_list = list(y_list)

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
    if not os.path.exists(HISTORICAL_SNAPSHOTS_DIR):
        return None
    files = [f for f in os.listdir(HISTORICAL_SNAPSHOTS_DIR) if f.endswith(".csv")]
    files.sort(reverse=True)
    for f in files:
        # Extrair data do nome do arquivo
        parts = f.split("_")
        file_date = None
        for part in parts:
            if len(part) == 8 and part.isdigit():
                file_date = datetime.strptime(part, "%Y%m%d").date()
                break
        if file_date is None:
            continue
        if file_date <= target_date and (target_date - file_date).days <= 2:
            try:
                df = pd.read_csv(os.path.join(HISTORICAL_SNAPSHOTS_DIR, f))
                # Verificar se o DataFrame tem a coluna 'symbol' (opcional)
                if df is not None and 'symbol' in df.columns:
                    return df
                else:
                    print(f"⚠️ Snapshot {f} sem coluna 'symbol', ignorado.")
            except Exception as e:
                print(f"⚠️ Erro ao ler snapshot {f}: {e}, ignorando.")
                continue
    return None

def train_model():
    print("Iniciando treinamento do modelo ML...")
    X, y = load_training_data()
    if X is None:
        print("Dados insuficientes para treinar.")
        return

    # Garantir que os dados estão ordenados cronologicamente
    # (assumindo que load_training_data já retorna na ordem dos picks)
    # Se não estiver, ordenar antes – mas load_training_data percorre perf em ordem arbitrária.
    # Para segurança, vamos reordenar os pares (X, y) pela data do pick.
    # Como a função load_training_data não retorna as datas, precisamos modificá-la para retornar também uma lista de datas.
    # Melhor: modificar load_training_data para retornar X, y, dates.
    # Vamos fazer a correção completa.

    # Dividir cronologicamente: 80% primeiros para treino, 20% últimos para validação
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # ... após o split ...
    pos_train = np.sum(y_train == 1)
    neg_train = np.sum(y_train == 0)
    if pos_train > 0:
        scale_pos_weight = neg_train / pos_train
    else:
        scale_pos_weight = 1.0
    print(f"📊 Classe positiva: {pos_train} amostras, negativa: {neg_train} → scale_pos_weight = {scale_pos_weight:.2f}")

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss',
        scale_pos_weight=scale_pos_weight   # ← adicionar
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:, 1]   # probabilidade da classe positiva

    acc  = accuracy_score(y_val, y_pred)
    prec = precision_score(y_val, y_pred, zero_division=0)
    rec  = recall_score(y_val, y_pred)
    f1   = f1_score(y_val, y_pred)
    auc  = roc_auc_score(y_val, y_proba)

    print("=" * 60)
    print("📊 MÉTRICAS DE VALIDAÇÃO (cronológica):")
    print(f"  Acurácia   : {acc:.3f}")
    print(f"  Precisão   : {prec:.3f}")
    print(f"  Recall     : {rec:.3f}")
    print(f"  F1‑score   : {f1:.3f}")
    print(f"  ROC‑AUC    : {auc:.3f}")
    print("=" * 60)

    n_samples = X.shape[0]
    n_features = X.shape[1]
    _save_model_version(model, acc, n_samples, n_features)

def _save_model_version(model, accuracy: float, n_samples: int, n_features: int):
    """Salva o modelo com timestamp e registra metadados."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ml_ranker_{timestamp}.pkl"
    filepath = os.path.join(MODELS_DIR, filename)

    # Salvar modelo
    joblib.dump(model, filepath)

    # Carregar versões existentes
    versions = []
    if os.path.exists(VERSIONS_FILE):
        with open(VERSIONS_FILE, "r") as f:
            versions = json.load(f)

    # Adicionar nova versão
    versions.append({
        "version": timestamp,
        "filename": filename,
        "accuracy": round(accuracy, 4),
        "n_samples": n_samples,
        "n_features": n_features,
        "date": datetime.now().isoformat()
    })

    # Manter apenas as MAX_VERSIONS mais recentes (primeiras no arquivo = mais antigas)
    versions = versions[-MAX_VERSIONS:]

    # Salvar metadados
    with open(VERSIONS_FILE, "w") as f:
        json.dump(versions, f, indent=2)

    # Opcional: excluir arquivos de versões antigas que não estão na lista
    keep_filenames = {v["filename"] for v in versions}
    for f in os.listdir(MODELS_DIR):
        if f.startswith("ml_ranker_") and f.endswith(".pkl") and f not in keep_filenames:
            os.remove(os.path.join(MODELS_DIR, f))

    # Também sobrescrever o modelo padrão (para compatibilidade)
    joblib.dump(model, MODEL_FILE)

    print(f"✅ Modelo versão {timestamp} salvo (acurácia {accuracy:.2f}, {n_samples} amostras)")

def _get_best_model():
    """
    Carrega a versão do modelo com maior acurácia registrada no arquivo de versões.
    Se não encontrar, tenta carregar o modelo padrão (ml_ranker.pkl).
    Retorna o modelo carregado ou None se nenhum for encontrado.
    """
    # Tenta carregar a lista de versões
    if not os.path.exists(VERSIONS_FILE):
        # Fallback: modelo padrão
        if os.path.exists(MODEL_FILE):
            print("[ML] Nenhum registro de versões encontrado. Usando modelo padrão.")
            return joblib.load(MODEL_FILE)
        return None

    try:
        with open(VERSIONS_FILE, "r") as f:
            versions = json.load(f)
    except Exception as e:
        print(f"[ML] Erro ao ler versões: {e}. Usando modelo padrão.")
        if os.path.exists(MODEL_FILE):
            return joblib.load(MODEL_FILE)
        return None

    if not versions:
        print("[ML] Nenhuma versão registrada. Usando modelo padrão.")
        if os.path.exists(MODEL_FILE):
            return joblib.load(MODEL_FILE)
        return None

    # Encontra a versão com maior acurácia
    best_version = max(versions, key=lambda v: v.get("accuracy", 0))
    best_path = os.path.join(MODELS_DIR, best_version.get("filename"))
    if best_version.get("filename") is None or not os.path.exists(best_path):
        print("[ML] Melhor versão sem nome de arquivo. Usando modelo padrão.")
        if os.path.exists(MODEL_FILE):
            return joblib.load(MODEL_FILE)
        return None

    if not os.path.exists(best_path):
        print(f"[ML] Arquivo da melhor versão ({best_version['filename']}) não encontrado. Usando modelo padrão.")
        if os.path.exists(MODEL_FILE):
            return joblib.load(MODEL_FILE)
        return None

    print(f"[ML] ✅ Usando melhor modelo: versão {best_version['version']} (acurácia {best_version['accuracy']:.2f}, {best_version['n_samples']} amostras)")
    return joblib.load(best_path)

def get_current_model_info():
    if not os.path.exists(VERSIONS_FILE):
        if os.path.exists(MODEL_FILE):
            return {"version": "legacy", "accuracy": None, "n_samples": None, "n_features": None, "date": None}
        return None

    with open(VERSIONS_FILE, "r") as f:
        versions = json.load(f)

    if not versions:
        return None

    # Encontra a versão com maior acurácia (usa .get para evitar KeyError)
    best = max(versions, key=lambda v: v.get("accuracy", 0))
    # Se a melhor tiver acurácia 0 e não tiver a chave, pode ser qualquer uma; pega a primeira
    if best.get("accuracy") is None:
        best = versions[0]

    return {
        "version": best.get("version", "unknown"),
        "accuracy": best.get("accuracy"),
        "n_samples": best.get("n_samples"),
        "n_features": best.get("n_features"),
        "date": best.get("date")
    }

def ml_predict_picks(claude_result, df_agg):
    if not os.path.exists(MODEL_FILE):
        return claude_result
    model = _get_best_model()
    if model is None:
        print("[ML] Nenhum modelo disponível para predição.")
        return claude_result
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

        # --- Adicionar features derivadas (mesma ordem do treinamento) ---
        # 1. ratio * regime_winrate
        ratio_val = X[feature_cols.index("ratio")] if "ratio" in feature_cols else 0
        X.append(ratio_val * regime_winrate)

        # 2. drawdown_pct * regime_winrate
        drawdown_val = X[feature_cols.index("drawdown_pct")] if "drawdown_pct" in feature_cols else 0
        X.append(drawdown_val * regime_winrate)

        # 3. composite_score * regime_winrate
        comp_score_val = X[feature_cols.index("composite_score")] if "composite_score" in feature_cols else 0
        X.append(comp_score_val * regime_winrate)

        # 4. seller_exhaustion * regime_winrate
        seller_val = X[feature_cols.index("seller_exhaustion")] if "seller_exhaustion" in feature_cols else 0
        X.append(float(seller_val) * regime_winrate)

        # Garantir que o número de features bate com o modelo
        if len(X) != model.n_features_in_:
            print(f"⚠️ Número de features incompatível: modelo espera {model.n_features_in_}, temos {len(X)}")
            # Tentar truncar ou completar com zeros? Melhor pular.
            pick["ml_score"] = None
            continue
        proba = model.predict_proba([X])[0, 1]
        pick["ml_score"] = round(proba, 3)
    return claude_result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Treina o modelo ML do Gems AI Filter")
    parser.add_argument("--force", action="store_true", help="Força re-treino mesmo se o modelo existir")
    args = parser.parse_args()
    train_model()
