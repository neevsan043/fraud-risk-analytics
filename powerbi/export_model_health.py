import sqlite3
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve, auc
from pathlib import Path

# Project root paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
POWERBI_DIR = BASE_DIR / "powerbi"

def export_model_health_data():
    print("Loading processed data...")
    model_df = pd.read_csv(PROCESSED_DIR / "model_features.csv")
    context_df = pd.read_csv(PROCESSED_DIR / "transaction_features.csv")
    
    # Merge PCA features with contextual attributes
    df = model_df.merge(context_df, on="transaction_id")
    
    X = df.drop(columns=["transaction_id", "class"])
    y = df["class"]
    txn_ids = df["transaction_id"]
    
    print("Executing stratified train/test split (80/20)...")
    X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
        X, y, txn_ids, test_size=0.2, random_state=42, stratify=y
    )
    
    # Positive class weight ratio for imbalance
    ratio = (len(y_train) - sum(y_train)) / sum(y_train)
    
    print("Training XGBoost classifier...")
    model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        scale_pos_weight=ratio,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    test_preds = model.predict(X_test)
    test_probs = model.predict_proba(X_test)[:, 1]
    
    test_results_df = pd.DataFrame({
        "transaction_id": ids_test,
        "actual_label": y_test.values,
        "predicted_label": test_preds,
        "fraud_probability": test_probs,
        "split_type": "Test"
    })
    
    def get_cm_category(row):
        if row["actual_label"] == 1 and row["predicted_label"] == 1:
            return "True Positive (TP)"
        elif row["actual_label"] == 0 and row["predicted_label"] == 1:
            return "False Positive (FP)"
        elif row["actual_label"] == 1 and row["predicted_label"] == 0:
            return "False Negative (FN)"
        else:
            return "True Negative (TN)"
            
    test_results_df["confusion_matrix_category"] = test_results_df.apply(get_cm_category, axis=1)
    
    p, r, thresholds = precision_recall_curve(y_test, test_probs)
    pr_auc_score = auc(r, p)
    
    thresholds_padded = np.append(thresholds, 1.0)
    pr_curve_df = pd.DataFrame({
        "threshold": np.round(thresholds_padded, 4),
        "precision": np.round(p, 4),
        "recall": np.round(r, 4)
    })
    
    pr_curve_df = pr_curve_df.drop_duplicates(subset=["precision", "recall"]).reset_index(drop=True)
    
    test_export_path = POWERBI_DIR / "model_health_test_predictions.csv"
    pr_export_path = POWERBI_DIR / "pr_curve_coordinates.csv"
    
    test_results_df.to_csv(test_export_path, index=False)
    pr_curve_df.to_csv(pr_export_path, index=False)
    
    print("Exports completed:")
    print(f"  -> Test Predictions: {test_export_path} ({len(test_results_df)} rows)")
    print(f"  -> PR Curve Coordinates: {pr_export_path} ({len(pr_curve_df)} distinct coordinate points, PR-AUC: {pr_auc_score:.4f})")

if __name__ == "__main__":
    export_model_health_data()